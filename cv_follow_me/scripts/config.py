# config.py
import os

# --- Debugging ---
PRINT_STATEMENTS = False
DISPLAY_RGB_VIDEO = False
DISPLAY_DEPTH_VIDEO = False

# --- Control Mode ---
USE_TOPIC_CONTROL = True # Set to True to use ROS topic for state control, False for keyboard control
STATE_CONTROL_TOPIC = "/cv_follow_state" # Topic to send/receive state commands


# Expected messages on STATE_CONTROL_TOPIC (and messages to publish):
TOPIC_STATE_IDLE = "idle" 
TOPIC_STATE_ACQUIRE = "acquire"
TOPIC_STATE_TRACK = "track"
# Note: The application will internally use config.STATE_IDLE, config.STATE_ACQUIRING_TARGET, etc.


# --- YOLO Configuration ---
YOLO_MODEL_PATH_DEFAULT = "yolov8n.pt"
YOLO_PERSON_CONFIDENCE_THRESHOLD_DEFAULT = 0.7 # Minimum confidence for YOLO to consider a person detection valid


# --- Recording & Display ---
RECORD_VIDEO_FEED = False # Set to True to record the output video feed
RESULTS_FOLDER = os.path.expanduser("~/catkin_ws/src/FollowMe/cv_follow_me/results") # Folder to save recordings
RECORDING_FPS = 10 # Target FPS for recording (this affects the speed of the recording)
RECORDING_CODEC = 'mp4v' # Codec for recording (e.g., 'mp4v', 'XVID')
RECORDING_FILE_EXTENSION = '.mp4' # File extension for recordings


# --- Re-ID Configuration ---
MODALITY_WEIGHTS = {
    "RGB": 1.0,
    "Depth": 1.0,
    "Skeleton": 1.0,
    "FaceRecognition": 0.0,
    "ForearmColor": 1.0
}

# MODALITY_WEIGHTS = {
#     "RGB": 0.0,
#     "Depth": 0.0,
#     "Skeleton": 0.0,
#     "FaceRecognition": 0.0,
#     "ForearmColor": 1.0
# }

ACQUISITION_DURATION_SEC_DEFAULT = 10.0 # Duration for target acquisition
SUBSEQUENT_FRAMES_FOR_MATCH = 3 # Number of frames for a Re-ID match to be considered valid during tracking

# --- Percentile-based Re-ID Threshold Configuration ---
USE_PERCENTILE_REID_THRESHOLD = True  # Set to True to dynamically calculate Re-ID threshold
REID_THRESHOLD_PERCENTILE = .7     # E.g., 0.2 means the threshold will be the score at the 80th percentile (top 20% boundary)
MIN_SAMPLES_FOR_PERCENTILE_THRESHOLD = 10 # Min enrolled samples needed for percentile threshold calculation

# Or we can use a fixed threshold
REID_THRESHOLD = 0.9 # Default minimum fused score to consider a Re-ID match. Can be overridden by percentile calculation.


# --- Dynamic Weighting Configuration ---
USE_DYNAMIC_WEIGHTING = True  # Set to True to enable dynamic weight calculation
MIN_SAMPLES_FOR_VARIANCE_WEIGHTING = 15 # Min samples needed to calculate variance for a modality
MIN_VALID_SAMPLES_FOR_RELIABILITY = 5 # Min non-zero feature samples needed for a modality to be considered reliable from variance
MAX_VARIANCE_FOR_WEIGHTING = 1e9     # Effective variance for modalities failing reliability checks (e.g., all zero features)
DEFAULT_RELIABILITY_FACTOR_NO_SAMPLES = 0.1 # Multiplier for base_weight if not enough samples for variance calculation
YOLO_CONFIDENCE_MODULATION_POWER = 1.0 # Power to raise average YOLO confidence (0 to disable, 1 for linear)


# --- Set Device ---
DEVICE = 'cpu'


# --- Feature Extractor Configuration ---
# RGB Extractor (TorchReID)
RGB_EXTRACTOR_MODEL_NAME = 'osnet_x1_0'

