# Multi-Modal Person Tracker with Re-Identification

This system tracks a person using YOLO for detection and a multi-modal Re-ID system to keep track of their identity across frames. It works with RGB, Depth, and Skeleton data, using ROS for input/output. It is made for use with a robot that is already sending topics from its Realsense camera and can recieve pose coordinates to follow.

## How to run this

1. Run `pip install -r requirements.txt`

2. Makes sure you have Ros 1 installed and have the following camera topics published from a Realsense camera (we used a Realsense D455):

- RGB: `/camera/color/image_raw`
- Camera Intrinsics: `/camera/color/camera_info`
- Depth: `/camera/aligned_depth_to_color/image_raw`
- Depth for local development: `/camera/depth/image_rect_raw`

3. **Run `roslaunch cv_follow_me follow_me.launch`**

4. Run this to view the published topics for the robot `rostopic echo /spot/cv_follower/pose`


## Core Components

1. **ROS Interface (`ros_multi_modal_tracker.py`)**
- This is the main script that controls the flow.
- Subscribes to RealSense camera topics for RGB and Depth images, and camera info.
- Manages the application state (IDLE, ACQUIRING_TARGET, TRACKING_TARGET) via user interaction (key presses).
3. **Feature Extractors (`feature_extractors.py`)**
- Extract feature vector for each modality (RGB, Depth, Skeleton, etc.).

4. **Re-Identification System (`reid_system.py`)**

- Manages the enrolled target's features.
- Compares query person features against the target's features.
- Performs score-level fusion of similarity scores from active modalities.
- Determines if a query person matches the target based on a fused score and a threshold.

## Other Files

1. **Parameter Setting** (`config.py`)
- Used to set parameters for the program

2. **Event Handling** (`event_and_state_handlers.py`)
- Handles transitions from one state to the other (e.g. IDLE -> Tracking) and incoming key presses.

3. **Vision Utility Functions** (`vision_utils.py`)

4. **Kalman Filter** (`kalman_filter.py`)

5. **Input Testing** (`state_control_topic_client.py`)
- Used to test the ability to send commands to the robot (aquire target, start tracking, start idle).

## Pseudocode
```
Modalities = RGB, Skeleton, Depth, Forearm Color, etc.
Modality weights = RGB: .4, Skeleton: 1, Depth: .8, etc. (how important is each modality)

While the program is running:
  If STATE = IDLE:
    Nothing happens

  IF STATE = ACQUIRE:
    For n seconds:
      For each modality:
        Samples = Collect feature vector samples of the 
        person in frame (high dimensional embedding 
        representation of the person)

    For each sample collected:
      Sample Scores = Compute the score of the sample, 
      leaving the current sample out of the other 
      samples when compared

    Target Score = score in the 90th percentile of Sample 
    Scores (90th is an example, but basically the 
    "score to beat" is the score that is better than 
    some amount of the sample scores)

  IF STATE = TRACK:
    For each frame:
      Find all people in frame with YOLO:
        If they align with the Kalman filter or there 
        is no kalman filter:
          Compute their score

      If only one person in the frame has a score > 
      Target Score:
        Chosen person = this person

      If multiple people in frame have a score > 
      Target Score:
        Chosen person = this person
        
      Initialize Kalman filter on Chosen person
      Draw a box around the chosen person and send 
      their coordinates to the robot's topic



function Compute_Score(Current Frame, Samples):
  Score = 0
  for each modality:
    Modality Score = max score acheived when comparing the 
    Current Frame modality feature vector with each sample
     feature vector (essentially, the cosine distance 
     between the current frame and whichever sample is most 
     similar to it)


    Score += Modality Score * Modality Weight

    (This is a simplified version of the score, 
    you also have the option to include the variance 
    of each modality and yolo confidence score on the 
    right-hand side of this equation)


    Return Score
```




## Modalities
### Forearm Color Feature Extractor

The system now includes a **Forearm Color Feature Extractor**. This extractor uses skeleton tracking (MediaPipe Pose) to identify the forearm regions (elbow to wrist for both left and right arms) from a person's image crop.

1.  **Skeleton Detection**: First, MediaPipe Pose is used to detect 33 body landmarks on the person crop.
2.  **Forearm Identification**: Key landmarks for elbows and wrists (left_elbow, left_wrist, right_elbow, right_wrist) are identified. Their visibility scores are checked against `config.MP_MIN_VISIBILITY_FOR_FOREARM`.
3.  **Region Definition**: For each forearm with sufficient landmark visibility, a rotated rectangle is calculated to approximate the forearm area. The thickness of this rectangle is proportional to the forearm length (distance between elbow and wrist pixels), capped at a min/max.
4.  **Mask Creation**: A binary mask is created corresponding to this rotated rectangle within the person crop.
5.  **Color Histogram Extraction**:
    * For the masked region of each forearm in the RGB person crop, separate color histograms are calculated for the Red, Green, and Blue channels.
    * Each histogram uses 10 bins to cover the 0-255 pixel value range.
    * The histograms are normalized by dividing by the sum of their own bins (L1 norm).
