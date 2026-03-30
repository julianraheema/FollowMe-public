# feature_extractors.py
import numpy as np
import cv2
import torch
import torchvision.transforms as T
from torchreid.utils import FeatureExtractor as TorchReidFeatureExtractor # Rename to avoid clash
import mediapipe as mp
import config

# --- Base Class ---
class ModalityFeatureExtractor:
    """Base class for feature extractors."""
    def __init__(self, model_path=None, model_name=""):
        """Initializes the base feature extractor."""
        self.modality_name_for_logging = model_name
        # self.model will be loaded by the derived class or this base class's load_model
        self.model = self.load_model(model_path)
        if config.PRINT_STATEMENTS:
            model_status = type(self.model).__name__ if self.model else "None"
            print(f"  [FE Log] {self.modality_name_for_logging} Feature Extractor Base Initialized. Model status: {model_status}")

    def load_model(self, model_path):
        """Loads the model for the feature extractor.
        Placeholder model loader. Derived classes MUST override this
        to load actual models or return a specific identifier if no model is used.
        Returning None or a generic string might cause issues later.
        """
        if config.PRINT_STATEMENTS:
                print(f"  [FE Log] Base load_model called for {self.modality_name_for_logging}. Path: {model_path}. Returning placeholder.")
        # Return a specific placeholder indicating no real model is loaded by base
        return f"NO_MODEL_LOADED_BY_BASE_{self.modality_name_for_logging}"

    def preprocess(self, data_input, is_enrollment_phase=False):
        """Preprocesses the input data."""
        """Placeholder preprocess. Should be overridden if needed."""
        return data_input

    def extract_features(self, data_input, is_enrollment_phase=False):
        """Extracts features from the input data."""
        """
        Base feature extraction. MUST be overridden by subclasses that load actual models.
        """
        feature_size_map = {
            "RGB": 512,
            "Depth": 512,
            "Skeleton": 61, 
            "FaceRecognition": 128,
            "ForearmColor": 60, 
            "Thermal": 256 
        }
        default_feature_size = feature_size_map.get(self.modality_name_for_logging, 256)

        if config.PRINT_STATEMENTS:
            input_type = type(data_input).__name__ if data_input is not None else "None"
            print(f"  [FE Log] WARNING: Base extract_features called for {self.modality_name_for_logging} (Input type: {input_type}). This likely means the subclass didn't override it correctly or handle its input. Returning zeros.")

        return np.zeros((1, default_feature_size), dtype=np.float32)


# --- RGB Feature Extractor ---
class RGBFeatureExtractor(ModalityFeatureExtractor):
    """Extracts features from RGB images."""

    def __init__(self, model_name='osnet_x1_0', model_path=None, device='cuda'):
        """Initializes the RGB feature extractor."""
        self.torchreid_model_name = model_name
        self.torchreid_model_path = model_path
        if device == 'cuda' and torch.cuda.is_available():
            self.device = 'cuda'
        else:
            if device == 'cuda': 
                if config.PRINT_STATEMENTS: 
                    print("  [FE Log] WARNING: CUDA selected for RGB but not available. Falling back to CPU.")
            self.device = 'cpu'
        super().__init__(model_path=self.torchreid_model_path, model_name="RGB")
        self.transform = None
        if isinstance(self.model, TorchReidFeatureExtractor): 
            self._build_preprocess()
        elif config.PRINT_STATEMENTS:
                print(f"  [FE Log] RGB Model is not a TorchReidFeatureExtractor (Type: {type(self.model).__name__}). Preprocessing transform not built.")

    def load_model(self, model_path_weights):
        """Loads the RGB model."""
        try:
            extractor = TorchReidFeatureExtractor(
                model_name=self.torchreid_model_name,
                model_path=model_path_weights,
                device=self.device
            )
            if config.PRINT_STATEMENTS:
                print(f"  [FE Log] TorchReID RGB Extractor ({self.torchreid_model_name}) loaded successfully on {self.device}.")
            return extractor
        except Exception as e:
            print(f"ERROR: Failed loading TorchReID model {self.torchreid_model_name} for RGB: {e}")
            return super().load_model(model_path_weights)

    def _build_preprocess(self):
        """Builds the preprocessing transform for RGB images."""
        self.transform = T.Compose([
            T.ToPILImage(), 
            T.Resize((256, 128)), 
            T.ToTensor(), 
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        if config.PRINT_STATEMENTS:
            print(f"  [FE Log] RGB preprocessing transform built for TorchReID on {self.device}.")

    def preprocess(self, rgb_image_crop_bgr, is_enrollment_phase=False):
        """Preprocesses the RGB image crop."""
        if not isinstance(self.model, TorchReidFeatureExtractor) or self.transform is None:
                if config.PRINT_STATEMENTS: 
                    print(f"  [FE Log] RGB Preprocessing skipped: Model not loaded or transform not built.")
                return None
        if rgb_image_crop_bgr is None or rgb_image_crop_bgr.size == 0:
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] RGB Preprocessing skipped: Input image is None or empty.")
            return None
        try:
            rgb_image_crop_rgb = cv2.cvtColor(rgb_image_crop_bgr, cv2.COLOR_BGR2RGB)
            return self.transform(rgb_image_crop_rgb)
        except Exception as e:
            print(f"ERROR during RGB preprocessing: {e}. Crop shape: {rgb_image_crop_bgr.shape}")
            return None

    def extract_features(self, rgb_image_crop_bgr, is_enrollment_phase=False):
        """Extracts features from the RGB image crop."""
        default_feature_size = 512 
        if not isinstance(self.model, TorchReidFeatureExtractor):
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] RGB Feature extraction skipped: Incorrect model type ({type(self.model).__name__}). Returning zeros.")
            return super().extract_features(rgb_image_crop_bgr, is_enrollment_phase)
        preprocessed_tensor = self.preprocess(rgb_image_crop_bgr, is_enrollment_phase)
        if preprocessed_tensor is None:
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] RGB Feature extraction skipped: Preprocessing failed. Returning zeros.")
            return np.zeros((1, default_feature_size), dtype=np.float32)
        input_tensor = preprocessed_tensor.unsqueeze(0).to(self.device)
        try:
            with torch.no_grad(): 
                features = self.model(input_tensor) 
            return features.cpu().numpy()
        except Exception as e:
            print(f"ERROR during TorchReID RGB feature extraction: {e}")
            return np.zeros((1, default_feature_size), dtype=np.float32)


