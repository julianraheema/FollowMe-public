#!/usr/bin/env python
import rospy
import math
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PoseStamped, Twist
from std_srvs.srv import SetBool, SetBoolResponse, Trigger, TriggerRequest, TriggerResponse
from collections import deque
from std_msgs.msg import String

class VelocityFollower(object):
    def __init__(self):
        rospy.init_node('follow_me_engine')

        # Parameters
        self.k_rho = rospy.get_param('~k_rho', 0.6)
        self.k_alpha = rospy.get_param('~k_alpha', 1.0)
        self.desired_distance = rospy.get_param('~desired_distance', 1.0)
        self.max_lin_vel = rospy.get_param('~max_lin_vel', 1.0)
        self.max_ang_vel = rospy.get_param('~max_ang_vel', 1.0)
        self.distance_tolerance = rospy.get_param('~distance_tolerance', 0.5)
        self.smoothing_window = rospy.get_param('~smoothing_window', 1)
        self.last_pose_time = rospy.Time.now()

        self.use_bt = False
        self.use_cv = False

        self.tf_buffer = tf2_ros.Buffer()
        tf2_ros.TransformListener(self.tf_buffer)

        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)

        self.pose_buffer = deque(maxlen=self.smoothing_window)
        self.last_cmd = Twist()

        rospy.Subscriber('/spot/cv_follower/pose', PoseStamped, self.on_cv_pose)
        rospy.Subscriber('/spot/bt_follower/pose', PoseStamped, self.on_bt_pose)

        rospy.Service('/enable_bt_follower', SetBool, self.set_bt_follower)
        rospy.Service('/enable_cv_follower', SetBool, self.set_cv_follower)
        rospy.Service('/cv_follow_image_acquire', Trigger, self.set_cv_state)

        self.state_pub = rospy.Publisher('/cv_follow_state', String, queue_size=10)
        # self.state_pub.publish("idle")

        # Timer for control loop at 20 Hz
        self.control_timer = rospy.Timer(rospy.Duration(1.0 / 30), self.control_loop)

        rospy.loginfo("Velocity follower ready.")
        rospy.spin()

    def set_bt_follower(self, req):
        #TODO
        # Add bt_control_loop logic of robot moving based on Bluetooth.
        pass

    def set_cv_follower(self, req):
        self.use_cv = req.data
        if self.use_cv:
            if not hasattr(self, 'control_timer') or self.control_timer is None:
                self.control_timer = rospy.Timer(rospy.Duration(1.0 / 30), self.control_loop)
                state = "track"
                self.state_pub.publish(state)
        else:
            if hasattr(self, 'control_timer') and self.control_timer is not None:
                state = "idle"
                self.state_pub.publish(state)
                self.control_timer.shutdown()
                self.control_timer = None

        return SetBoolResponse(success=True, message="CV follower " + ("enabled" if self.use_cv else "disabled"))
    
    def set_cv_state(self, req):
        rospy.loginfo("Trigger acquire image service called")
        state_m = "acquire"
        self.state_pub.publish(state_m)
        return TriggerResponse(success=True, message="Operation completed")

    def on_cv_pose(self, msg):
        if self.use_cv:
            self._store_pose(msg)

    def on_bt_pose(self, msg):
        if self.use_bt:
            self._store_pose(msg)

    def _store_pose(self, msg):
        try:
            target = self.tf_buffer.transform(msg, 'base_link', rospy.Duration(0.2))
            self.pose_buffer.append(target)
            self.last_pose_time = rospy.Time.now()
        except (tf2_ros.LookupException,
                tf2_ros.ExtrapolationException,
                tf2_ros.ConnectivityException) as e:
            rospy.logwarn_throttle(5, "TF error: %s", e)

    def _get_smoothed_pose(self):
        if not self.pose_buffer:
            return None
        avg_x = sum(p.pose.position.x for p in self.pose_buffer) / len(self.pose_buffer)
        avg_y = sum(p.pose.position.y for p in self.pose_buffer) / len(self.pose_buffer)
        return avg_x, avg_y

    def control_loop(self, event):
        if rospy.Time.now() - self.last_pose_time > rospy.Duration(1.5) and self.use_cv:
            rospy.logwarn_throttle(1, "No image pose received for over 3 seconds. Stopping robot.")
            cmd = Twist()  # zero velocity
            self.cmd_pub.publish(cmd)
            self.last_cmd = cmd
            return

        if self.use_cv == "disabled":
            return
        
        pose = self._get_smoothed_pose()
        if pose is None:
            return

        x, y = pose
        rho = math.hypot(x, y)
        alpha = math.atan2(y, x)

        cmd = Twist()

        # Compute distance error
        distance_error = rho - self.desired_distance

        distance_ok = distance_error <= self.distance_tolerance
        angle_ok = abs(alpha) <= 0.087

        if not distance_ok or not angle_ok:
            distance_ratio = max(0.0, min(1.0, distance_error / 1.0))
            scaled_lin = self.k_rho * distance_error * distance_ratio
            scaled_ang = self.k_alpha * alpha

            # Clamp velocities
            cmd.linear.x = max(-self.max_lin_vel, min(self.max_lin_vel, scaled_lin))
            cmd.angular.z = max(-self.max_ang_vel, min(self.max_ang_vel, scaled_ang))

            # min velocity threshold
            if abs(cmd.linear.x) < 0.1:
                cmd.linear.x = 0.0
            if abs(cmd.angular.z) < 0.1:
                cmd.angular.z = 0.0

            # Smooth velocity transitions
            cmd.linear.x = self._ramp(self.last_cmd.linear.x, cmd.linear.x, 0.1)
            cmd.angular.z = self._ramp(self.last_cmd.angular.z, cmd.angular.z, 0.1)

            self.cmd_pub.publish(cmd)
            self.last_cmd = cmd
        else:
            # Inside tolerance -> stop
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            self.cmd_pub.publish(cmd)
            self.last_cmd = cmd


    def _ramp(self, last, target, max_delta):
        delta = target - last
        delta = max(-max_delta, min(max_delta, delta))
        return last + delta

if __name__ == '__main__':
    try:
        VelocityFollower()
    except rospy.ROSInterruptException:
        pass