6.  **Feature Vector**: The normalized histogram bins for R, G, B for the left forearm are concatenated, followed by the R, G, B bins for the right forearm. If a forearm is not visible or valid, zero-filled histogram bins are used.
    * This results in a feature vector of size (10 bins/channel * 3 channels * 2 forearms) = 60 dimensions. *(Self-correction: The `ForearmColorFeatureExtractor` class in `feature_extractors.py` initializes `self.feature_dim = 6` but then `features.extend([0] * 30)` per forearm, leading to a 60-dimensional feature vector. The `config.py` `feature_size_map` has `ForearmColor: 6`. This seems to be a discrepancy. The code in `extract_features` for `ForearmColorFeatureExtractor` clearly produces a 60-dimensional vector [10 bins * 3 channels for left + 10 bins * 3 channels for right]. I will describe based on the code's behavior, which is 60 dimensions).*

This extractor is particularly useful for distinguishing individuals wearing armbands or clothing of specific colors on their forearms.

### RGB Person Feature Extractor

The RGB Person Feature Extractor is responsible for generating a distinctive feature vector from the visual appearance (color image) of a detected person.

1.  **Model**: It utilizes a pre-trained deep learning model, typically one designed for person Re-Identification tasks. The default model is 'osnet_x1_0' from the `torchreid` library, but this can be configured via `config.RGB_EXTRACTOR_MODEL_NAME`.
2.  **Input**: It takes an RGB image crop of a person, usually obtained from a YOLO detection bounding box.
3.  **Preprocessing**:
    * The input BGR image crop is first converted to RGB format.
    * The RGB image is then transformed using `torchvision.transforms`:
        * Converted to a PIL (Python Imaging Library) Image.
        * Resized to a standard input size for the Re-ID model (e.g., 256x128 pixels).
        * Converted to a PyTorch tensor.
        * Normalized using standard ImageNet mean and standard deviation values.
4.  **Feature Extraction**:
    * The preprocessed tensor is passed through the loaded `torchreid` model.
    * The model outputs a feature vector (e.g., 512-dimensional for OSNet). This vector is a compact representation of the person's appearance.
5.  **Output**: The extractor returns this feature vector as a 1D NumPy array. If any step fails (e.g., empty input image, model error), it returns a zero vector of the expected feature size.

This feature vector can then be used by the Re-ID system to compare similarity with other RGB features.

### Depth Person Feature Extractor

The Depth Person Feature Extractor aims to generate a feature vector based on the 3D shape information of a detected person, derived from a depth image.

1.  **Model**: Similar to the RGB extractor, it employs a pre-trained deep learning model from `torchreid` (e.g., 'osnet_x1_0' by default). The idea is to adapt a CNN, originally trained on RGB images, to work with depth data by converting the depth map into an image-like format.
2.  **Input**: It takes a raw depth image crop corresponding to a detected person. Depth values are typically 16-bit integers representing distance (e.g., in millimeters).
3.  **Preprocessing**: This is an important step to adapt depth data for an RGB-trained model:
    * **Depth Normalization**:
        * Valid depth values within the crop (e.g., > 0) are considered.
        * These values are clipped to a practical range (e.g., 500mm to 8000mm as per the code).
        * The clipped depth values within the crop are then normalized to a 0-255 range (uint8) to create a grayscale-like image. This is a local normalization based on the min/max depth *within the current crop*.
    * **Channel Conversion**: The single-channel 8-bit depth image is converted into a 3-channel BGR image by replicating the grayscale channel three times (`cv2.cvtColor(depth_8u, cv2.COLOR_GRAY2BGR)`).
    * **Standard Image Transforms**: The resulting 3-channel image undergoes the same `torchvision.transforms` as the RGB extractor:
        * Converted to PIL Image.
        * Resized (e.g., 256x128).
        * Converted to PyTorch tensor.
        * Normalized using ImageNet statistics (though these stats are for RGB, it's a common practice when repurposing such models).
4.  **Feature Extraction**:
    * The preprocessed 3-channel tensor is fed into the loaded `torchreid` model.
    * The model outputs a feature vector (e.g., 512-dimensional).
5.  **Output**: It returns this feature vector as a 1D NumPy array. A zero vector is returned upon failure.

This approach allows leveraging powerful image-based Re-ID models for depth data, capturing shape and structural cues.

### Skeleton Feature Extractor

The Skeleton Feature Extractor generates features based on the detected human body pose and joint locations.

1.  **Pose Estimation Engine**: It uses MediaPipe Pose as its core engine. MediaPipe Pose is initialized with parameters from `config.py` (e.g., `MP_MODEL_COMPLEXITY`, `MP_MIN_DETECTION_CONFIDENCE`).
2.  **Input**: It takes an RGB image crop of a detected person.
3.  **Joint Detection (`get_joints` method)**:
    * The input crop is processed by the MediaPipe Pose estimator.
    * If a pose is detected, it provides 33 2D landmarks (x, y coordinates normalized to the crop dimensions) and a visibility score for each landmark.
    * The extractor returns a dictionary containing these landmarks as a NumPy array (shape: 33x3 for x, y, visibility) and the raw MediaPipe pose results.
4.  **Feature Vector Creation**:
    * The "features" are directly derived from these 33 landmarks.
    * The (33, 3) array of (x, y, visibility) values is flattened into a single 1D vector.
    * The resulting feature vector has 33 * 3 = 99 dimensions.
    * The code includes logic to pad with zeros or truncate if the flattened joint data is not exactly 99 elements, though with MediaPipe's fixed 33 landmarks, this should consistently be 99.
5.  **Output**: It returns this 99-dimensional NumPy array representing the person's pose. If no pose is detected or an error occurs, a zero vector of size 99 is returned.

Unlike the RGB and Depth extractors, this one does not use a separate deep learning model to *learn* features from the skeleton; instead, the normalized joint coordinates and their visibilities *are* the features. This captures the geometric configuration of the person's body.


### Face Recognition
This is implemented, but it slows down the program by quite a bit and isn't necessarily going to be the most helpful in this use case. The robot oftentimes doesn't have a clear view of the person's face because the camera is so low.