# event_and_state_handlers.py
import cv2
import rospy
import numpy as np
import config
from vision_utils import convert_box_to_cxcywh, calculate_iou
from std_msgs.msg import String

# --- Core State Transition Functions ---

def _reset_and_go_to_idle(tracker, triggered_by="system", full_reset=False, publish_now=True):
    """
    Transitions tracker to IDLE state.
    If full_reset is True, clears enrollment and KF.
    If full_reset is False (default), keeps enrollment and KF.
    Publishes 'idle' to the state feedback topic if USE_TOPIC_CONTROL is True and publish_now is True.
    """
    tracker.current_app_state = config.STATE_IDLE # Set internal state first
    log_msg_detail = "Transitioning to IDLE"

    if full_reset:
        if tracker.reid_module:
            tracker.reid_module.reset_enrollment() 
        if config.USE_KALMAN_FILTER:
            tracker.kf = None 
            tracker.frames_since_kf_update = 0
        else:
            tracker.kf = None
        tracker.tracked_target_info = {'box': None, 'score': -float('inf'), 'kf_box': None}
        tracker.current_target_consecutive_reid_count = 0
        log_msg_detail = "Full Reset to IDLE"
    else:
        log_msg_detail = "Pausing to IDLE (Enrollment/KF Kept)"
    
    tracker.acquisition_start_time = None 
    
    msg_log = f"STATE: ==> IDLE ({log_msg_detail} by {triggered_by})."
    rospy.loginfo(msg_log)

    if publish_now and config.USE_TOPIC_CONTROL and hasattr(tracker, 'state_feedback_pub') and tracker.state_feedback_pub is not None:
        try:
            tracker.state_feedback_pub.publish(String(data=config.TOPIC_STATE_IDLE))
            rospy.loginfo(f"Published '{config.TOPIC_STATE_IDLE}' to {config.STATE_CONTROL_TOPIC} (from _reset_and_go_to_idle by {triggered_by}).")
        except Exception as e:
            rospy.logerr(f"Failed to publish state feedback for IDLE from _reset_and_go_to_idle: {e}")
            
    return True, f"System set to IDLE ({log_msg_detail})."


def initiate_acquisition_sequence(tracker):
    """Starts the target acquisition process. This ALWAYS implies a full reset of previous target data."""
    if not (tracker.reid_module and tracker.reid_module.feature_extractors):
        rospy.logwarn("Cannot start acquisition: ReID module not initialized or no active Re-ID modalities.")
        return False, "ReID module not ready."
    
    # Reset fully, but defer publishing "idle" as we'll immediately publish "acquire".
    _reset_and_go_to_idle(tracker, triggered_by="new_acquisition_request", full_reset=True, publish_now=False) 
    
    tracker.current_app_state = config.STATE_ACQUIRING_TARGET # Set internal state
    tracker.acquisition_start_time = rospy.Time.now()
    tracker.target_samples_collected_during_acquisition = 0
    
    msg = f"STATE: ==> ACQUIRING_TARGET. Duration: {tracker.acquisition_duration.to_sec()} seconds."
    rospy.loginfo(msg)
    # Now publish the "acquire" state
    if hasattr(tracker, 'state_feedback_pub') and tracker.state_feedback_pub is not None and config.USE_TOPIC_CONTROL:
        try:
            tracker.state_feedback_pub.publish(String(data=config.TOPIC_STATE_ACQUIRE)) 
            rospy.loginfo(f"Published '{config.TOPIC_STATE_ACQUIRE}' to {config.STATE_CONTROL_TOPIC}.")
        except Exception as e:
            rospy.logerr(f"Failed to publish state feedback for ACQUIRE: {e}")
    return True, "Acquisition sequence started."

