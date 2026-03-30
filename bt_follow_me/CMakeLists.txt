cmake_minimum_required(VERSION 3.0.2)
project(bt_follow_me)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  tf2_ros
  tf2_geometry_msgs
  geometry_msgs
  std_msgs
)

find_package(PkgConfig REQUIRED)
pkg_check_modules(MOSQUITTO REQUIRED libmosquitto)

catkin_package(
  LIBRARIES mqtt
)

# 1) Build AoA host
find_program(MAKE_EXECUTABLE make)
if(NOT MAKE_EXECUTABLE)
  message(FATAL_ERROR "GNU Make not found. Required to build AoA host.")
endif()

set(HOST_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../bt_follow_me/NCP_Host/app/bluetooth/followme_bt_AoA_host")

add_custom_target(followme_bt_AoA_host
  COMMAND ${MAKE_EXECUTABLE}
  WORKING_DIRECTORY ${HOST_DIR}
  COMMENT "Building AoA host..."
)

# 2) Include dirs
include_directories(
  ${catkin_INCLUDE_DIRS}
  ${MOSQUITTO_INCLUDE_DIRS}
)

# 3) Add executable BEFORE linking it
add_executable(bt_follow_me_node src/bt_follow_me_node.cpp)

add_dependencies(bt_follow_me_node followme_bt_AoA_host)

target_link_libraries(bt_follow_me_node
  ${catkin_LIBRARIES}
  ${MOSQUITTO_LIBRARIES}
)