# Depth Extractor (Adapted TorchReID)
DEPTH_EXTRACTOR_MODEL_NAME = 'osnet_x1_0'

# Skeleton Extractor (MediaPipe)
MP_STATIC_IMAGE_MODE = False # For video streams
MP_MODEL_COMPLEXITY = 1 # MediaPipe Pose model complexity (0, 1, or 2)
MP_MIN_DETECTION_CONFIDENCE = 0.5
MP_MIN_TRACKING_CONFIDENCE = 0.5
MP_MIN_VISIBILITY_FOR_FOREARM = 0.5 # Minimum visibility score for elbow/wrist to be considered for forearm detection

# Face Recognition Extractor
FACE_DETECTION_RESIZE_FACTOR = 1.0 # Factor to resize frame for face detection (smaller = faster)
FACE_DETECTION_MODEL = "hog" # "hog" (faster) or "cnn" (more accurate, slower, needs GPU)

# --- Application States (Internal) ---
STATE_IDLE = "IDLE"
STATE_ACQUIRING_TARGET = "ACQUIRING_TARGET"
STATE_TRACKING_TARGET = "TRACKING_TARGET"

# --- Key Bindings (Used when USE_TOPIC_CONTROL is False) ---
START_ACQUISITION_KEY = ' '  # Key to start target acquisition (space bar)
RESET_KEY = 'r'  # Key to reset to IDLE state
QUIT_KEY = 'q'  # Key to quit the application


# --- Robot Control ---
DISTANCE_AWAY_FROM_TARGET_MM = 1000 # mm, desired standoff distance from target
DISTANCE_BUFFER_MM = 250 # mm, buffer to prevent jittery movement

# --- Camera ---
DEFAULT_CAMERA_OPTICAL_FRAME_ID = "camera_color_optical_frame" # Default if not received from CameraInfo

# --- ROS Topics ---
COLOR_IMAGE_TOPIC = '/camera/color/image_raw'
DEPTH_IMAGE_TOPIC = '/camera/aligned_depth_to_color/image_raw'
# DEPTH_IMAGE_TOPIC = '/camera/depth/image_rect_raw'
CAMERA_INFO_TOPIC = '/camera/color/camera_info'
TARGET_POSE_TOPIC = '/spot/cv_follower/pose'

# --- Other ---
NODE_NAME = 'cv_follow_me'
MAIN_WINDOW_NAME = "Multi-Modal Tracker"
DEPTH_WINDOW_NAME = "Depth Visual (Colormapped)"

# Kalman Filter Configuration
USE_KALMAN_FILTER = True
KF_UPDATE_LOSS_THRESHOLD = 5  # Number of frames to predict before considering the KF track potentially lost
KF_DEFAULT_DT = 1.0 / 10.0  # Default time step for Kalman Filter
KF_STD_ACC_PROCESS = 2.5  # Standard deviation for process noise (acceleration)
KF_STD_MEAS_POS = 1.0  # Standard deviation for measurement noise (position)
KF_STD_MEAS_SIZE = 1.0  # Standard deviation for measurement noise (size)

REID_WEAK_MATCH_DELTA = 0.08 # Used for KF-assisted selection when appearance cues are not strong but spatial consistency exists
LOST_KF_THRESHOLD_BONUS_NEEDED = 0.05 # (Used to derive STRONG_REID_CONFIDENCE_THRESHOLD_FOR_KF_RESET)
KF_YOLO_IOU_THRESHOLD = 0.3 #  The system considers all current YOLO boxes that have at least this moderate IoU with the KF's prediction. From this subset of spatially plausible candidates, it then tries to pick the one with the best Re-ID score (as long as that score is above the calculated_reid_threshold_weak_match).
KF_YOLO_IOU_STRONG_ALIGNMENT_THRESHOLD = 0.5 # This is used for reacquiring a target that was just lost (should be high)
KF_FRESHNESS_FOR_REACQUISITION_FRAMES = 3 # Defines how many frames the KF track is considered "fresh" for the strong alignment reacquisition.