def initiate_tracking_sequence(tracker):
    """Starts tracking if a target is enrolled. Does NOT reset enrollment."""
    if not tracker.reid_module or not tracker.reid_module.get_is_target_enrolled():
        rospy.logwarn("Cannot start tracking: Target not enrolled or ReID module issue.")
        if config.USE_TOPIC_CONTROL and hasattr(tracker, 'state_feedback_pub') and tracker.state_feedback_pub is not None:
             if tracker.current_app_state != config.STATE_IDLE:
                _reset_and_go_to_idle(tracker, triggered_by="failed_tracking_init_not_enrolled", full_reset=False, publish_now=True) 
             elif tracker.current_app_state == config.STATE_IDLE: # Already IDLE, re-affirm by publishing
                try:
                    tracker.state_feedback_pub.publish(String(data=config.TOPIC_STATE_IDLE))
                except Exception as e: rospy.logerr(f"Failed to publish state feedback for IDLE after failed track init: {e}")
        return False, "Target not enrolled."

    tracker.current_app_state = config.STATE_TRACKING_TARGET # Set internal state

    tracker.current_target_consecutive_reid_count = 0 # Reset count when explicitly starting to track

    if config.USE_KALMAN_FILTER and tracker.kf is not None:
        tracker.frames_since_kf_update = 0 
    elif config.USE_KALMAN_FILTER and tracker.kf is None:
        rospy.logwarn("Starting tracking, but KF is not initialized. Will attempt init on first strong ReID.")
        tracker.last_kf_time_update = rospy.Time.now() 

    msg = f"STATE: ==> TRACKING_TARGET. Active ReID Threshold: {tracker.reid_module.reid_threshold:.4f}"
    if config.PRINT_STATEMENTS:
        rospy.loginfo(msg)
    # Now publish the "track" state
    if hasattr(tracker, 'state_feedback_pub') and tracker.state_feedback_pub is not None and config.USE_TOPIC_CONTROL:
        try:
            tracker.state_feedback_pub.publish(String(data=config.TOPIC_STATE_TRACK)) 
            rospy.loginfo(f"Published '{config.TOPIC_STATE_TRACK}' to {config.STATE_CONTROL_TOPIC}.")
        except Exception as e:
            rospy.logerr(f"Failed to publish state feedback for TRACK: {e}")
    return True, "Tracking sequence started."

# --- Key Press Handler ---
def handle_key_press(tracker, key_code):
    key_char = ''
    try:
        key_char = chr(key_code & 0xFF)
    except ValueError:
        rospy.logwarn(f"Invalid key code received: {key_code}")
        return

    if key_char == config.QUIT_KEY:
        rospy.signal_shutdown("Quit signal received via keyboard.")
        return

    if config.USE_TOPIC_CONTROL:
        rospy.loginfo_throttle(5, "Key presses (except 'q') are ignored when USE_TOPIC_CONTROL is True. Use ROS topic for control.")
        return 

    if key_char == config.START_ACQUISITION_KEY: 
        if tracker.current_app_state == config.STATE_IDLE:
            initiate_acquisition_sequence(tracker) # This will publish "acquire"
        elif tracker.current_app_state in [config.STATE_ACQUIRING_TARGET, config.STATE_TRACKING_TARGET]:
            # Pressing space while acquiring or tracking (keyboard mode) means stop and go to IDLE,
            # but keep enrollment/KF (pause functionality). This will publish "idle".
            _reset_and_go_to_idle(tracker, triggered_by="user_keypress_stop_pause", full_reset=False, publish_now=True)
    elif key_char == config.RESET_KEY: 
        # 'r' key is a hard reset, clears everything and goes to IDLE. This will publish "idle".
        _reset_and_go_to_idle(tracker, triggered_by="user_keypress_reset", full_reset=True, publish_now=True)