# --- Depth Feature Extractor ---
class DepthFeatureExtractor(ModalityFeatureExtractor):
    """Extracts features from depth images."""

    def __init__(self, model_name='osnet_x1_0', model_path=None, device='cpu'):
        """Initializes the depth feature extractor."""
        self.torchreid_model_name = model_name
        self.torchreid_model_path = model_path
        if device == 'cuda' and torch.cuda.is_available():
            self.device = 'cuda'
        else:
            if device == 'cuda':
                if config.PRINT_STATEMENTS: 
                    print("  [FE Log] WARNING: CUDA selected for Depth but not available. Falling back to CPU.")
            self.device = 'cpu'
        super().__init__(model_path=self.torchreid_model_path, model_name="Depth")
        self.transform = None
        if isinstance(self.model, TorchReidFeatureExtractor):
            self._build_preprocess_for_depth_cnn() 
        elif config.PRINT_STATEMENTS:
                print(f"  [FE Log] Depth Model is not a TorchReidFeatureExtractor (Type: {type(self.model).__name__}). Preprocessing transform not built.")

    def load_model(self, model_path_weights):
        """Loads the depth model."""
        try:
            extractor = TorchReidFeatureExtractor(
                model_name=self.torchreid_model_name,
                model_path=model_path_weights,
                device=self.device
            )
            if config.PRINT_STATEMENTS:
                print(f"  [FE Log] TorchReID model ({self.torchreid_model_name}) loaded for Depth features on {self.device}.")
            return extractor
        except Exception as e:
            print(f"ERROR loading TorchReID model {self.torchreid_model_name} for Depth: {e}")
            return super().load_model(model_path_weights)

    def _build_preprocess_for_depth_cnn(self):
        """Builds the preprocessing transform for depth images."""
        self.transform = T.Compose([
            T.ToPILImage(),
            T.Resize((256, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        if config.PRINT_STATEMENTS:
            print(f"  [FE Log] Depth preprocessing transform (RGB-style) built for {self.device}.")

    def preprocess(self, depth_crop_image_raw, is_enrollment_phase=False):
        """Preprocesses the depth image crop."""
        if not isinstance(self.model, TorchReidFeatureExtractor) or self.transform is None:
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] Depth Preprocessing skipped: Model not loaded or transform not built.")
            return None
        if depth_crop_image_raw is None or depth_crop_image_raw.size == 0:
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] Depth Preprocessing skipped: Input image is None or empty.")
            return None
        try:
            min_depth_mm = 500.0 
            max_depth_mm = 8000.0 
            valid_mask = depth_crop_image_raw > 0
            normalized_depth = np.zeros_like(depth_crop_image_raw, dtype=np.float32)
            if np.any(valid_mask):
                temp_depth = depth_crop_image_raw[valid_mask].astype(np.float32)
                temp_depth = np.clip(temp_depth, min_depth_mm, max_depth_mm)
                min_val = np.min(temp_depth) 
                max_val = np.max(temp_depth) 
                if max_val - min_val > 1e-6: 
                    normalized_depth_values = 255 * (temp_depth - min_val) / (max_val - min_val)
                else: 
                    normalized_depth_values = np.full_like(temp_depth, 128)
                normalized_depth[valid_mask] = normalized_depth_values
            depth_8u = normalized_depth.astype(np.uint8)
            depth_3_channel_bgr = cv2.cvtColor(depth_8u, cv2.COLOR_GRAY2BGR)
            return self.transform(depth_3_channel_bgr)
        except Exception as e:
            print(f"ERROR during Depth preprocessing: {e}. Crop shape: {depth_crop_image_raw.shape if hasattr(depth_crop_image_raw, 'shape') else 'N/A'}")
            return None

    def extract_features(self, raw_depth_crop, is_enrollment_phase=False):
        """Extracts features from the depth image crop."""
        default_feature_size = 512 
        if not isinstance(self.model, TorchReidFeatureExtractor):
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] Depth Feature extraction skipped: Incorrect model type ({type(self.model).__name__}). Returning zeros.")
            return super().extract_features(raw_depth_crop, is_enrollment_phase)
        preprocessed_tensor = self.preprocess(raw_depth_crop, is_enrollment_phase)
        if preprocessed_tensor is None:
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] Depth Feature extraction skipped: Preprocessing failed. Returning zeros.")
            return np.zeros((1, default_feature_size), dtype=np.float32)
        input_tensor = preprocessed_tensor.unsqueeze(0).to(self.device)
        try:
            with torch.no_grad():
                features = self.model(input_tensor)
            return features.cpu().numpy()
        except Exception as e:
            print(f"ERROR during Depth feature extraction with TorchReID model: {e}")
            return np.zeros((1, default_feature_size), dtype=np.float32)

