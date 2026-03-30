# Bluetooth Follow Me Module

This ROS package provides Bluetooth-based position tracking and following capabilities using Angle of Arrival (AoA) technology. It processes Bluetooth signals to determine the position of a target device and publishes the position data as ROS messages.

Location Estimation taken from: https://github.com/nino192/Marinero-Localization

## Dependencies

### ROS Dependencies
- roscpp
- std_msgs
- tf2_ros
- tf2_geometry_msgs
- geometry_msgs

### System Dependencies
- libmosquitto-dev
- mosquitto

## Installation

1. Clone this repository into your catkin workspace:
```bash
cd ~/catkin_ws/src
git clone <repository-url>
```

2. Install system dependencies:
```bash
sudo apt-get install libmosquitto-dev mosquitto
```

3. Build the package:
```bash
cd ~/catkin_ws
catkin_make
```

## Usage

### Launching the Node

The package can be launched using the provided launch file:

```bash
roslaunch bt_follow_me bt_follow_me.launch
```

### Manual Setup and Running

#### 1. Running the AoA Host

The AoA host can be run manually using the following command:

```bash
rosrun bt_follow_me followme_bt_AoA_host -u /dev/ttyACM0 -m localhost:1883 -c $(rospack find bt_follow_me)/NCP_Host/app/bluetooth/followme_bt_AoA_host/config/followme_locator_config.json
```

Parameters:
- `-u`: Bluetooth device path (default: `/dev/ttyACM0`)
- `-m`: MQTT broker address (default: `localhost:1883`)
- `-c`: Path to the configuration file

#### 2. Running the Visualizer

The visualizer provides real-time visualization of the Bluetooth AoA data. To set it up and run:

1. Install Python dependencies:
```bash
cd bt_follow_me/visualizer
curl -LsSf https://astral.sh/uv/install.sh | sh  # Install uv package manager
uv pip install -e .  # Install visualizer dependencies
```

2. Start the visualizer:
```bash
python3 visualizer.py
```

The visualizer will:
- Connect to the MQTT broker automatically
- Display a 3D plot showing tag positions
- Show azimuth and elevation angles in a 2D plot

### Configuration Parameters

The following parameters can be configured through the launch file:

- `device`: Bluetooth device path (default: `/dev/ttyACM0`)
- `mqtt`: MQTT broker address (default: `localhost:1883`)
- `config`: Path to the configuration file
- `smoothing_enabled`: Enable/disable position smoothing (default: `true`)
- `min_window_size`: Minimum window size for the moving average filter (default: `3`)
- `max_window_size`: Maximum window size for the moving average filter (default: `10`)
- `velocity_threshold`: Velocity threshold for adaptive filtering (default: `0.5` m/s)
- `noise_threshold`: Noise threshold for adaptive filtering (default: `0.1` m)

### Output

The node publishes position data as `geometry_msgs/PoseStamped` messages on the topic `/spot/bt_follower/pose`. The position is published in the `bluetooth_receiver_box` frame.

## Architecture

The package consists of two main components:

1. **AoA Host**: Processes raw Bluetooth signals and calculates position using AoA technology
2. **ROS Node**: Receives position data via MQTT, applies filtering, and publishes ROS messages
