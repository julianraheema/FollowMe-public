# Bluetooth AoA Visualizer

This visualizer provides real-time visualization of Bluetooth Angle of Arrival (AoA) data from the FollowMe project.

## Features

- Real-time 3D position tracking
- Real-time angle visualization (azimuth and elevation)
- Support for multiple tags
- MQTT-based data subscription

## Prerequisites

- Python 3.6 or higher
- MQTT broker (Mosquitto)
- uv (Python package manager)

## Installation

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install the required Python packages:
```bash
uv pip install -e .
```

3. Ensure the MQTT broker is running:
```bash
sudo systemctl start mosquitto
```

## Usage

1. Start the FollowMe Bluetooth AoA host application (see main project README)

2. Run the visualizer:
```bash
python3 visualizer.py
```

The visualizer will automatically connect to the MQTT broker and start displaying:
- A 3D plot showing the position of all tracked tags
- A 2D plot showing the azimuth and elevation angles

## Configuration

The visualizer can be configured by modifying the following parameters in `visualizer.py`:
- `broker`: MQTT broker address (default: "localhost")
- `port`: MQTT broker port (default: 1883)

## Troubleshooting

1. If you see "Connection refused" errors:
   - Ensure the MQTT broker is running
   - Check if the broker address and port are correct

2. If the plots are not updating:
   - Verify that the FollowMe host application is running
   - Check if data is being published to the MQTT topics 