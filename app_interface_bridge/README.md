# app_interface_bridge

The `app_interface_bridge` package is a ROS wrapper designed to interface with a smartwatch application, allowing for remote control and interaction with a robot via HTTP POST requests.

## Overview

This module listens for commands sent from a smartwatch using HTTPS POST requests. The messages are sent in JSON format and translated into ROS commands, services, or actions to control a robot running within a ROS ecosystem.

## Features

- Accepts remote commands via HTTP POST using JSON
- Supports full teleoperation of the robot (e.g., velocity control)
- Provides service calls for:
  - Sit / Stand
  - Claim lease
  - Power On / Off
  - Initiate robot following mode

## Use Case

This package bridges mobile app interfaces with ROS, enabling intuitive and remote control of robots using wearable devices such as a smartwatch. 


## Requirements

- ROS Noetic (or compatible version)
- Smartwatch application capable of sending JSON data via HTTPS POST
- Python libraries for HTTP server handling (e.g., `Flask` or `http.server`)


## Running the Server

```bash
source devel/setup.bash
rosrun app_interface_bridge app_server
```

Make sure the smartwatch and the computer are connected to the same network, and the smartwatch is configured to send requests to the server’s IP address and port.

---

For any issues or support, contact:  
julian.y.raheema.civ@us.navy.mil  
jraheema@ucsd.edu