cmake_minimum_required(VERSION 3.0.2)
project(app_interface_bridge)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  roscpp
  rospy
  std_msgs
)


catkin_package(
#  INCLUDE_DIRS include
#  LIBRARIES cv_follow_me
#  CATKIN_DEPENDS geometry_msgs roscpp rospy std_msgs
#  DEPENDS system_lib
)

###########
## Build ##
###########

## Specify additional locations of header files
## Your package locations should be listed before other locations
include_directories(
# include
  ${catkin_INCLUDE_DIRS}
)


#target_link_libraries(${PROJECT_NAME}_node ${catkin_LIBRARIES})


catkin_install_python(PROGRAMS
  scripts/app_server.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)