#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
import sys

# Values based on the latest config.py provided
STATE_CONTROL_TOPIC = "/cv_follow_state"  # Updated topic name
TOPIC_STATE_IDLE = "idle"
TOPIC_STATE_ACQUIRE = "acquire"
TOPIC_STATE_TRACK = "track"

def state_control_client():
    """
    A simple client to publish state commands to the multi-modal tracker.
    """
    try:
        rospy.init_node('state_control_client', anonymous=True)
    except rospy.exceptions.ROSException as e:
        if "rospy.init_node() has already been called" in str(e):
            rospy.logwarn("Node 'state_control_client' already initialized, proceeding.")
        else:
            rospy.logerr(f"Failed to initialize ROS node: {e}")
            return

    pub = rospy.Publisher(STATE_CONTROL_TOPIC, String, queue_size=10)

    rospy.loginfo(f"State Control Client initialized. Publishing to: {STATE_CONTROL_TOPIC}")
    rospy.loginfo(f"Enter commands: '{TOPIC_STATE_IDLE}', '{TOPIC_STATE_ACQUIRE}', '{TOPIC_STATE_TRACK}', or 'quit' to exit.")

    # It might take a moment for the publisher to establish connection
    rospy.sleep(0.5) # Brief pause to ensure publisher is ready

    while not rospy.is_shutdown():
        try:
            command_input = input("Enter command > ").strip().lower()

            if command_input in ["quit", "exit"]:
                rospy.loginfo("Exiting state control client.")
                break
            
            if command_input in [TOPIC_STATE_IDLE, TOPIC_STATE_ACQUIRE, TOPIC_STATE_TRACK]:
                msg_to_send = String()
                msg_to_send.data = command_input # Command is already lowercase
                
                pub.publish(msg_to_send)
                rospy.loginfo(f"Sent command: '{command_input}'")
            else:
                rospy.logwarn(f"Unknown command: '{command_input}'. Please use '{TOPIC_STATE_IDLE}', '{TOPIC_STATE_ACQUIRE}', '{TOPIC_STATE_TRACK}', or 'quit'.")

        except EOFError: 
            rospy.loginfo("EOF received, exiting state control client.")
            break
        except KeyboardInterrupt: 
            rospy.loginfo("KeyboardInterrupt received, exiting state control client.")
            break
        except Exception as e:
            rospy.logerr(f"An error occurred in client input loop: {e}")
            # Depending on the error, you might want to break or continue
            # For robustness, we'll continue here unless it's a shutdown signal

if __name__ == '__main__':
    try:
        state_control_client()
    except rospy.ROSInterruptException:
        rospy.loginfo("Client shut down due to ROS interrupt.")
    except Exception as e:
        rospy.logerr(f"Unhandled exception in main client: {e}")

