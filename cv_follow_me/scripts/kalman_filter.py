# kalman_filter.py
import numpy as np
import cv2
import rospy # For logging if in ROS environment
import config

class KalmanFilterPy:
    """
    A Kalman filter implementation for tracking bounding box coordinates,
    wrapping cv2.KalmanFilter.
    The state is [cx, cy, w, h, v_cx, v_cy, v_w, v_h]
    The measurement is [cx, cy, w, h]
    """
    def __init__(self, dt=1.0/10.0, std_acc_process=1.0, std_meas_pos=1.0, std_meas_size=1.0):
        self.dt = dt
        self.std_acc_process = std_acc_process
        
        self.kf = cv2.KalmanFilter(8, 4) # 8 state dims, 4 measurement dims

        self.kf.transitionMatrix = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.kf.transitionMatrix[i, i + 4] = self.dt

        self.kf.measurementMatrix = np.zeros((4, 8), dtype=np.float32)
        for i in range(4):
            self.kf.measurementMatrix[i, i] = 1.0

        self._update_process_noise_cov() 

        self.kf.measurementNoiseCov = np.diag([
            std_meas_pos**2, std_meas_pos**2,
            std_meas_size**2, std_meas_size**2
        ]).astype(np.float32)

        self.kf.errorCovPost = np.eye(8, dtype=np.float32) * 100.0
        self.kf.statePost = np.zeros(8, dtype=np.float32)
        self.initialized = False

    def _update_transition_matrix(self):
        for i in range(4):
            self.kf.transitionMatrix[i, i + 4] = self.dt
            
    def _update_process_noise_cov(self):
        Q_comp_dt_part = np.array([
            [self.dt**4 / 4, self.dt**3 / 2],
            [self.dt**3 / 2, self.dt**2]
        ])
        Q_scalar_part = self.std_acc_process**2
        Q_single_dim_block = Q_comp_dt_part * Q_scalar_part
        Q = np.zeros((8, 8), dtype=np.float32)
        for i in range(4):
            idx_pos, idx_vel = i, i + 4
            Q[idx_pos, idx_pos] = Q_single_dim_block[0, 0]
            Q[idx_pos, idx_vel] = Q_single_dim_block[0, 1]
            Q[idx_vel, idx_pos] = Q_single_dim_block[1, 0]
            Q[idx_vel, idx_vel] = Q_single_dim_block[1, 1]
        self.kf.processNoiseCov = Q

    def initialize(self, initial_measurement_bbox_cxcywh):
        if len(initial_measurement_bbox_cxcywh) != 4:
            if config.PRINT_STATEMENTS: 
                rospy.logerr("KF Error: initial_measurement_bbox wrong size")
            return

        state_post_temp = np.zeros(8, dtype=np.float32)
        state_post_temp[:4] = np.array(initial_measurement_bbox_cxcywh, dtype=np.float32)
        self.kf.statePost = state_post_temp

        P_post_temp = np.eye(8, dtype=np.float32) * 100.0
        for i in range(4): P_post_temp[i,i] = self.kf.measurementNoiseCov[i,i]
        self.kf.errorCovPost = P_post_temp
        
        self.initialized = True
        if config.PRINT_STATEMENTS: 
            rospy.loginfo(f"KF (cv2) initialized: {self.kf.statePost[:4].flatten()}")

    def predict(self, current_dt=None):
        if not self.initialized:
            if config.PRINT_STATEMENTS: 
                rospy.logwarn_throttle(5, "KF (cv2) predict before init.")
            return None
        if current_dt is not None and current_dt > 0:
            self.dt = current_dt
            self._update_transition_matrix()
            self._update_process_noise_cov()
        return self.kf.predict().flatten()

    def update(self, measurement_bbox_cxcywh):
        if not self.initialized:
            if config.PRINT_STATEMENTS: 
                rospy.logwarn_throttle(5, "KF (cv2) update before init. Initializing.")
            self.initialize(measurement_bbox_cxcywh)
            return self.kf.statePost.flatten()
        if len(measurement_bbox_cxcywh) != 4:
            if config.PRINT_STATEMENTS: 
                rospy.logerr(f"KF (cv2) Error: measurement_bbox wrong size. Got: {measurement_bbox_cxcywh}")
            return self.kf.statePost.flatten()
        measurement_cv = np.array(measurement_bbox_cxcywh, dtype=np.float32).reshape(4,1)
        corrected_state = self.kf.correct(measurement_cv)
        self.kf.statePost[2] = max(1, self.kf.statePost[2]) # min width
        self.kf.statePost[3] = max(1, self.kf.statePost[3]) # min height
        return corrected_state.flatten()

    def get_state_bbox_cxcywh(self):
        if not self.initialized: return None
        return self.kf.statePost[:4].flatten().copy()

    def get_state_bbox_xyxy(self):
        if not self.initialized: return None
        cx, cy, w, h = self.kf.statePost[:4].flatten()
        return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]