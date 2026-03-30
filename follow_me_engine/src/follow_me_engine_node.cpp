#include "ros/ros.h"
#include "std_msgs/String.h"

int main(int argc, char **argv)

{
    //Initialize the ros
    ros::init(argc, argv, "bt_follow_me_node");
    ros::NodeHandle nh;

    //Loop rate
    ros::Rate loop_rate(10);

    while(ros::ok())
    {
        ROS_INFO("bt_follow_me_node is running...");
        ros::spinOnce();
        loop_rate.sleep();
    }
    return 0;
}