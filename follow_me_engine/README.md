# FollowMe Project: follow_me_engine Module

## Overview
The `follow_me_engine` module is a key component of the FollowMe project. It enables the Boston Dynamics robot to track and follow a designated human leader using data from Bluetooth and/or computer vision sources.
Implemented as a ROS node, the module subscribes to position topics, processes them through a control loop to determine the desired heading and distance, and publishes velocity commands to the `/cmd_vel` topic to drive the robot.
 

## Functionality
- **Subscriptions**:
  - **Bluetooth Position Topic**: Receives position data via BG22-PK6022A locator from a Bluetooth beacon EFR32BG22 Thunderboard Kit carried by the human leader.
  - **Computer Vision Position Topic**: Receives 3D pose data (e.g., x, y, z coordinates or skeleton data) from an RGB-D camera, potentially using techniques like those in *Online RGB-D Person Re-identification Based on Metric Model Update*.
- **Control Loop**:
  - Employs a control algorithm Proportional (P) Controller to compute the robot’s heading (angle to the leader, α) and distance (ρ) relative to the desired distance.
- **Output**:
  - Publishes `geometry_msgs/Twist` messages to `/cmd_vel`, specifying linear (x-axis) and angular (z-axis) velocities to align the robot with the leader.
- **Safety Mechanism**:
  - Stops the robot by publishing zero velocity commands to `/cmd_vel` if no pose data (Bluetooth or vision) is received for 1.5 seconds, preventing unsafe movement.

## Parameters
The `follow_me_engine` node supports the following ROS parameters, configurable via a launch file or configuration file (e.g., `follow_me_engine.yaml`):

| Parameter            | Type   | Description                                                                 | Default Value |
|----------------------|--------|-----------------------------------------------------------------------------|---------------|
| `K_rho`              | Float  | Proportional gain for distance control (ρ), adjusting linear velocity.       | 0.6           |
| `K_alpha`            | Float  | Proportional gain for heading control (α), adjusting angular velocity.       | 1.0           |
| `desired_distance`   | Float  | Target distance (meters) to maintain from the human leader.                  | 1.0           |
| `max_lin_vel`        | Float  | Maximum linear velocity (m/s) for the robot.                                 | 1.0           |
| `max_ang_vel`        | Float  | Maximum angular velocity (rad/s) for the robot.                              | 1.0           |
| `distance_tolerance` | Float  | Acceptable error (meters) in maintaining the desired distance.               | 0.5           |
| `smoothing_window`   | Int    | Window size for smoothing noisy position data (e.g., moving average filter). | 1             |

## Dependencies
- **ROS**: Compatible with ROS Noetic or ROS 2 Humble.
- **Python**: Python 3.8+ for node implementation.
- **Messages**:
  - `geometry_msgs/Twist`: For velocity commands to `/cmd_vel`.
  - `geometry_msgs/PoseStamped` or similar: For computer vision position data.
  - Custom Bluetooth message (e.g., `follow_me_msgs/BluetoothPose`): For Bluetooth position data.
- **Libraries**:
  - `rospy` or `rclpy`: For ROS node development.
  - `numpy`: For numerical computations and data smoothing.
  - `OpenCV` or `PCL`: Optional for direct RGB-D data processing.
  - `catkin_tools`: `sudo apt install python3-catkin-tools`

## Installation
1. Clone the FollowMe repository into your ROS workspace:
   ```bash
   cd ~/catkin_ws/src
   git clone <repository_url>
   ```
2. Build the workspace:
   ```bash
   cd ~/catkin_ws
   catkin build
   ```
3. Source the workspace:
   ```bash
   source devel/setup.bash
   ```

## Usage

1. **Run the Node**:
   ```bash
   roslaunch follow_me follow_me_engine.launch
   ```

## Safety Features
- **Timeout Mechanism**: Publishes zero linear and angular velocities to `/cmd_vel` if pose data is absent for 1.5 seconds.
- **Velocity Limits**: Enforces `max_lin_vel` and `max_ang_vel` to keep robot movements within safe bounds.


## Notes
- **RGB-D Integration**: Is paired with re-identification methods (e.g., from *Online RGB-D Person Re-identification Based on Metric Model Update*) to ensure accurate leader tracking using features like skeleton data.

- **Tuning**: Adjust `K_rho`, `K_alpha`, and `smoothing_window` based on robot dynamics and environment (e.g., indoor vs. outdoor).


## Restriction
Please do not share this code at this time, as it is currently under patent application.