# --- Skeleton Feature Extractor ---
class SkeletonFeatureExtractor(ModalityFeatureExtractor):
    """
    Extracts detailed structural and proportional features from skeleton data,
    optimized for low camera angles and also considering full body visibility.
    """

    def __init__(self, 
                 device='cpu',  # Device argument is not directly used by MediaPipe Pose CPU version
                 mp_static_image_mode=False, mp_model_complexity=1,
                 mp_min_detection_confidence=0.5, mp_min_tracking_confidence=0.5):
        """Initializes the skeleton feature extractor."""
        self.device = device 
        self.mp_static_image_mode = mp_static_image_mode
        self.mp_model_complexity = mp_model_complexity
        self.mp_min_detection_confidence = mp_min_detection_confidence
        self.mp_min_tracking_confidence = mp_min_tracking_confidence
        self.pose_estimator = self._load_pose_estimator() 
        super().__init__(model_path=None, model_name="SkeletonMediaPipeProportions")
        
        self.expected_feature_size = 61 # 57 body/proportion features + 4 visibility scores

    def _load_pose_estimator(self):
        """Loads the MediaPipe Pose estimator model."""
        try:
            pose = mp.solutions.pose.Pose(
                static_image_mode=self.mp_static_image_mode,
                model_complexity=self.mp_model_complexity,
                min_detection_confidence=self.mp_min_detection_confidence,
                min_tracking_confidence=self.mp_min_tracking_confidence
            )
            if config.PRINT_STATEMENTS:
                print(f"  [FE Log] MediaPipe Pose Estimator loaded: static_mode={self.mp_static_image_mode}, "
                      f"complexity={self.mp_model_complexity}, det_conf={self.mp_min_detection_confidence}, "
                      f"track_conf={self.mp_min_tracking_confidence}")
            return pose
        except Exception as e:
            print(f"ERROR: Failed loading MediaPipe Pose model: {e}")
            raise RuntimeError(f"Could not initialize MediaPipe Pose: {e}") from e

    def load_model(self, skeleton_feature_model_path):
        """
        This method is part of the base class structure. 
        For this extractor, the primary "model" is MediaPipe Pose, loaded in __init__.
        """
        if skeleton_feature_model_path:
            if config.PRINT_STATEMENTS:
                print(f"  [FE Log] Conceptual skeleton feature model path provided: {skeleton_feature_model_path}. "
                      "Actual loading for a secondary model not implemented here.")
            self.secondary_model_path = skeleton_feature_model_path 
            return "CONCEPTUAL_SKELETON_FEATURE_MODEL_" + skeleton_feature_model_path
        else:
            if config.PRINT_STATEMENTS:
                print(f"  [FE Log] No secondary skeleton feature model path provided.")
            self.secondary_model_path = None
            return "MEDIAPIPE_POSE_PRIMARY_MODEL"


    def get_joints(self, rgb_crop_image_for_pose):
        """
        Extracts joint landmarks from an RGB image using MediaPipe Pose.
        """
        if self.pose_estimator is None: 
            print("ERROR: MediaPipe Pose estimator not initialized in get_joints.")
            return None
        if rgb_crop_image_for_pose is None or rgb_crop_image_for_pose.size == 0:
            return None
        
        try:
            image_rgb = cv2.cvtColor(rgb_crop_image_for_pose, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = self.pose_estimator.process(image_rgb)
            image_rgb.flags.writeable = True 

            if results.pose_landmarks:
                landmarks_np = []
                for landmark in results.pose_landmarks.landmark:
                    landmarks_np.append([landmark.x, landmark.y, landmark.visibility])
                return {
                    'landmarks_array': np.array(landmarks_np, dtype=np.float32), 
                    'mp_pose_landmarks': results.pose_landmarks 
                }
            else:
                return None
        except Exception as e:
            print(f"ERROR during MediaPipe joint extraction: {e}")
            return None

    def _extract_detailed_structural_features(self, joints_xyv_array_normalized):
        """
        Extracts pose-invariant body proportion and structural features from MediaPipe landmarks.
        Optimized by pre-allocating the feature array.
        """
        if joints_xyv_array_normalized is None or joints_xyv_array_normalized.shape != (33, 3):
            return np.zeros(self.expected_feature_size, dtype=np.float32)
        
        # Pre-allocate feature array
        # 57 body/proportion features + 4 visibility scores = 61
        features_arr = np.zeros(self.expected_feature_size, dtype=np.float32)
        idx = 0 # Current index for feature assignment

        landmarks = joints_xyv_array_normalized[:, :2]
        visibility = joints_xyv_array_normalized[:, 2]
        
        nose = landmarks[0]; left_eye = landmarks[1]; right_eye = landmarks[2]
        left_ear = landmarks[7]; right_ear = landmarks[8]
        left_shoulder = landmarks[11]; right_shoulder = landmarks[12]
        left_elbow = landmarks[13]; right_elbow = landmarks[14]
        left_wrist = landmarks[15]; right_wrist = landmarks[16]
        left_hip = landmarks[23]; right_hip = landmarks[24]
        left_knee = landmarks[25]; right_knee = landmarks[26]
        left_ankle = landmarks[27]; right_ankle = landmarks[28]
        left_heel = landmarks[29]; right_heel = landmarks[30]
        left_foot_index = landmarks[31]; right_foot_index = landmarks[32]
        
        shoulder_center = (left_shoulder + right_shoulder) / 2
        hip_center = (left_hip + right_hip) / 2
        knee_center = (left_knee + right_knee) / 2
        ankle_center = (left_ankle + right_ankle) / 2 # Not used directly in features
        head_center = (left_eye + right_eye) / 2
        
        shoulder_width = np.linalg.norm(left_shoulder - right_shoulder)
        hip_width = np.linalg.norm(left_hip - right_hip)
        knee_width = np.linalg.norm(left_knee - right_knee)
        ankle_width = np.linalg.norm(left_ankle - right_ankle)
        
        torso_height = np.linalg.norm(shoulder_center - hip_center)
        hip_to_knee_height = np.linalg.norm(hip_center - knee_center)
        knee_to_ankle_height = np.linalg.norm(knee_center - ankle_center)
        total_leg_height = hip_to_knee_height + knee_to_ankle_height
        head_shoulder_dist = np.linalg.norm(head_center - shoulder_center)
        
        left_upper_arm = np.linalg.norm(left_shoulder - left_elbow)
        left_forearm = np.linalg.norm(left_elbow - left_wrist)
        right_upper_arm = np.linalg.norm(right_shoulder - right_elbow)
        right_forearm = np.linalg.norm(right_elbow - right_wrist)
        left_thigh = np.linalg.norm(left_hip - left_knee)
        left_shin = np.linalg.norm(left_knee - left_ankle)
        right_thigh = np.linalg.norm(right_hip - right_knee)
        right_shin = np.linalg.norm(right_knee - right_ankle)
        
        primary_normalizer = total_leg_height if total_leg_height > 1e-6 else torso_height
        
        num_body_features_expected = 57 

        if primary_normalizer > 1e-6:
            # === LOW-ANGLE OPTIMIZED PROPORTIONS === (5 + 2 + 1 + 1 + 3 = 12 features)
            features_arr[idx] = hip_width / primary_normalizer; idx += 1
            features_arr[idx] = knee_width / primary_normalizer; idx += 1
            features_arr[idx] = ankle_width / primary_normalizer; idx += 1
            features_arr[idx] = hip_to_knee_height / primary_normalizer; idx += 1
            features_arr[idx] = knee_to_ankle_height / primary_normalizer; idx += 1
            
            if hip_width > 1e-6:
                features_arr[idx] = knee_width / hip_width; idx += 1
                features_arr[idx] = ankle_width / hip_width; idx += 1
            else: features_arr[idx:idx+2] = 0.0; idx += 2
            
            if knee_width > 1e-6: features_arr[idx] = ankle_width / knee_width; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            
            if knee_to_ankle_height > 1e-6: features_arr[idx] = hip_to_knee_height / knee_to_ankle_height; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            
            if torso_height > 1e-6:
                features_arr[idx] = shoulder_width / primary_normalizer; idx += 1
                features_arr[idx] = torso_height / primary_normalizer; idx += 1
                features_arr[idx] = head_shoulder_dist / primary_normalizer; idx += 1
            else: features_arr[idx:idx+3] = 0.0; idx += 3
            
            # === INDIVIDUAL LIMB SEGMENT LENGTHS === (8 features)
            limb_lengths = [left_thigh, left_shin, right_thigh, right_shin,
                            left_upper_arm, left_forearm, right_upper_arm, right_forearm]
            for length in limb_lengths:
                features_arr[idx] = length / primary_normalizer; idx += 1
            
            # === FOOT AND ANKLE FEATURES === (8 features)
            left_foot_length = np.linalg.norm(left_heel - left_foot_index)
            right_foot_length = np.linalg.norm(right_heel - right_foot_index)
            features_arr[idx] = left_foot_length / primary_normalizer; idx += 1
            features_arr[idx] = right_foot_length / primary_normalizer; idx += 1
            
            left_ankle_heel_dist = np.linalg.norm(left_ankle - left_heel)
            left_ankle_toe_dist = np.linalg.norm(left_ankle - left_foot_index)
            right_ankle_heel_dist = np.linalg.norm(right_ankle - right_heel)
            right_ankle_toe_dist = np.linalg.norm(right_ankle - right_foot_index)
            foot_ankle_dists = [left_ankle_heel_dist, left_ankle_toe_dist, 
                                right_ankle_heel_dist, right_ankle_toe_dist]
            for dist in foot_ankle_dists:
                features_arr[idx] = dist / primary_normalizer; idx += 1

            if left_foot_length > 1e-6: features_arr[idx] = left_ankle_heel_dist / left_foot_length; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            if right_foot_length > 1e-6: features_arr[idx] = right_ankle_heel_dist / right_foot_length; idx += 1
            else: features_arr[idx] = 0.0; idx += 1

            # === STANCE AND GAIT FEATURES === (5 features)
            features_arr[idx] = np.linalg.norm(left_ankle - right_ankle) / primary_normalizer; idx += 1 # foot_separation
            left_hip_ankle_x_offset = (left_hip[0] - left_ankle[0])
            right_hip_ankle_x_offset = (right_hip[0] - right_ankle[0])
            features_arr[idx] = left_hip_ankle_x_offset / primary_normalizer; idx += 1
            features_arr[idx] = right_hip_ankle_x_offset / primary_normalizer; idx += 1
            features_arr[idx] = abs(left_hip_ankle_x_offset) / primary_normalizer; idx += 1
            features_arr[idx] = abs(right_hip_ankle_x_offset) / primary_normalizer; idx += 1

            # === LIMB PROPORTION RATIOS (INTRA-LIMB) === (4 features)
            if left_forearm > 1e-6: features_arr[idx] = left_upper_arm / left_forearm; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            if right_forearm > 1e-6: features_arr[idx] = right_upper_arm / right_forearm; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            if left_shin > 1e-6: features_arr[idx] = left_thigh / left_shin; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            if right_shin > 1e-6: features_arr[idx] = right_thigh / right_shin; idx += 1
            else: features_arr[idx] = 0.0; idx += 1

            # === SYMMETRY FEATURES === (4 features)
            if right_upper_arm > 1e-6: features_arr[idx] = left_upper_arm / right_upper_arm; idx += 1
            else: features_arr[idx] = (1.0 if left_upper_arm < 1e-6 else 0.0); idx += 1
            if right_forearm > 1e-6: features_arr[idx] = left_forearm / right_forearm; idx += 1
            else: features_arr[idx] = (1.0 if left_forearm < 1e-6 else 0.0); idx += 1
            if right_thigh > 1e-6: features_arr[idx] = left_thigh / right_thigh; idx += 1
            else: features_arr[idx] = (1.0 if left_thigh < 1e-6 else 0.0); idx += 1
            if right_shin > 1e-6: features_arr[idx] = left_shin / right_shin; idx += 1
            else: features_arr[idx] = (1.0 if left_shin < 1e-6 else 0.0); idx += 1

            # === JOINT ANGLES === (5 features)
            v_pairs = [
                (left_hip - left_knee, left_ankle - left_knee), (right_hip - right_knee, right_ankle - right_knee),
                (left_knee - left_hip, right_knee - right_hip), 
                (left_shoulder - left_elbow, left_wrist - left_elbow),
                (right_shoulder - right_elbow, right_wrist - right_elbow)
            ]
            for v1, v2 in v_pairs:
                norm_prod = np.linalg.norm(v1) * np.linalg.norm(v2)
                if norm_prod > 1e-6: features_arr[idx] = np.clip(np.dot(v1, v2) / norm_prod, -1, 1); idx += 1
                else: features_arr[idx] = 0.0; idx += 1
            
            # === RELATIVE POSITION AND SLOPE FEATURES === (4 features)
            if torso_height > 1e-6:
                features_arr[idx] = (head_center[0] - shoulder_center[0]) / torso_height; idx += 1
                features_arr[idx] = (head_center[0] - hip_center[0]) / torso_height; idx += 1
            else:
                features_arr[idx] = (head_center[0] - shoulder_center[0]) / primary_normalizer; idx += 1
                features_arr[idx] = (head_center[0] - hip_center[0]) / primary_normalizer; idx += 1
            if shoulder_width > 1e-6: features_arr[idx] = (left_shoulder[1] - right_shoulder[1]) / shoulder_width; idx += 1
            else: features_arr[idx] = 0.0; idx += 1
            if hip_width > 1e-6: features_arr[idx] = (left_hip[1] - right_hip[1]) / hip_width; idx += 1
            else: features_arr[idx] = 0.0; idx += 1

            # === OVERALL BODY SPAN AND PROPORTION === (2 + 5 = 7 features)
            approx_arm_span = shoulder_width + left_upper_arm + left_forearm + right_upper_arm + right_forearm
            avg_individual_leg_len = (left_thigh + left_shin + right_thigh + right_shin) / 2
            features_arr[idx] = approx_arm_span / primary_normalizer; idx += 1
            features_arr[idx] = avg_individual_leg_len / primary_normalizer; idx += 1
            
            approx_total_height = head_shoulder_dist + torso_height + total_leg_height
            if approx_total_height > 1e-6:
                body_proportions = [total_leg_height / approx_total_height, torso_height / approx_total_height,
                                 approx_arm_span / approx_total_height, shoulder_width / approx_total_height,
                                 hip_width / approx_total_height]
                for prop in body_proportions:
                    features_arr[idx] = prop; idx += 1
            else: features_arr[idx:idx+5] = 0.0; idx += 5
            
            # Sanity check for index against expected body features
            if idx != num_body_features_expected:
                 if config.PRINT_STATEMENTS:
                    print(f"  [FE Log] WARNING: Mismatch in body feature count index. Expected {num_body_features_expected}, got {idx}. This might indicate an issue in feature counting.")
                 # If idx is off, the array might be wrongly sized or populated.
                 # For robustness, ensure idx doesn't exceed array bounds before visibility scores
                 idx = min(idx, num_body_features_expected)


        else: # primary_normalizer is too small, fill body features with zeros
            # features_arr[0:num_body_features_expected] are already 0.0
            idx = num_body_features_expected # Set index to where visibility scores will start

        # === VISIBILITY-WEIGHTED RELIABILITY SCORES === (4 features)
        # Ensure idx is correctly positioned before adding these last 4 features.
        # If the main block was skipped, idx is num_body_features_expected.
        # If the main block executed, idx should be num_body_features_expected.

        LOWER_BODY_VIS_INDICES = [23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
        UPPER_BODY_VIS_INDICES = [11, 12, 13, 14, 15, 16]
        CRITICAL_VIS_INDICES = [11, 12, 23, 24, 25, 26, 27, 28]

        # Ensure visibility array has data before indexing
        if visibility is not None and visibility.size > 0:
            vis_scores_lower = visibility[LOWER_BODY_VIS_INDICES] if all(i < len(visibility) for i in LOWER_BODY_VIS_INDICES) else np.array([])
            vis_scores_upper = visibility[UPPER_BODY_VIS_INDICES] if all(i < len(visibility) for i in UPPER_BODY_VIS_INDICES) else np.array([])
            vis_scores_critical = visibility[CRITICAL_VIS_INDICES] if all(i < len(visibility) for i in CRITICAL_VIS_INDICES) else np.array([])

            avg_vis_lower = np.mean(vis_scores_lower) if vis_scores_lower.size > 0 else 0.0
            avg_vis_upper = np.mean(vis_scores_upper) if vis_scores_upper.size > 0 else 0.0
            min_vis_critical = np.min(vis_scores_critical) if vis_scores_critical.size > 0 else 0.0
        else: # Should not happen if joints_xyv_array_normalized is valid
            avg_vis_lower, avg_vis_upper, min_vis_critical = 0.0, 0.0, 0.0

        weighted_overall_visibility = 0.7 * avg_vis_lower + 0.3 * avg_vis_upper
        
        # Assign visibility scores to the pre-allocated array
        # The final 4 slots are for these scores.
        vis_idx_start = num_body_features_expected 
        features_arr[vis_idx_start] = avg_vis_lower
        features_arr[vis_idx_start + 1] = avg_vis_upper
        features_arr[vis_idx_start + 2] = weighted_overall_visibility
        features_arr[vis_idx_start + 3] = min_vis_critical
        
        return np.nan_to_num(features_arr, nan=0.0, posinf=0.0, neginf=0.0)


    def extract_features(self, skeleton_joints_dict, is_enrollment_phase=False):
        """
        Extracts the detailed structural features from the skeleton_joints_dict.
        """
        if skeleton_joints_dict is None or \
           'landmarks_array' not in skeleton_joints_dict or \
           skeleton_joints_dict['landmarks_array'] is None:
            if config.PRINT_STATEMENTS:
                print("  [FE Log] No skeleton landmarks provided to extract_features. Returning zeros.")
            return np.zeros((1, self.expected_feature_size), dtype=np.float32)

        landmarks_array_normalized = skeleton_joints_dict['landmarks_array'] 
        
        detailed_features = self._extract_detailed_structural_features(landmarks_array_normalized)

        # _extract_detailed_structural_features now always returns an array of expected_feature_size
        # so, padding/truncating logic here is mostly a safeguard or for future changes.
        num_extracted_features = detailed_features.shape[0]

        if num_extracted_features == self.expected_feature_size:
            final_features = detailed_features
        elif num_extracted_features < self.expected_feature_size: # Should ideally not happen with pre-allocation
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] WARNING: Extracted skeleton features ({num_extracted_features}) "
                      f"fewer than expected ({self.expected_feature_size}). Padding with zeros.")
            padding = np.zeros(self.expected_feature_size - num_extracted_features, dtype=np.float32)
            final_features = np.concatenate((detailed_features, padding))
        else: # Should ideally not happen
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] WARNING: Extracted skeleton features ({num_extracted_features}) "
                      f"more than expected ({self.expected_feature_size}). Truncating.")
            final_features = detailed_features[:self.expected_feature_size]
            
        return final_features.reshape(1, -1)

