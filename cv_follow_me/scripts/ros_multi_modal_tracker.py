#!/usr/bin/env python3
# ros_multi_modal_tracker.py
import os

import torch
import argparse
import datetime
import sys
import time
import traceback
import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge, CvBridgeError
from ultralytics import YOLO
import face_recognition
import mediapipe as mp
import config
from feature_extractors import (RGBFeatureExtractor, DepthFeatureExtractor, SkeletonFeatureExtractor, FaceRecognitionFeatureExtractor, ForearmColorFeatureExtractor)
from reid_system import ReIDSystem
from kalman_filter import KalmanFilterPy
import event_and_state_handlers as esh
import vision_utils

# ROS Message Imports
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

# MediaPipe Setup
mp_drawing = None
mp_pose = None
if config.MODALITY_WEIGHTS.get("Skeleton", 0) > 0 or config.MODALITY_WEIGHTS.get("ForearmColor", 0) > 0:
    try:
        mp_drawing = mp.solutions.drawing_utils
        mp_pose = mp.solutions.pose
        if config.PRINT_STATEMENTS:
            rospy.loginfo("MediaPipe drawing utils and pose solution imported for skeleton/forearm visualization.")
    except ImportError:
        rospy.logerr("Failed to import MediaPipe. Skeleton/Forearm drawing will be disabled.")
        mp_drawing = None
        mp_pose = None