# --- State Logic Handlers ---
def handle_idle_state(tracker, display_frame):
    if config.DISPLAY_RGB_VIDEO and display_frame is not None:
        status_text = "IDLE"
        if not tracker.reid_module or not tracker.reid_module.feature_extractors:
            status_text = "IDLE (ReID Disabled or No Active Modalities)"
        elif config.USE_TOPIC_CONTROL:
            if tracker.reid_module.get_is_target_enrolled():
                 status_text = f"IDLE (Target Enrolled - Ready for '{config.TOPIC_STATE_TRACK}' cmd)"
            else:
                 status_text = f"IDLE (Ready for '{config.TOPIC_STATE_ACQUIRE}' cmd)"
        elif not config.USE_TOPIC_CONTROL: 
             status_text = "IDLE: Press SPACE to Start Acquisition"
        cv2.putText(display_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)


def handle_acquisition_state(tracker, display_frame, detected_persons_data,
                               rgb_frame_full, raw_depth_frame_full,
                               frame_face_locations_scaled, frame_face_encodings, face_scale_factor):
    if not tracker.reid_module or not tracker.reid_module.feature_extractors or tracker.acquisition_start_time is None:
        rospy.logwarn("Acquisition state entered incorrectly or ReID module not ready. Resetting to IDLE.")
        _reset_and_go_to_idle(tracker, triggered_by="acquisition_precondition_fail", full_reset=True, publish_now=True) 
        return

    time_remaining = tracker.acquisition_duration - (rospy.Time.now() - tracker.acquisition_start_time)
    status_msg_prefix = f"ACQUIRING ({tracker.target_samples_collected_during_acquisition} samples)"
    status_msg, acquisition_box_color = "", (0, 255, 255) 
    target_person_box_for_enroll, yolo_conf_for_enroll = None, None

    if time_remaining > rospy.Duration(0):
        if detected_persons_data:
            if len(detected_persons_data) == 1:
                target_person_box_for_enroll = detected_persons_data[0]['box']
                yolo_conf_for_enroll = detected_persons_data[0]['conf']
                status_msg = f"{status_msg_prefix}: {time_remaining.to_sec():.1f}s left. Keep target in view."
            else: 
                status_msg = f"{status_msg_prefix}: Multiple people! Isolate. {time_remaining.to_sec():.1f}s left."
                acquisition_box_color = (0, 165, 255) 
        else: 
            status_msg = f"{status_msg_prefix}: No person. {time_remaining.to_sec():.1f}s left."
            acquisition_box_color = (0, 0, 255) 

        if target_person_box_for_enroll: 
            enroll_data_dict = tracker._prepare_modality_inputs(
                rgb_frame_full, raw_depth_frame_full, target_person_box_for_enroll,
                frame_face_locations_scaled, frame_face_encodings, face_scale_factor)
            if enroll_data_dict:
                try:
                    features_added_this_sample = tracker.reid_module.enroll_target_features_sample(enroll_data_dict, yolo_conf_for_enroll)
                    if features_added_this_sample:
                        tracker.target_samples_collected_during_acquisition += 1
                        if config.USE_KALMAN_FILTER and tracker.kf is None and tracker.target_samples_collected_during_acquisition >= 1:
                            cx, cy, w, h = convert_box_to_cxcywh(target_person_box_for_enroll)
                            current_kf_init_time = rospy.Time.now()
                            if tracker.last_kf_time_update is None: tracker.last_kf_time_update = current_kf_init_time - rospy.Duration.from_sec(tracker.KF_DEFAULT_DT)
                            dt_init = (current_kf_init_time - tracker.last_kf_time_update).to_sec()
                            if dt_init <= 0: dt_init = tracker.KF_DEFAULT_DT
                            tracker.kf = tracker.KalmanFilterPy(dt=dt_init,
                                                                std_acc_process=tracker.KF_STD_ACC_PROCESS,
                                                                std_meas_pos=tracker.KF_STD_MEAS_POS,
                                                                std_meas_size=tracker.KF_STD_MEAS_SIZE)
                            tracker.kf.initialize([cx, cy, w, h])
                            tracker.last_kf_time_update = current_kf_init_time
                            rospy.loginfo(f"Kalman Filter initialized during acquisition with box {target_person_box_for_enroll}.")
                except Exception as e:
                    rospy.logerr(f"Error during ReID enrollment call: {e}")
            if config.DISPLAY_RGB_VIDEO and display_frame is not None and target_person_box_for_enroll: 
                x1, y1, x2, y2 = map(int, target_person_box_for_enroll)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), acquisition_box_color, 2)
        if config.DISPLAY_RGB_VIDEO and display_frame is not None:
            cv2.putText(display_frame, status_msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, acquisition_box_color, 2)
    else: # Acquisition time ended
        acquisition_was_successful = tracker.reid_module.get_is_target_enrolled()
        tracker.acquisition_start_time = None 
        if acquisition_was_successful:
            rospy.loginfo(f"Acquisition complete. Total distinct samples with features: {tracker.reid_module.get_enrollment_count()}.")
            tracker.reid_module.finalize_enrollment_phase() 
            if config.USE_TOPIC_CONTROL:
                _reset_and_go_to_idle(tracker, triggered_by="successful_acquisition_topic_mode", full_reset=False, publish_now=True)
                if config.PRINT_STATEMENTS:
                    rospy.loginfo(f"Waiting for '{config.TOPIC_STATE_TRACK}' command. Active ReID Threshold: {tracker.reid_module.reid_threshold:.4f}")
            else: 
                initiate_tracking_sequence(tracker) 
        else: 
            rospy.logwarn("Acquisition ended, but target not successfully enrolled. Returning to IDLE with full reset.")
            _reset_and_go_to_idle(tracker, triggered_by="failed_acquisition", full_reset=True, publish_now=True)
        