# --- Face Recognition Feature Extractor ---
class FaceRecognitionFeatureExtractor(ModalityFeatureExtractor):
    """Extracts features for face recognition."""

    def __init__(self):
        """Initializes the face recognition feature extractor."""
        super().__init__(model_path=None, model_name="FaceRecognition")
        self.feature_dim = 128 

    def load_model(self, model_path):
        """Loads the face recognition model."""
        if config.PRINT_STATEMENTS:
                print("  [FE Log] FaceRecognitionFeatureExtractor uses built-in face_recognition (dlib) models. No external model loaded.")
        return "FACE_RECOGNITION_DLIB_INTERNAL"

    def preprocess(self, data_input, is_enrollment_phase=False):
        """Preprocesses the input data."""
        return data_input 

    def extract_features(self, precomputed_face_encoding, is_enrollment_phase=False):
        """Extracts features from face encodings."""
        if precomputed_face_encoding is not None and \
           isinstance(precomputed_face_encoding, np.ndarray) and \
           precomputed_face_encoding.shape == (self.feature_dim,):
            return precomputed_face_encoding.reshape(1, -1)
        else:
            return np.zeros((1, self.feature_dim), dtype=np.float32)


# --- Forearm Color Feature Extractor ---
class ForearmColorFeatureExtractor(ModalityFeatureExtractor):
    """Extracts color features from forearm regions."""

    def __init__(self):
        """Initializes the forearm color feature extractor."""
        super().__init__(model_path=None, model_name="ForearmColor")
        self.feature_dim = 60 # 2 forearms * 30 color channels (RGB)

    def load_model(self, model_path):
        """Overrides base load_model. Returns an identifier string."""
        if config.PRINT_STATEMENTS:
            print("  [FE Log] ForearmColorFeatureExtractor uses direct color calculation. No external model loaded.")
        return "ForearmColor"

    def _calculate_rotated_forearm_corners(self, p_elbow_px, p_wrist_px, 
                                           elbow_visibility, wrist_visibility,
                                           person_crop_w, person_crop_h):
        """
        Calculates the four corner points of a rotated rectangle around the forearm.
        Returns None if visibility is too low or calculation fails.
        """
        # Check visibility first
        if elbow_visibility < config.MP_MIN_VISIBILITY_FOR_FOREARM or \
           wrist_visibility < config.MP_MIN_VISIBILITY_FOR_FOREARM:
            return None

        if not (np.all(np.isfinite(p_elbow_px)) and np.all(np.isfinite(p_wrist_px))):
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] ForearmColor: Non-finite elbow/wrist points: E={p_elbow_px}, W={p_wrist_px}")
            return None

        forearm_vec = p_wrist_px - p_elbow_px
        forearm_length_px = np.linalg.norm(forearm_vec)

        if forearm_length_px < 1: 
            if config.PRINT_STATEMENTS: 
                print(f"  [FE Log] ForearmColor: Degenerate forearm length ({forearm_length_px:.2f}px).")
            return None

        thickness_px = max(5, min(25, int(forearm_length_px * 0.30))) 
        dir_vec_normalized = forearm_vec / forearm_length_px
        perp_vec_normalized = np.array([-dir_vec_normalized[1], dir_vec_normalized[0]])
        half_thickness_vec = perp_vec_normalized * (thickness_px / 2.0)

        c1 = p_elbow_px - half_thickness_vec 
        c2 = p_elbow_px + half_thickness_vec 
        c3 = p_wrist_px + half_thickness_vec 
        c4 = p_wrist_px - half_thickness_vec 
        
        corners = np.array([c1, c2, c3, c4], dtype=np.int32)
        return corners


    def extract_forearm_regions(self, skeleton_joints_dict, person_crop_image_dimensions_wh):
        """
        Identifies the four corner points for rotated bounding boxes around left and right forearms.
        """
        if skeleton_joints_dict is None or 'landmarks_array' not in skeleton_joints_dict or \
           person_crop_image_dimensions_wh is None or len(person_crop_image_dimensions_wh) != 2:
            if config.PRINT_STATEMENTS: 
                print("  [FE Log] ForearmColor: Invalid input to extract_forearm_regions.")
            return None

        landmarks_normalized = skeleton_joints_dict['landmarks_array'] # Shape (33, 3) [x, y, visibility]
        crop_w, crop_h = person_crop_image_dimensions_wh

        landmarks_pixel = landmarks_normalized.copy()
        landmarks_pixel[:, 0] *= crop_w  
        landmarks_pixel[:, 1] *= crop_h  

        left_elbow_idx, left_wrist_idx = 13, 15
        right_elbow_idx, right_wrist_idx = 14, 16

        left_elbow_px = landmarks_pixel[left_elbow_idx, :2]
        left_wrist_px = landmarks_pixel[left_wrist_idx, :2]
        left_elbow_vis = landmarks_normalized[left_elbow_idx, 2]
        left_wrist_vis = landmarks_normalized[left_wrist_idx, 2]

        right_elbow_px = landmarks_pixel[right_elbow_idx, :2]
        right_wrist_px = landmarks_pixel[right_wrist_idx, :2]
        right_elbow_vis = landmarks_normalized[right_elbow_idx, 2]
        right_wrist_vis = landmarks_normalized[right_wrist_idx, 2]

        left_forearm_corners = self._calculate_rotated_forearm_corners(
            left_elbow_px, left_wrist_px, 
            left_elbow_vis, left_wrist_vis,
            crop_w, crop_h
        )
        right_forearm_corners = self._calculate_rotated_forearm_corners(
            right_elbow_px, right_wrist_px,
            right_elbow_vis, right_wrist_vis,
            crop_w, crop_h
        )
        
        return {
            'left_forearm_corners': left_forearm_corners, # Can be None
            'right_forearm_corners': right_forearm_corners # Can be None
        }

    def extract_features(self, skeleton_joints_dict, person_crop_rgb_image, is_enrollment_phase=False):
        """Extracts color features from forearm regions."""
        if person_crop_rgb_image is None or person_crop_rgb_image.size == 0:
            if config.PRINT_STATEMENTS: 
                print("  [FE Log] ForearmColor: person_crop_rgb_image is None or empty.")
            return np.zeros((1, self.feature_dim), dtype=np.float32)
        
        crop_h, crop_w = person_crop_rgb_image.shape[:2]
        
        forearm_corner_sets = self.extract_forearm_regions(skeleton_joints_dict, (crop_w, crop_h))
        
        if forearm_corner_sets is None:
            if config.PRINT_STATEMENTS: 
                print("  [FE Log] ForearmColor: Failed to extract forearm regions (corner_sets is None).")
            return np.zeros((1, self.feature_dim), dtype=np.float32)

        features = []
        # Iterate through the keys that _calculate_rotated_forearm_corners would produce
        for region_key_suffix in ['left_forearm_corners', 'right_forearm_corners']: 
            corners_px = forearm_corner_sets.get(region_key_suffix) 

            if corners_px is None or not isinstance(corners_px, np.ndarray) or corners_px.shape != (4,2):
                features.extend([0] * 30)  # 10 bins * 3 channels
                continue
            
            mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
            cv2.fillPoly(mask, [corners_px.astype(np.int32)], 255) 

            if np.any(mask):
                hist_b = cv2.calcHist([person_crop_rgb_image], [0], mask, [10], [0, 256])
                hist_g = cv2.calcHist([person_crop_rgb_image], [1], mask, [10], [0, 256])
                hist_r = cv2.calcHist([person_crop_rgb_image], [2], mask, [10], [0, 256])

                hist_b = hist_b.flatten() / np.sum(hist_b)
                hist_g = hist_g.flatten() / np.sum(hist_g)
                hist_r = hist_r.flatten() / np.sum(hist_r)

                features.extend(hist_r.tolist() + hist_g.tolist() + hist_b.tolist())
            else:
                if config.PRINT_STATEMENTS: 
                    print(f"  [FE Log] ForearmColor: Empty mask for {region_key_suffix} (polygon likely out of bounds or zero area). Adding zeros.")
                features.extend([0] * 30)  # 10 bins * 3 channels

        return np.array(features, dtype=np.float32).reshape(1, -1)