class MultiModalRealsenseTracker:
    def __init__(self, yolo_model_path_arg, yolo_confidence_arg, acquisition_duration_arg):
        rospy.init_node(config.NODE_NAME, anonymous=True)
        self.bridge = CvBridge()
        self.window_name = config.MAIN_WINDOW_NAME

        # --- Initialize critical state attributes EARLY ---
        self.current_app_state = config.STATE_IDLE 
        self.acquisition_start_time = None
        self.target_samples_collected_during_acquisition = 0
        self.last_kf_time_update = rospy.Time.now() 
        self.frames_since_kf_update = 0
        self.tracked_target_info = {'box': None, 'score': -float('inf'), 'kf_box': None}
        self.kf = None 

        self.current_target_consecutive_reid_count = 0 
        
        if config.DISPLAY_RGB_VIDEO:
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

        if config.DISPLAY_DEPTH_VIDEO and config.DEPTH_WINDOW_NAME:
            cv2.namedWindow(config.DEPTH_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)

        self.record_feed = config.RECORD_VIDEO_FEED
        self.video_writer = None
        self.output_video_path = None
        self.recording_fps = config.RECORDING_FPS
        codec_str = config.RECORDING_CODEC[:4] if config.RECORDING_CODEC else 'mp4v'
        self.recording_codec_fourcc = cv2.VideoWriter_fourcc(*codec_str)
        self.recording_file_extension = config.RECORDING_FILE_EXTENSION if config.RECORDING_FILE_EXTENSION.startswith('.') else '.' + config.RECORDING_FILE_EXTENSION

        self.color_image = None
        self.raw_depth_image = None
        self.display_depth_image = None
        self.new_color_frame_flag = False
        self.new_depth_frame_flag = False
        self.camera_info = None
        self.fx, self.fy, self.cx, self.cy = None, None, None, None
        self.camera_optical_frame_id = config.DEFAULT_CAMERA_OPTICAL_FRAME_ID

        self.color_sub = rospy.Subscriber(config.COLOR_IMAGE_TOPIC, Image, self.color_image_callback, queue_size=1, buff_size=2**24)
        self.depth_sub = rospy.Subscriber(config.DEPTH_IMAGE_TOPIC, Image, self.depth_image_callback, queue_size=1, buff_size=2**24)

        self.camera_info_sub = rospy.Subscriber(config.CAMERA_INFO_TOPIC, CameraInfo, self.camera_info_callback)
        self.target_pose_pub = rospy.Publisher(config.TARGET_POSE_TOPIC, PoseStamped, queue_size=10)
        
        self.PoseStamped = PoseStamped
        self.KalmanFilterPy = KalmanFilterPy
 
        self.state_feedback_pub = None 
        if config.USE_TOPIC_CONTROL:
            self.state_control_sub = rospy.Subscriber(config.STATE_CONTROL_TOPIC, String, self.state_control_callback, queue_size=10) 
            self.state_feedback_pub = rospy.Publisher(config.STATE_CONTROL_TOPIC, String, queue_size=1) 
            if config.PRINT_STATEMENTS:
                rospy.loginfo(f"Topic control enabled. Subscribed to and Publishing on '{config.STATE_CONTROL_TOPIC}' for state control/feedback.")
            rospy.Timer(rospy.Duration(0.5), self._publish_initial_idle_state, oneshot=True)
        else:
            if config.PRINT_STATEMENTS:
                rospy.loginfo("Keyboard control enabled. State control topic is not used.")


        try:
            if not os.path.exists(yolo_model_path_arg):
                rospy.logwarn(f"YOLO model path '{yolo_model_path_arg}' does not exist. Attempting to load anyway.")
            self.yolo_model = YOLO(yolo_model_path_arg)
            if config.PRINT_STATEMENTS:
                rospy.loginfo(f"YOLO model '{yolo_model_path_arg}' loaded.")
        except Exception as e:
            rospy.logerr(f"Failed to load YOLO model from '{yolo_model_path_arg}': {e}")
            raise

        self.yolo_confidence = yolo_confidence_arg
        self.target_class_name = "person"
        self.acquisition_duration = rospy.Duration(acquisition_duration_arg)
        
        if config.PRINT_STATEMENTS:
            rospy.loginfo(f"Acquisition duration: {acquisition_duration_arg}s.")
        self.yolo_target_class_id = None
        try:
            if hasattr(self.yolo_model, 'model') and hasattr(self.yolo_model.model, 'names'):
                yolo_names = self.yolo_model.model.names
                for class_id, name_from_model in yolo_names.items():
                    if name_from_model == self.target_class_name:
                        self.yolo_target_class_id = class_id
                        break
                if self.yolo_target_class_id is None:
                    raise ValueError(f"Target class '{self.target_class_name}' not found in YOLO model names: {yolo_names}")
            else: 
                rospy.logwarn("Cannot directly access YOLO class names...")
                if self.target_class_name == 'person':
                    self.yolo_target_class_id = 0 
                    rospy.loginfo(f"Assuming 'person' is class ID 0...")
                else: 
                    raise ValueError(f"Target class is '{self.target_class_name}' but cannot verify its ID...")
        except Exception as e:
            rospy.logerr(f"Error determining YOLO target class ID: {e}")
            raise

        if config.PRINT_STATEMENTS:
            rospy.loginfo(f"Tracking YOLO class: '{self.target_class_name}' (ID: {self.yolo_target_class_id}), conf > {self.yolo_confidence}")

        self.skeleton_extractor_instance = None
        self.reid_module = None
        self.initialize_reid_system_components()

        self.KF_UPDATE_LOSS_THRESHOLD = config.KF_UPDATE_LOSS_THRESHOLD
        self.KF_DEFAULT_DT = config.KF_DEFAULT_DT
        self.KF_STD_ACC_PROCESS = config.KF_STD_ACC_PROCESS
        self.KF_STD_MEAS_POS = config.KF_STD_MEAS_POS
        self.KF_STD_MEAS_SIZE = config.KF_STD_MEAS_SIZE
        
        initial_control_mode = "TOPIC" if config.USE_TOPIC_CONTROL else "KEYBOARD"
        if config.PRINT_STATEMENTS:
            rospy.loginfo(f"Tracker initialized. Control Mode: {initial_control_mode}. Current State: {self.current_app_state}")
        if config.PRINT_STATEMENTS and not config.USE_TOPIC_CONTROL:
             rospy.loginfo("Press SPACE to start acquisition, 'r' to reset, 'q' to quit.")

    def _publish_initial_idle_state(self, event=None):
        """Publishes the initial IDLE state if topic control is enabled."""
        if config.USE_TOPIC_CONTROL and self.state_feedback_pub:
            if self.current_app_state == config.STATE_IDLE:
                try:
                    self.state_feedback_pub.publish(String(data=config.TOPIC_STATE_IDLE))
                    rospy.loginfo(f"Published initial '{config.TOPIC_STATE_IDLE}' state to {config.STATE_CONTROL_TOPIC}.")
                except Exception as e:
                    rospy.logerr(f"Failed to publish initial IDLE state: {e}")

    def state_control_callback(self, msg):
        """Handles incoming state commands from the control topic."""
        commanded_topic_str = msg.data.lower()
        rospy.loginfo(f"Received state command via topic: '{commanded_topic_str}'")

        if not hasattr(self, 'current_app_state'):
            rospy.logerr("CRITICAL: current_app_state attribute not found in state_control_callback.")
            return

        # Map topic string to internal state constant
        target_internal_state = None
        if commanded_topic_str == config.TOPIC_STATE_IDLE:
            target_internal_state = config.STATE_IDLE
        elif commanded_topic_str == config.TOPIC_STATE_ACQUIRE:
            target_internal_state = config.STATE_ACQUIRING_TARGET
        elif commanded_topic_str == config.TOPIC_STATE_TRACK:
            target_internal_state = config.STATE_TRACKING_TARGET
        else:
            rospy.logwarn(f"Unknown state command '{commanded_topic_str}' received on topic. Ignoring.")
            return

        # If the commanded state is the same as the current internal state, do nothing.
        if target_internal_state == self.current_app_state:
            rospy.loginfo(f"Command '{commanded_topic_str}' matches current state '{self.current_app_state}'. No action taken.")
            # Do NOT re-publish here, as it can cause loops if this callback is triggered by its own message.
            # The esh functions will publish upon actual state *change*.
            return

        # --- Process valid state transition requests ---
        # The esh functions are responsible for setting self.current_app_state
        # and publishing the new state string to the topic.

        if target_internal_state == config.STATE_IDLE:
            esh._reset_and_go_to_idle(self, triggered_by="topic_command_idle", full_reset=False, publish_now=True) 
        
        elif target_internal_state == config.STATE_ACQUIRING_TARGET:
            if self.current_app_state == config.STATE_IDLE:
                esh.initiate_acquisition_sequence(self) 
            else: 
                rospy.logwarn(f"Cannot transition to ACQUIRE from current state '{self.current_app_state}'. Must be IDLE. Send '{config.TOPIC_STATE_IDLE}' first.")
                # Feedback current actual state if command is invalid for current context
                if self.state_feedback_pub:
                    current_state_topic_str_feedback = ""
                    if self.current_app_state == config.STATE_ACQUIRING_TARGET: current_state_topic_str_feedback = config.TOPIC_STATE_ACQUIRE
                    elif self.current_app_state == config.STATE_TRACKING_TARGET: current_state_topic_str_feedback = config.TOPIC_STATE_TRACK
                    elif self.current_app_state == config.STATE_IDLE: current_state_topic_str_feedback = config.TOPIC_STATE_IDLE
                    if current_state_topic_str_feedback: self.state_feedback_pub.publish(String(data=current_state_topic_str_feedback))
        
        elif target_internal_state == config.STATE_TRACKING_TARGET:
            if self.current_app_state == config.STATE_IDLE:
                esh.initiate_tracking_sequence(self) 
            elif self.current_app_state == config.STATE_ACQUIRING_TARGET: # Cannot go from ACQUIRING directly to TRACK via command
                rospy.logwarn(f"Cannot transition to TRACK from ACQUIRING via command. Acquisition must complete first, which will then transition to IDLE (keeping enrollment). Then send TRACK command.")
                if self.state_feedback_pub: self.state_feedback_pub.publish(String(data=config.TOPIC_STATE_ACQUIRE)) 
            else: 
                 rospy.logwarn(f"Cannot transition to TRACK from current state '{self.current_app_state}'. Must be IDLE with an enrolled target.")


    def initialize_reid_system_components(self):
        if config.PRINT_STATEMENTS:
            rospy.loginfo("Initializing Re-ID components...")
        active_extractors = {}
        self.reid_module = ReIDSystem({}, config.MODALITY_WEIGHTS, config.REID_THRESHOLD)

        if config.MODALITY_WEIGHTS.get("RGB", 0) > 0:
            try:
                rgb_extractor = RGBFeatureExtractor(model_name=config.RGB_EXTRACTOR_MODEL_NAME, model_path=None, device=config.DEVICE)
                if not isinstance(rgb_extractor.model, str) or "NO_MODEL_LOADED_BY_BASE" not in rgb_extractor.model: 
                    active_extractors["RGB"] = rgb_extractor
                    if config.PRINT_STATEMENTS:
                        rospy.loginfo("RGB Feature Extractor initialized.")
                else: rospy.logwarn("RGB Feature Extractor base model placeholder returned. RGB features may not work.")
            except Exception as e: rospy.logerr(f"Failed to init RGBFeatureExtractor: {e}. RGB features disabled for ReID.")
        
        if config.MODALITY_WEIGHTS.get("Depth", 0) > 0:
            try:
                depth_extractor = DepthFeatureExtractor(model_name=config.DEPTH_EXTRACTOR_MODEL_NAME, model_path=None, device=config.DEVICE)
                if not isinstance(depth_extractor.model, str) or "NO_MODEL_LOADED_BY_BASE" not in depth_extractor.model:
                    active_extractors["Depth"] = depth_extractor
                    if config.PRINT_STATEMENTS:
                        rospy.loginfo("Depth Feature Extractor initialized.")
                else: 
                    if config.PRINT_STATEMENTS:
                        rospy.logwarn("Depth Feature Extractor base model placeholder returned. Depth features may not work.")
            except Exception as e: rospy.logerr(f"Failed to init DepthFeatureExtractor: {e}. Depth features disabled for ReID.")

        skeleton_modalities_active = config.MODALITY_WEIGHTS.get("Skeleton", 0) > 0 or config.MODALITY_WEIGHTS.get("ForearmColor", 0) > 0
        if skeleton_modalities_active:
            try:
                self.skeleton_extractor_instance = SkeletonFeatureExtractor(
                    device=config.DEVICE,
                    mp_static_image_mode=config.MP_STATIC_IMAGE_MODE,
                    mp_model_complexity=config.MP_MODEL_COMPLEXITY,
                    mp_min_detection_confidence=config.MP_MIN_DETECTION_CONFIDENCE,
                    mp_min_tracking_confidence=config.MP_MIN_TRACKING_CONFIDENCE
                )
                if config.PRINT_STATEMENTS:
                    rospy.loginfo("SkeletonFeatureExtractor (MediaPipe Pose) initialized.")
                if config.MODALITY_WEIGHTS.get("Skeleton", 0) > 0 : 
                     active_extractors["Skeleton"] = self.skeleton_extractor_instance
            except Exception as e: 
                self.skeleton_extractor_instance = None
                rospy.logerr(f"Error initializing SkeletonFeatureExtractor: {e}. Skeleton and ForearmColor features might be affected.")

        if config.MODALITY_WEIGHTS.get("FaceRecognition", 0) > 0:
            try:
                face_extractor = FaceRecognitionFeatureExtractor()
                if face_extractor.model == "FACE_RECOGNITION_DLIB_INTERNAL": 
                    active_extractors["FaceRecognition"] = face_extractor
                    if config.PRINT_STATEMENTS:
                        rospy.loginfo("FaceRecognition Feature Extractor initialized.")
                else: rospy.logwarn("FaceRecognition Feature Extractor model not correctly identified. Face features may not work.")
            except Exception as e: rospy.logerr(f"Failed to init FaceRecognitionFeatureExtractor: {e}. Face features disabled.")

        if config.MODALITY_WEIGHTS.get("ForearmColor", 0) > 0:
            if not self.skeleton_extractor_instance: 
                rospy.logwarn("ForearmColor modality active, but SkeletonFeatureExtractor (dependency) failed to initialize. ForearmColor features disabled.")
            else:
                try:
                    forearm_color_extractor = ForearmColorFeatureExtractor()
                    if forearm_color_extractor.model == "ForearmColor": 
                        active_extractors["ForearmColor"] = forearm_color_extractor
                        if config.PRINT_STATEMENTS:
                            rospy.loginfo("ForearmColor Feature Extractor initialized.")
                    else: rospy.logwarn("ForearmColor Feature Extractor model not correctly identified. ForearmColor features may not work.")
                except Exception as e: rospy.logerr(f"Failed to init ForearmColorFeatureExtractor: {e}. ForearmColor features disabled.")
        
        if not active_extractors: rospy.logwarn("Re-ID System: No modalities successfully initialized. Re-identification will not function.")
        else:
            if config.PRINT_STATEMENTS:
                rospy.loginfo(f"Re-ID System: Finalizing with active extractors: {list(active_extractors.keys())}")
            self.reid_module.feature_extractors = active_extractors
            self.reid_module.target_features = {mod_name: [] for mod_name in active_extractors.keys()}
            if config.PRINT_STATEMENTS:
                rospy.loginfo("Re-ID System component fully initialized with active extractors.")


    def camera_info_callback(self, msg):
        if self.camera_info is None: 
            self.camera_info = msg
            if msg.K and len(msg.K) >=6: 
                self.fx, self.fy, self.cx, self.cy = msg.K[0], msg.K[4], msg.K[2], msg.K[5]
                self.camera_optical_frame_id = msg.header.frame_id
                if config.PRINT_STATEMENTS:
                    rospy.loginfo(f"Camera intrinsics received. fx:{self.fx}, fy:{self.fy}, cx:{self.cx}, cy:{self.cy}. Optical Frame: {self.camera_optical_frame_id}")
                self.camera_info_sub.unregister() 
            else:
                rospy.logwarn("Received CameraInfo does not contain a valid K matrix (expected 9 elements). Retrying...")
                self.camera_info = None 


    def color_image_callback(self, data):
        try:
            self.color_image = self.bridge.imgmsg_to_cv2(data, "bgr8")
            self.new_color_frame_flag = True
        except CvBridgeError as e: rospy.logerr(f"CvBridge Error (Color): {e}")
        except Exception as e: rospy.logerr(f"Error in color_image_callback: {e}")


    def depth_image_callback(self, data):
        try:
            self.raw_depth_image = self.bridge.imgmsg_to_cv2(data, desired_encoding="passthrough")
            if self.raw_depth_image.dtype != np.uint16:
                rospy.logwarn_throttle(10, f"Depth image received with dtype {self.raw_depth_image.dtype}, expected uint16. This might cause issues.")
            self.new_depth_frame_flag = True
            if config.DISPLAY_DEPTH_VIDEO and config.DEPTH_WINDOW_NAME:
                if self.raw_depth_image is not None:
                    clipped_depth = np.clip(self.raw_depth_image, 0, 8000) 
                    depth_norm_display = cv2.normalize(clipped_depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                    self.display_depth_image = cv2.applyColorMap(depth_norm_display, cv2.COLORMAP_JET)
                else:
                    self.display_depth_image = None 
        except CvBridgeError as e: rospy.logerr(f"CvBridge Error (Depth): {e}")
        except Exception as e: rospy.logerr(f"Error in depth_image_callback: {e}")


    def get_median_depth_in_box_mm(self, box_coords):
        return vision_utils.get_median_depth_in_box_mm(self.raw_depth_image, box_coords)

    def deproject_pixel_to_point_m(self, pixel_x, pixel_y, depth_mm):
        if not all([self.fx, self.fy, self.cx, self.cy]): 
            rospy.logwarn_throttle(5,"Deprojection skipped: Camera intrinsics not yet available.")
            return None, None, None
        return vision_utils.deproject_pixel_to_point_m(self.fx, self.fy, self.cx, self.cy, pixel_x, pixel_y, depth_mm)

    def _match_yolo_to_face(self, yolo_box, frame_face_locations_scaled, frame_face_encodings, scale_factor):
        return vision_utils.match_yolo_to_face(yolo_box, frame_face_locations_scaled, frame_face_encodings, scale_factor, logger=rospy)

    def _prepare_modality_inputs(self, rgb_frame_full, raw_depth_frame_full, yolo_person_box,
                                 frame_face_locations_scaled, frame_face_encodings, face_scale_factor):
        x1_orig, y1_orig, x2_orig, y2_orig = map(int, yolo_person_box)
        h_rgb_full, w_rgb_full = rgb_frame_full.shape[:2]
        pc_x1, pc_y1 = max(0, x1_orig), max(0, y1_orig)
        pc_x2, pc_y2 = min(w_rgb_full, x2_orig), min(h_rgb_full, y2_orig)
        
        modality_inputs = {}
        rgb_person_crop = None
        if pc_x1 < pc_x2 and pc_y1 < pc_y2: 
            rgb_person_crop = rgb_frame_full[pc_y1:pc_y2, pc_x1:pc_x2]
        else:
            if config.PRINT_STATEMENTS: 
                rospy.logwarn(f"Invalid RGB crop dimensions for box {yolo_person_box}. Skipping modality input prep.")
            return {} 

        raw_depth_person_crop = None
        if raw_depth_frame_full is not None:
            pdc_x1,pdc_y1,pdc_x2,pdc_y2 = pc_x1, pc_y1, pc_x2, pc_y2 
            if pdc_x1 < pdc_x2 and pdc_y1 < pdc_y2: 
                 raw_depth_person_crop = raw_depth_frame_full[pdc_y1:pdc_y2, pdc_x1:pdc_x2]

        if self.reid_module and "RGB" in self.reid_module.feature_extractors and \
           config.MODALITY_WEIGHTS.get("RGB",0)>0 and rgb_person_crop is not None and rgb_person_crop.size > 0:
            modality_inputs["RGB"] = rgb_person_crop
        
        if self.reid_module and "Depth" in self.reid_module.feature_extractors and \
           config.MODALITY_WEIGHTS.get("Depth",0)>0 and raw_depth_person_crop is not None and raw_depth_person_crop.size > 0:
            modality_inputs["Depth"] = raw_depth_person_crop

        computed_skeleton_joints_dict = None
        skeleton_needed = (self.reid_module and "Skeleton" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("Skeleton",0)>0) or \
                          (self.reid_module and "ForearmColor" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("ForearmColor",0)>0)
        
        if self.skeleton_extractor_instance and skeleton_needed and rgb_person_crop is not None and rgb_person_crop.size > 0:
            computed_skeleton_joints_dict = self.skeleton_extractor_instance.get_joints(rgb_person_crop)

        if self.reid_module and "Skeleton" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("Skeleton",0)>0:
            if computed_skeleton_joints_dict: 
                modality_inputs["Skeleton"] = computed_skeleton_joints_dict
        
        if self.reid_module and "ForearmColor" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("ForearmColor",0)>0:
            if computed_skeleton_joints_dict and rgb_person_crop is not None and rgb_person_crop.size > 0:
                modality_inputs["ForearmColor"] = {
                    "skeleton_joints_dict": computed_skeleton_joints_dict,
                    "rgb_image": rgb_person_crop 
                }
        
        if self.reid_module and "FaceRecognition" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("FaceRecognition",0)>0:
            current_face_scale_factor = face_scale_factor if face_scale_factor != 0 else 1.0 
            modality_inputs["FaceRecognition"] = self._match_yolo_to_face(yolo_person_box, frame_face_locations_scaled, frame_face_encodings, current_face_scale_factor)
        
        return modality_inputs


    def run(self):
        loop_fps = self.recording_fps if self.record_feed and self.recording_fps > 0 else 30
        rate = rospy.Rate(loop_fps)
        
        face_locations_scaled, face_encodings, current_face_scale_factor = [], [], 1.0

        while not rospy.is_shutdown():
            if self.camera_info is None or not (self.new_color_frame_flag and self.new_depth_frame_flag):
                if config.DISPLAY_RGB_VIDEO and self.color_image is not None :
                    temp_display = self.color_image.copy() 
                    wait_msg_parts = []
                    if self.camera_info is None: wait_msg_parts.append("CamInfo")
                    if not self.new_color_frame_flag: wait_msg_parts.append("Color")
                    if not self.new_depth_frame_flag: wait_msg_parts.append("Depth")
                    wait_msg = f"Waiting for: {', '.join(wait_msg_parts)}" if wait_msg_parts else "Waiting for data..."
                    cv2.putText(temp_display, wait_msg, (10,50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255),2)
                    cv2.imshow(self.window_name, temp_display)
                    key = cv2.waitKey(1) & 0xFF
                    if key != 255: esh.handle_key_press(self, key)
                elif self.camera_info is None: 
                     rospy.loginfo_throttle(5, "Waiting for camera_info...")
                else: 
                     rospy.loginfo_throttle(5, "Waiting for new color/depth frames...")
                rate.sleep()
                continue

            current_color_frame = self.color_image.copy()
            current_raw_depth = self.raw_depth_image.copy() 
            self.new_color_frame_flag = self.new_depth_frame_flag = False 

            display_frame = current_color_frame.copy() if config.DISPLAY_RGB_VIDEO or self.record_feed else None

            if self.record_feed and self.video_writer is None and display_frame is not None:
                try:
                    results_dir = config.RESULTS_FOLDER; os.makedirs(results_dir, exist_ok=True)
                    height, width, _ = display_frame.shape; timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_filename = f"recording_{timestamp}{self.recording_file_extension}"
                    self.output_video_path = os.path.join(results_dir, output_filename)
                    self.video_writer = cv2.VideoWriter(self.output_video_path, self.recording_codec_fourcc, self.recording_fps, (width, height))
                    if not self.video_writer.isOpened(): raise IOError("Cannot open video writer")
                    rospy.loginfo(f"Recording to: {self.output_video_path} at {self.recording_fps} FPS...")
                except Exception as e:
                    rospy.logerr(f"VideoWriter initialization error: {e}. Recording disabled.")
                    self.record_feed = False; self.video_writer = None
            
            face_active = self.reid_module and "FaceRecognition" in self.reid_module.feature_extractors and \
                          config.MODALITY_WEIGHTS.get("FaceRecognition", 0) > 0
            if not face_active: 
                face_locations_scaled, face_encodings, current_face_scale_factor = [], [], 1.0
            else: 
                try:
                    scale = config.FACE_DETECTION_RESIZE_FACTOR
                    current_face_scale_factor = scale if 0 < scale <= 1.0 else 1.0
                    small_frame = cv2.resize(current_color_frame, (0, 0), fx=current_face_scale_factor, fy=current_face_scale_factor) \
                                    if current_face_scale_factor != 1.0 else current_color_frame
                    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB) 
                    face_locations_scaled = face_recognition.face_locations(rgb_small_frame, model=config.FACE_DETECTION_MODEL)
                    if face_locations_scaled: 
                        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations_scaled)
                    else: face_encodings = [] 
                except Exception as e:
                    rospy.logerr(f"Face detection/encoding error: {e}")
                    face_locations_scaled, face_encodings = [], [] 

            detected_persons_this_frame = [] 
            try:
                yolo_preds = self.yolo_model.predict(current_color_frame, conf=self.yolo_confidence, classes=[self.yolo_target_class_id], verbose=False)
                if yolo_preds and yolo_preds[0].boxes: 
                    for box_obj in yolo_preds[0].boxes:
                        x1, y1, x2, y2 = map(int, box_obj.xyxy[0].tolist()); conf = float(box_obj.conf[0])
                        detected_persons_this_frame.append({'box': (x1, y1, x2, y2), 'conf': conf})
                        
                        if display_frame is not None and config.DISPLAY_RGB_VIDEO:
                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 200, 100), 1) 
                            
                            skeleton_draw_active = self.skeleton_extractor_instance and mp_drawing and mp_pose and \
                                                   (config.MODALITY_WEIGHTS.get("Skeleton",0)>0 or config.MODALITY_WEIGHTS.get("ForearmColor",0)>0)
                            if skeleton_draw_active:
                                pc_x1,pc_y1 = max(0,x1), max(0,y1)
                                pc_x2,pc_y2 = min(current_color_frame.shape[1],x2), min(current_color_frame.shape[0],y2)
                                if pc_y1 < pc_y2 and pc_x1 < pc_x2: 
                                    person_crop_for_mp = current_color_frame[pc_y1:pc_y2, pc_x1:pc_x2]
                                    if person_crop_for_mp.size > 0:
                                        joint_data_dict = self.skeleton_extractor_instance.get_joints(person_crop_for_mp)
                                        if joint_data_dict and joint_data_dict.get('mp_pose_landmarks'):
                                            if config.MODALITY_WEIGHTS.get("Skeleton",0)>0:
                                                region_to_draw_on = display_frame[pc_y1:pc_y2, pc_x1:pc_x2] 
                                                mp_drawing.draw_landmarks(region_to_draw_on, joint_data_dict['mp_pose_landmarks'], mp_pose.POSE_CONNECTIONS,
                                                                        mp_drawing.DrawingSpec(color=(0,255,255),thickness=1,circle_radius=1), 
                                                                        mp_drawing.DrawingSpec(color=(255,0,255),thickness=1,circle_radius=1)) 
                                            
                                            if self.reid_module and "ForearmColor" in self.reid_module.feature_extractors and config.MODALITY_WEIGHTS.get("ForearmColor",0)>0:
                                                forearm_extractor = self.reid_module.feature_extractors.get("ForearmColor")
                                                if forearm_extractor: 
                                                    crop_h_mp, crop_w_mp = person_crop_for_mp.shape[:2]
                                                    forearm_corners_relative_to_crop = forearm_extractor.extract_forearm_regions(joint_data_dict, (crop_w_mp, crop_h_mp))
                                                    if forearm_corners_relative_to_crop:
                                                        for key_fc, corners_rel in forearm_corners_relative_to_crop.items():
                                                            if corners_rel is not None and isinstance(corners_rel, np.ndarray):
                                                                abs_corners = corners_rel + np.array([pc_x1, pc_y1]) 
                                                                color_fc = (255,165,0) if "left" in key_fc else (0,165,255) 
                                                                cv2.polylines(display_frame, [abs_corners.astype(np.int32)], True, color_fc, 2)
            except Exception as e:
                rospy.logerr(f"YOLO prediction or subsequent debug drawing error: {e}")

            if self.current_app_state == config.STATE_IDLE:
                esh.handle_idle_state(self, display_frame)
            elif self.current_app_state == config.STATE_ACQUIRING_TARGET:
                esh.handle_acquisition_state(self, display_frame, detected_persons_this_frame,
                                             current_color_frame, current_raw_depth, 
                                             face_locations_scaled, face_encodings, current_face_scale_factor)
            elif self.current_app_state == config.STATE_TRACKING_TARGET:
                esh.handle_tracking_state(self, display_frame, detected_persons_this_frame,
                                          current_color_frame, current_raw_depth, 
                                          face_locations_scaled, face_encodings, current_face_scale_factor)

            if self.record_feed and self.video_writer and self.video_writer.isOpened() and display_frame is not None:
                try: self.video_writer.write(display_frame)
                except Exception as e: rospy.logerr(f"Video write error: {e}")
            
            if config.DISPLAY_RGB_VIDEO and display_frame is not None:
                control_info_text = "q:Quit"
                if config.USE_TOPIC_CONTROL:
                    control_info_text += f" | Topic: {config.STATE_CONTROL_TOPIC}"
                else: 
                    control_info_text += " | SPACE:Acquire/Stop | r:Reset"
                cv2.putText(display_frame, control_info_text, (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                
                cv2.imshow(self.window_name, display_frame)
                if config.DISPLAY_DEPTH_VIDEO and self.display_depth_image is not None and config.DEPTH_WINDOW_NAME:
                    cv2.imshow(config.DEPTH_WINDOW_NAME, self.display_depth_image)
            
            key = cv2.waitKey(1) & 0xFF
            if key != 255: 
                esh.handle_key_press(self, key)

            rate.sleep()
        
        if config.PRINT_STATEMENTS:
            rospy.loginfo("Shutting down tracker node...")
        if config.DISPLAY_RGB_VIDEO or config.DISPLAY_DEPTH_VIDEO: 
            cv2.destroyAllWindows()
        if self.video_writer and self.video_writer.isOpened(): self.video_writer.release()
        
        if self.skeleton_extractor_instance and hasattr(self.skeleton_extractor_instance, 'pose_estimator'):
            if self.skeleton_extractor_instance.pose_estimator is not None:
                try:
                    close_method = getattr(self.skeleton_extractor_instance.pose_estimator, 'close', None)
                    if callable(close_method): 
                        close_method()
                        if config.PRINT_STATEMENTS:
                            rospy.loginfo("MediaPipe Pose estimator closed.")
                except Exception as e: 
                    rospy.logerr(f"Error closing MediaPipe Pose estimator: {e}")
        
        try:
            if hasattr(self, 'color_sub') and self.color_sub: self.color_sub.unregister()
            if hasattr(self, 'depth_sub') and self.depth_sub: self.depth_sub.unregister()
            if hasattr(self, 'depth_sub_backup') and self.depth_sub_backup: self.depth_sub_backup.unregister()
            if hasattr(self, 'camera_info_sub') and self.camera_info_sub and self.camera_info_sub.impl is not None : 
                 try: self.camera_info_sub.unregister()
                 except Exception: pass 
            if hasattr(self, 'state_control_sub') and self.state_control_sub: self.state_control_sub.unregister()
        except Exception as e: rospy.logerr(f"Error unregistering subscribers: {e}")
        
        if config.PRINT_STATEMENTS:
            rospy.loginfo("Shutdown complete.")


if __name__ == '__main__':
    filtered_args = rospy.myargv(argv=sys.argv) 
    parser = argparse.ArgumentParser(description="Multi-Modal Tracker ROS Node")
    parser.add_argument('--yolo_model', type=str, default=config.YOLO_MODEL_PATH_DEFAULT, help="Path to YOLO model.")
    parser.add_argument('--yolo_conf', type=float, default=config.YOLO_PERSON_CONFIDENCE_THRESHOLD_DEFAULT, help="YOLO detection confidence threshold.")
    parser.add_argument('--acq_duration', type=float, default=config.ACQUISITION_DURATION_SEC_DEFAULT, help="Duration for target acquisition in seconds.")
    
    args = parser.parse_args(filtered_args[1:]) 
    
    tracker_app = None
    try:
        tracker_app = MultiModalRealsenseTracker(args.yolo_model, args.yolo_conf, args.acq_duration)
        tracker_app.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("ROS interrupt signal received. Shutting down.")
    except Exception as e:
        rospy.logerr(f"An unexpected error occurred in main execution: {e}")
        rospy.logerr(traceback.format_exc()) 
    finally:
        if config.PRINT_STATEMENTS:
            rospy.loginfo("Final cleanup in main execution block.")

        if tracker_app and hasattr(tracker_app, 'video_writer') and \
           tracker_app.video_writer and tracker_app.video_writer.isOpened():
            rospy.loginfo("Releasing video writer in final cleanup.")
            tracker_app.video_writer.release()
