#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import json
from collections import defaultdict
import time

class AoAVisualizer:
    def __init__(self, broker="localhost", port=1883):
        print(f"Initializing visualizer with broker: {broker}:{port}")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.broker = broker
        self.port = port

        # Data storage
        self.positions = defaultdict(list)  # {tag_id: [(x, y, z), ...]}
        self.angles = defaultdict(list)     # {tag_id: [(azimuth, elevation), ...]}

        # Plot setup
        self.fig = plt.figure(figsize=(12, 6))
        self.ax1 = self.fig.add_subplot(121, projection='3d')  # 3D position plot
        self.ax2 = self.fig.add_subplot(122)                   # 2D angle plot

        # Labels
        self.ax1.set_xlabel('X (m) - Up/Down')
        self.ax1.set_ylabel('Y (m) - Left/Right')
        self.ax1.set_zlabel('Z (m) - Forward/Backward')
        self.ax2.set_xlabel('Azimuth (deg)')
        self.ax2.set_ylabel('Elevation (deg)')

        # 3D limits
        self.ax1.set_xlim(0, 5)
        self.ax1.set_ylim(-3, 3)
        self.ax1.set_zlim(-2, 2)
        self.ax1.set_box_aspect([1, 1, 1])

        # Arrow length
        self.arrow_length = 1.0

        # Debug
        self.debug_text = plt.figtext(0.02, 0.98, '', fontsize=8, va='top')
        self.last_msg_time = None
        self.msg_count = 0

    def _sph2cart(self, raw_az, raw_el):
        """
        Convert board az/el to Cartesian dx,dy,dz.
        Board: raw_el 0°=up,90°=horizontal; raw_az 0° on -x axis.
        Map to standard: phi=polar from +z: phi=90-raw_el;
        theta=azimuth from +x axis CCW: theta=raw_az+180.
        x = sin(phi)*cos(theta)
        y = sin(phi)*sin(theta)
        z = cos(phi)
        """
        phi = np.deg2rad(90 - raw_el)
        theta = np.deg2rad(raw_az + 180)
        dx = np.sin(phi) * np.cos(theta)
        dy = np.sin(phi) * np.sin(theta)
        dz = np.cos(phi)
        return dx, dy, dz

    def on_connect(self, client, userdata, flags, rc, properties):
        print(f"Connected with result code {rc}")
        client.subscribe("silabs/aoa/#")

    def on_message(self, client, userdata, msg):
        self.last_msg_time = time.strftime('%H:%M:%S')
        self.msg_count += 1

        parts = msg.topic.split('/')
        if len(parts) != 5:
            return
        _, _, data_type, _, tag_id = parts

        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            return

        if data_type == 'position':
            x = payload.get('z', 0)
            y = payload.get('y', 0)
            z = payload.get('x', 0)
            pts = self.positions[tag_id]
            pts.append((x,y,z))
            if len(pts)>100: pts.pop(0)

        elif data_type == 'angle':
            raw_az = payload.get('azimuth', 0)
            raw_el = payload.get('elevation', 0)
            self.angles[tag_id].append((raw_az, raw_el))
            if len(self.angles[tag_id])>100:
                self.angles[tag_id].pop(0)

    def update_plot(self, frame):
        self.ax1.clear(); self.ax2.clear()
        # axes
        self.ax1.quiver(0,0,0, 1,0,0, color='b', arrow_length_ratio=0.1, label='X')
        self.ax1.quiver(0,0,0, 0,1,0, color='g', arrow_length_ratio=0.1, label='Y')
        self.ax1.quiver(0,0,0, 0,0,1, color='r', arrow_length_ratio=0.1, label='Z')

        # trajectories
        for tag, pts in self.positions.items():
            if not pts: continue
            xs,ys,zs = zip(*pts)
            self.ax1.plot(xs,ys,zs, label=f'Tag {tag}')
            self.ax1.scatter(xs[-1],ys[-1],zs[-1], s=50)

        for tag, angs in self.angles.items():
            if not angs: continue
            azs, els = zip(*angs)
            self.ax2.plot(azs,els, label=f'Tag {tag}')
            self.ax2.scatter(azs[-1], els[-1], s=50)
            txt = f"Az: {azs[-1]:.1f}°\nEl: {els[-1]:.1f}°"
            self.ax2.text(0.02,0.98, txt, transform=self.ax2.transAxes,
                          va='top', bbox=dict(facecolor='white',alpha=0.7))

        # limits
        self.ax1.set_xlim(0,5); self.ax1.set_ylim(-3,3); self.ax1.set_zlim(-2,2)
        self.ax1.set_box_aspect([1,1,1])
        self.ax2.set_xlim(-180,180); self.ax2.set_ylim(0,180); self.ax2.grid(True)

        if self.positions or self.angles:
            self.ax1.legend(loc='upper right'); self.ax2.legend(loc='upper right')

        info = (f"Last msg: {self.last_msg_time or 'N/A'}\n"
                f"Msgs: {self.msg_count}\n"
                f"Tags: {list(self.positions.keys())}")
        self.debug_text.set_text(info)

        return self.ax1, self.ax2

    def start(self):
        self.client.connect(self.broker, self.port)
        self.client.loop_start()
        self.ani = FuncAnimation(self.fig, self.update_plot, interval=100,
                                  blit=False, cache_frame_data=False)
        plt.show()
        self.client.loop_stop(); self.client.disconnect()

if __name__ == '__main__':
    AoAVisualizer().start()