def handle_tracking_state(tracker, display_frame, detected_persons_data,
                          rgb_frame_full, raw_depth_frame_full,
                          frame_face_locations_scaled, frame_face_encodings, face_scale_factor):
    if not tracker.reid_module or not tracker.reid_module.get_is_target_enrolled():
        rospy.logwarn("Tracking state entered but target not enrolled or ReID module issue. Resetting to IDLE.")
        _reset_and_go_to_idle(tracker, triggered_by="tracking_precondition_fail_not_enrolled", full_reset=True, publish_now=True) 
        return

    is_potential_target_found_this_frame = False
    potential_authoritative_box = None
    potential_output_score = -float('inf')
    status_msg = "TRACKING"
    kf_box_after_update_or_pred = None

    calculated_reid_threshold_weak_match = 0.05 
    if hasattr(tracker.reid_module, 'reid_threshold') and hasattr(config, 'REID_WEAK_MATCH_DELTA'):
        calculated_reid_threshold_weak_match = max(0.05, tracker.reid_module.reid_threshold - config.REID_WEAK_MATCH_DELTA)

    kf_prediction_box_this_frame = None
    if config.USE_KALMAN_FILTER and tracker.kf and tracker.kf.initialized:
        current_kf_op_time = rospy.Time.now()
        if tracker.last_kf_time_update is None: tracker.last_kf_time_update = current_kf_op_time - rospy.Duration.from_sec(tracker.KF_DEFAULT_DT)
        dt_kf = (current_kf_op_time - tracker.last_kf_time_update).to_sec()
        if dt_kf <= 0: dt_kf = tracker.KF_DEFAULT_DT
        _ = tracker.kf.predict(current_dt=dt_kf) 
        kf_prediction_box_this_frame = tracker.kf.get_state_bbox_xyxy()
        kf_box_after_update_or_pred = kf_prediction_box_this_frame
        tracker.frames_since_kf_update += 1
        tracker.last_kf_time_update = current_kf_op_time
    elif config.USE_KALMAN_FILTER and tracker.kf is None: 
        if tracker.last_kf_time_update is None : tracker.last_kf_time_update = rospy.Time.now()

    all_yolo_candidates_with_reid_scores = []
    best_primary_reid_yolo_box = None
    best_primary_reid_score = -float('inf')
    target_primarily_reidentified = False

    for person_data in detected_persons_data: 
        query_yolo_box = person_data['box']
        x1_q, y1_q, _, _ = map(int, query_yolo_box) 
        query_data_dict_for_reid = tracker._prepare_modality_inputs(
            rgb_frame_full, raw_depth_frame_full, query_yolo_box,
            frame_face_locations_scaled, frame_face_encodings, face_scale_factor)
        fused_score = -1.0 
        is_strong_match_for_this_box = False
        if query_data_dict_for_reid:
            try:
                is_strong_match_for_this_box, fused_score, _ = tracker.reid_module.re_identify(query_data_dict_for_reid)
            except Exception as e: rospy.logerr(f"Re-ID error for box {query_yolo_box}: {e}")
        all_yolo_candidates_with_reid_scores.append({
            'box': query_yolo_box, 'reid_score': fused_score, 'is_strong_match': is_strong_match_for_this_box })
        if config.DISPLAY_RGB_VIDEO and display_frame is not None: 
            score_text_y = max(15, y1_q - 7)
            cv2.putText(display_frame, f"F:{fused_score:.2f}", (x1_q, score_text_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0) if is_strong_match_for_this_box else (0, 100, 255), 1)
        if is_strong_match_for_this_box and fused_score > best_primary_reid_score:
            best_primary_reid_score = fused_score
            best_primary_reid_yolo_box = query_yolo_box
            target_primarily_reidentified = True

    kf_was_updated_or_reinitialized_this_frame = False 
    STRONG_REID_CONFIDENCE_THRESHOLD_FOR_KF_RESET = tracker.reid_module.reid_threshold + config.LOST_KF_THRESHOLD_BONUS_NEEDED

    if target_primarily_reidentified:
        is_potential_target_found_this_frame = True
        potential_authoritative_box = best_primary_reid_yolo_box
        potential_output_score = best_primary_reid_score
        status_msg = f"TRACKING (Strong ReID: {potential_output_score:.2f})"
        if config.USE_KALMAN_FILTER:
            cx_m, cy_m, w_m, h_m = convert_box_to_cxcywh(potential_authoritative_box)
            current_kf_op_time_for_update = rospy.Time.now()
            if tracker.last_kf_time_update is None or tracker.last_kf_time_update > current_kf_op_time_for_update :
                 tracker.last_kf_time_update = current_kf_op_time_for_update - rospy.Duration.from_sec(tracker.KF_DEFAULT_DT)
            dt_op = (current_kf_op_time_for_update - tracker.last_kf_time_update).to_sec()
            if dt_op <= 0: dt_op = tracker.KF_DEFAULT_DT
            if tracker.kf and tracker.kf.initialized:
                is_kf_stale = tracker.frames_since_kf_update > (tracker.KF_UPDATE_LOSS_THRESHOLD * 0.60)
                if is_kf_stale and potential_output_score > STRONG_REID_CONFIDENCE_THRESHOLD_FOR_KF_RESET:
                    rospy.logwarn(f"KF stale ({tracker.frames_since_kf_update} frames no update), strong Re-ID found. Re-initializing KF.")
                    tracker.kf.dt = dt_op; tracker.kf.initialize([cx_m, cy_m, w_m, h_m]); status_msg += " KF Re-Init"
                else:
                    tracker.kf.update([cx_m, cy_m, w_m, h_m]); status_msg += " KF Update"
            elif tracker.kf is None :
                rospy.loginfo(f"Target re-identified. Initializing KF with box {potential_authoritative_box}.")
                tracker.kf = tracker.KalmanFilterPy(dt=dt_op, std_acc_process=tracker.KF_STD_ACC_PROCESS, std_meas_pos=tracker.KF_STD_MEAS_POS, std_meas_size=tracker.KF_STD_MEAS_SIZE)
                tracker.kf.initialize([cx_m, cy_m, w_m, h_m]); status_msg += " KF Init"
            
            if tracker.kf:
                kf_was_updated_or_reinitialized_this_frame = True; tracker.frames_since_kf_update = 0
                tracker.last_kf_time_update = current_kf_op_time_for_update
                kf_box_after_update_or_pred = tracker.kf.get_state_bbox_xyxy()

    elif config.USE_KALMAN_FILTER and tracker.kf and tracker.kf.initialized and kf_prediction_box_this_frame and all_yolo_candidates_with_reid_scores:
        chosen_for_kf_assist = False
        kf_assist_box = None
        kf_assist_score = -float('inf')

        if tracker.frames_since_kf_update <= config.KF_FRESHNESS_FOR_REACQUISITION_FRAMES:
            best_strong_iou_candidate = None; best_strong_iou_value = -1.0
            for candidate in all_yolo_candidates_with_reid_scores:
                iou_with_kf = calculate_iou(kf_prediction_box_this_frame, candidate['box'])
                if iou_with_kf > config.KF_YOLO_IOU_STRONG_ALIGNMENT_THRESHOLD:
                    if iou_with_kf > best_strong_iou_value:
                        best_strong_iou_value = iou_with_kf; best_strong_iou_candidate = candidate
            if best_strong_iou_candidate:
                kf_assist_box = best_strong_iou_candidate['box']; kf_assist_score = best_strong_iou_candidate['reid_score']
                status_msg = f"TRACKING (KF Re-Acq. IoU:{best_strong_iou_value:.2f} ReID:{kf_assist_score:.2f})"; chosen_for_kf_assist = True
        
        if not chosen_for_kf_assist:
            best_weak_reid_candidate = None; highest_reid_score_for_weak_match = -float('inf')
            for candidate in all_yolo_candidates_with_reid_scores:
                iou_with_kf = calculate_iou(kf_prediction_box_this_frame, candidate['box'])
                if iou_with_kf > config.KF_YOLO_IOU_THRESHOLD: 
                    if candidate['reid_score'] > highest_reid_score_for_weak_match:
                        highest_reid_score_for_weak_match = candidate['reid_score']; best_weak_reid_candidate = candidate
            if best_weak_reid_candidate and highest_reid_score_for_weak_match > calculated_reid_threshold_weak_match:
                kf_assist_box = best_weak_reid_candidate['box']; kf_assist_score = highest_reid_score_for_weak_match
                status_msg = f"TRACKING (KF-WeakReID: {kf_assist_score:.2f})"; chosen_for_kf_assist = True
        
        if chosen_for_kf_assist and kf_assist_box and tracker.kf:
            is_potential_target_found_this_frame = True
            potential_authoritative_box = kf_assist_box
            potential_output_score = kf_assist_score
            cx_m, cy_m, w_m, h_m = convert_box_to_cxcywh(potential_authoritative_box)
            current_kf_op_time_for_update = rospy.Time.now()
            if tracker.last_kf_time_update is None or tracker.last_kf_time_update > current_kf_op_time_for_update:
                tracker.last_kf_time_update = current_kf_op_time_for_update - rospy.Duration.from_sec(tracker.KF_DEFAULT_DT)
            dt_op_kf_assist = (current_kf_op_time_for_update - tracker.last_kf_time_update).to_sec()
            if dt_op_kf_assist <=0: dt_op_kf_assist = tracker.KF_DEFAULT_DT
            tracker.kf.update([cx_m, cy_m, w_m, h_m]); kf_was_updated_or_reinitialized_this_frame = True
            tracker.frames_since_kf_update = 0; tracker.last_kf_time_update = current_kf_op_time_for_update
            kf_box_after_update_or_pred = tracker.kf.get_state_bbox_xyxy(); status_msg += " KF Update"

    authoritative_yolo_box_for_output = None
    output_score = -float('inf')
    final_kf_box_for_display_and_info = kf_box_after_update_or_pred

    if is_potential_target_found_this_frame:
        tracker.current_target_consecutive_reid_count += 1
    else:
        tracker.current_target_consecutive_reid_count = 0
        if config.USE_KALMAN_FILTER and tracker.kf and tracker.kf.initialized and \
           tracker.frames_since_kf_update < tracker.KF_UPDATE_LOSS_THRESHOLD:
            status_msg = f"TRACKING - ReID Lost (KF Pred {tracker.frames_since_kf_update}/{tracker.KF_UPDATE_LOSS_THRESHOLD})"
        else:
            status_msg = "TRACKING - Target Lost"
            if config.USE_KALMAN_FILTER and tracker.kf and \
               tracker.frames_since_kf_update >= tracker.KF_UPDATE_LOSS_THRESHOLD:
                status_msg += " (KF Lost)"
            final_kf_box_for_display_and_info = None


    if tracker.current_target_consecutive_reid_count >= config.SUBSEQUENT_FRAMES_FOR_MATCH:
        authoritative_yolo_box_for_output = potential_authoritative_box
        output_score = potential_output_score
        
        if potential_authoritative_box:
            base_status_for_confirm = status_msg 
            if "(Strong ReID:" in base_status_for_confirm or "(KF Re-Acq." in base_status_for_confirm or "(KF-WeakReID:" in base_status_for_confirm :
                 # Try to keep the method info from the status_msg
                 parts = base_status_for_confirm.split(')')
                 if len(parts) > 0:
                     status_msg = f"{parts[0]}) Confirmed [{tracker.current_target_consecutive_reid_count}]"
                 else: # Fallback if split fails
                     status_msg = f"TRACKING (Confirmed: {output_score:.2f} [{tracker.current_target_consecutive_reid_count}])"
            else: # Fallback if status_msg was generic
                 status_msg = f"TRACKING (Confirmed: {output_score:.2f} [{tracker.current_target_consecutive_reid_count}])"

    elif is_potential_target_found_this_frame:
        status_msg = f"TRACKING (Pending: {potential_output_score:.2f} [{tracker.current_target_consecutive_reid_count}/{config.SUBSEQUENT_FRAMES_FOR_MATCH}])"

    tracker.tracked_target_info = {'box': authoritative_yolo_box_for_output,
                                 'score': output_score,
                                 'kf_box': final_kf_box_for_display_and_info if config.USE_KALMAN_FILTER else None }

    if config.DISPLAY_RGB_VIDEO and display_frame is not None:
        if is_potential_target_found_this_frame and \
           tracker.current_target_consecutive_reid_count < config.SUBSEQUENT_FRAMES_FOR_MATCH and \
           potential_authoritative_box:
            px1, py1, px2, py2 = map(int, potential_authoritative_box)
            cv2.rectangle(display_frame, (px1, py1), (px2, py2), (0, 0, 255), 2) # Yellow
            cv2.putText(display_frame, f"Pending ({tracker.current_target_consecutive_reid_count})",
                        (px1, py1 - 20 if py1 - 20 > 0 else py1 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)

        auth_box_draw = tracker.tracked_target_info.get('box')
        if auth_box_draw:
            ax1, ay1, ax2, ay2 = map(int, auth_box_draw); cv2.rectangle(display_frame, (ax1, ay1), (ax2, ay2), (0, 255, 0), 3) # Green
            # current_displayed_score = tracker.tracked_target_info.get('score', -float('inf'))
            # score_label_text = f"CONFIRMED ({current_displayed_score:.2f})" if current_displayed_score > -float('inf') else "CONFIRMED TARGET"
            # label_y_pos = ay1 - 7 if ay1 - 7 > 0 else ay1 + 20
            # cv2.putText(display_frame, score_label_text, (ax1, label_y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0),2)

        kf_box_draw = tracker.tracked_target_info.get('kf_box')
        if config.USE_KALMAN_FILTER and kf_box_draw:
            kfx1, kfy1, kfx2, kfy2 = map(int, kf_box_draw); kf_color_draw = (255, 255, 0); kf_label_draw = "KF Est."
            if not auth_box_draw and tracker.kf and tracker.kf.initialized and tracker.frames_since_kf_update < tracker.KF_UPDATE_LOSS_THRESHOLD :
                 kf_color_draw = (0, 165, 255); kf_label_draw = "KF Pred (No Lock)"
            cv2.rectangle(display_frame, (kfx1, kfy1), (kfx2, kfy2), kf_color_draw, 1)
            kf_label_y_pos = kfy1 - 7 if kfy1 - 7 > 0 else kfy1 + 15
            if auth_box_draw and 'ay1' in locals() and abs(kfy1 - ay1) < 20 : # check ay1 exists
                 kf_label_y_pos = kfy1 + 25 if kfy1 < display_frame.shape[0] - 30 else kfy1 - 15 # check bounds better

            cv2.putText(display_frame, kf_label_draw, (kfx1, kf_label_y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.45, kf_color_draw, 1)
        
        top_status_color_draw = (0,255,0) if auth_box_draw else \
                               ((0, 255, 255) if is_potential_target_found_this_frame and potential_authoritative_box else \
                               ((0,165,255) if (config.USE_KALMAN_FILTER and kf_box_draw and not auth_box_draw) else (0,0,255)))
        cv2.putText(display_frame, status_msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, top_status_color_draw, 2)
        
        if tracker.reid_module and hasattr(config, 'REID_WEAK_MATCH_DELTA'):
            weak_thresh_val = calculated_reid_threshold_weak_match
            reid_thresh_text = f"ReID Th:{tracker.reid_module.reid_threshold:.2f} Wk:{weak_thresh_val:.2f}"
            if not config.USE_KALMAN_FILTER: reid_thresh_text += " (KF OFF)"
            reid_thresh_text += f" ConfirmN:{config.SUBSEQUENT_FRAMES_FOR_MATCH}"
            cv2.putText(display_frame, reid_thresh_text,
                        (display_frame.shape[1] - 400, display_frame.shape[0] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 0), 1)

    if authoritative_yolo_box_for_output:
        tx1, ty1, tx2, ty2 = map(int, authoritative_yolo_box_for_output)
        center_x_px, center_y_px = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0
        depth_mm = tracker.get_median_depth_in_box_mm(authoritative_yolo_box_for_output)
        if depth_mm is not None and depth_mm > (config.DISTANCE_AWAY_FROM_TARGET_MM + config.DISTANCE_BUFFER_MM):
            depth_for_robot_goal_mm = depth_mm - config.DISTANCE_AWAY_FROM_TARGET_MM
            point_x, point_y, point_z = tracker.deproject_pixel_to_point_m(center_x_px, center_y_px, depth_for_robot_goal_mm)
            if point_x is not None: 
                pose = tracker.PoseStamped(); pose.header.stamp = rospy.Time.now(); pose.header.frame_id = tracker.camera_optical_frame_id
                pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = point_x, point_y, point_z
                pose.pose.orientation.x, pose.pose.orientation.y, pose.pose.orientation.z, pose.pose.orientation.w = 0.5, -0.5, 0.5, 0.5 
                tracker.target_pose_pub.publish(pose)
        elif depth_mm is not None and config.PRINT_STATEMENTS: 
            rospy.loginfo_throttle(2, f"Target (YOLO Box for Pub) at {depth_mm:.0f}mm. Within standoff or too close. No pose published.")
        elif config.PRINT_STATEMENTS and authoritative_yolo_box_for_output:
            rospy.loginfo_throttle(1, "Confirmed target has no valid depth or pose. Pose not published.")
    elif config.PRINT_STATEMENTS:
        rospy.loginfo_throttle(1, f"Target not confirmed ({tracker.current_target_consecutive_reid_count}/{config.SUBSEQUENT_FRAMES_FOR_MATCH} frames). Pose not published.")