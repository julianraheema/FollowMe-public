#!/usr/bin/env python3

import threading
import json
from flask import Flask, request
import rospy
from geometry_msgs.msg import Twist
from wsgiref.simple_server import make_server, WSGIRequestHandler
from std_srvs.srv import SetBool, Trigger, TriggerRequest, SetBoolRequest

app = Flask(__name__)
_httpd = None  # will hold our HTTP server instance

# publisher and watchdog state (module‐level for simplicity)
_pub = None
_last_cmd_time = None
_watchdog_triggered = False

def make_twist(linear_x=0.0, linear_y=0.0, angular_z=0.0):
    t = Twist()
    t.linear.x = linear_x
    t.linear.y = linear_y
    t.angular.z = angular_z
    return t

@app.route('/post_action', methods=['POST'])
def post_action():
    global _last_cmd_time, _watchdog_triggered

    data = request.data.decode('utf-8')
    rospy.loginfo("Received HTTP: %s", data)

    # read speeds from params
    lin_speed = rospy.get_param('~linear_speed', 1.5)
    ang_speed = rospy.get_param('~angular_speed', 1.5)

    # command Twist mapping
    CMD_MAP = {
        'up':     make_twist(linear_x= lin_speed),
        'down':   make_twist(linear_x=-lin_speed),
        'left':   make_twist(linear_y= lin_speed),
        'right':  make_twist(linear_y=-lin_speed),
        'lrotate':  make_twist(angular_z= ang_speed),
        'rrotate': make_twist(angular_z=-ang_speed),
    }

    cmd_obj = json.loads(data)
    action = cmd_obj.get('action', '').strip().lower()

    # if it's a velocity command
    if action in CMD_MAP:
        twist = CMD_MAP[action]
        _pub.publish(twist)
        rospy.loginfo("Published cmd_vel %s: %s", action, twist)

        # reset watchdog
        _last_cmd_time = rospy.Time.now()
        _watchdog_triggered = False
        return "OK", 200

    # otherwise treat as a service
    _watchdog_triggered = False
    call_service(cmd_obj.get('action', ''))
    return "OK", 200

def _run_flask():
    global _httpd
    _httpd = make_server('0.0.0.0', 5000, app, handler_class=WSGIRequestHandler)
    rospy.loginfo("HTTP server listening on http://0.0.0.0:5000/post_action")
    _httpd.serve_forever()

def _shutdown_flask():
    if _httpd:
        rospy.loginfo("Shutting down HTTP server...")
        _httpd.shutdown()

def watchdog_cb(event):
    """Called at fixed rate to check for timeout."""
    global _last_cmd_time, _watchdog_triggered

    if _last_cmd_time is None:
        # no commands have ever arrived
        return

    elapsed = rospy.Time.now() - _last_cmd_time
    if elapsed > rospy.Duration(1):
        if not _watchdog_triggered:
            # publish zero-velocity once
            rospy.logwarn("Watchdog timeout! %0.3fs since last cmd — stopping", elapsed.to_sec())
            _pub.publish(make_twist(0.0, 0.0, 0.0))
            _watchdog_triggered = True

def call_service(service):
    global _last_cmd_time
    rospy.loginfo("Calling service: %s", service)
    _last_cmd_time = None
    svc = service.strip()
    # map service strings to topics & types
    svc_map = {
        "claim":         ('/spot/claim', Trigger,      TriggerRequest()),
        "release":       ('/spot/release', Trigger,    TriggerRequest()),
        "poweron":      ('/spot/power_on', Trigger,   TriggerRequest()),
        "poweroff":     ('/spot/power_off', Trigger,  TriggerRequest()),
        "stand":         ('/spot/stand', Trigger,      TriggerRequest()),
        "sit":           ('/spot/sit', Trigger,        TriggerRequest()),
        "qrfollow":     ('/spot/allow_fiducial_follow', SetBool, SetBoolRequest(data=True)),
        "qrunfollow":   ('/spot/allow_fiducial_follow', SetBool, SetBoolRequest(data=False)),
        "cvfollow":     ('/enable_cv_follower', SetBool, SetBoolRequest(data=True)),
        "cvacquire":     ('/cv_follow_image_acquire', Trigger, TriggerRequest()),
        "cvunfollow":   ('/enable_cv_follower', SetBool, SetBoolRequest(data=False)),
        "btfollow":     ('/enable_bt_follower', SetBool, SetBoolRequest(data=True)),
        "btunfollow":   ('/enable_bt_follower', SetBool, SetBoolRequest(data=False)),
        "freeze":   ('/spot/allow_motion', SetBool, SetBoolRequest(data=False)),
        "unfreeze":   ('/spot/allow_motion', SetBool, SetBoolRequest(data=True)),
    }

    key = svc.lower()
    if key not in svc_map:
        rospy.logwarn("Unknown service command '%s'", service)
        return
    _last_cmd_time = None
    topic, srv_type, req = svc_map[key]
    rospy.wait_for_service(topic)
    try:
        proxy = rospy.ServiceProxy(topic, srv_type)
        resp = proxy(req)
        if getattr(resp, 'success', True):
            rospy.loginfo("%s succeeded: %s", service, getattr(resp, 'message', ''))
        else:
            rospy.logwarn("%s failed: %s", service, getattr(resp, 'message', ''))
    except rospy.ServiceException as e:
        rospy.logerr("Service call '%s' exception: %s", service, e)

def main():
    global _pub, _last_cmd_time

    rospy.init_node('post_action_node')

    # set up publisher
    _pub = rospy.Publisher('/spot/cmd_vel', Twist, queue_size=1)

    # set up watchdog timer at 10Hz
    rospy.Timer(rospy.Duration(0.1), watchdog_cb)

    # launch Flask in a background thread
    t = threading.Thread(target=_run_flask)
    t.daemon = True
    t.start()

    # ensure HTTP server stops when ROS shuts down
    rospy.on_shutdown(_shutdown_flask)

    rospy.loginfo("post_action_node is up. Press Ctrl-C to exit.")
    rospy.spin()

if __name__ == '__main__':
    main()
