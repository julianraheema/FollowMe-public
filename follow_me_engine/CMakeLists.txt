cmake_minimum_required(VERSION 3.0.2)
project(follow_me_engine)

## Compile as C++11, supported in ROS Kinetic and newer
# add_compile_options(-std=c++11)

## Find catkin macros and libraries
## if COMPONENTS list like find_package(catkin REQUIRED COMPONENTS xyz)
## is used, also find other catkin packages
find_package(catkin REQUIRED COMPONENTS
  rospy
  tf2_ros
  tf2_geometry_msgs
  geometry_msgs
  std_srvs
  roscpp
  std_msgs
)

catkin_package()

###########
## Build ##
###########
include_directories(
  ${catkin_INCLUDE_DIRS}
)

add_executable(${PROJECT_NAME}_node src/follow_me_engine_node.cpp)
target_link_libraries(${PROJECT_NAME}_node ${catkin_LIBRARIES})

#############
## Install ##
#############
## Mark executable scripts for installation
catkin_install_python(PROGRAMS
  scripts/follow_me_engine_pynode.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

