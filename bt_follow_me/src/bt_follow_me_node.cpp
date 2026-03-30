#include "ros/ros.h"
#include "geometry_msgs/PoseStamped.h"
#include <mosquitto.h>
#include <string>
#include <sstream>
#include <cctype>
#include <deque>
#include <cmath>
#include <algorithm>

// Adaptive moving average filter class
class AdaptiveMovingAverageFilter {
private:
    std::deque<double> x_buffer;
    std::deque<double> y_buffer;
    std::deque<double> z_buffer;
    std::deque<ros::Time> time_buffer;
    
    size_t min_window_size;
    size_t max_window_size;
    double velocity_threshold;  // m/s
    double noise_threshold;     // m
    
    // Calculate velocity between two points
    double calculate_velocity(const std::deque<double>& buffer, const std::deque<ros::Time>& times, size_t idx1, size_t idx2) {
        double dx = buffer[idx2] - buffer[idx1];
        double dt = (times[idx2] - times[idx1]).toSec();
        return dt > 0 ? std::abs(dx / dt) : 0.0;
    }
    
    // Calculate standard deviation of recent measurements
    double calculate_std_dev(const std::deque<double>& buffer) {
        if (buffer.size() < 2) return 0.0;
        
        double sum = 0.0;
        double sum_sq = 0.0;
        for (double val : buffer) {
            sum += val;
            sum_sq += val * val;
        }
        
        double mean = sum / buffer.size();
        double variance = (sum_sq / buffer.size()) - (mean * mean);
        return std::sqrt(variance);
    }
    
public:
    AdaptiveMovingAverageFilter(size_t min_size = 3, size_t max_size = 10, 
                               double vel_thresh = 0.5, double noise_thresh = 0.1)
        : min_window_size(min_size), max_window_size(max_size),
          velocity_threshold(vel_thresh), noise_threshold(noise_thresh) {}
    
    void add_sample(double x, double y, double z, const ros::Time& time) {
        x_buffer.push_back(x);
        y_buffer.push_back(z);
        z_buffer.push_back(z);
        time_buffer.push_back(time);
        
        // Keep buffer size at max_window_size
        if (x_buffer.size() > max_window_size) {
            x_buffer.pop_front();
            y_buffer.pop_front();
            z_buffer.pop_front();
            time_buffer.pop_front();
        }
    }
    
    void get_average(double& x, double& y, double& z) {
        if (x_buffer.empty()) {
            x = y = z = 0.0;
            return;
        }
        
        // Calculate current velocity and noise levels
        double current_velocity = 0.0;
        if (x_buffer.size() >= 2) {
            current_velocity = std::max({
                calculate_velocity(x_buffer, time_buffer, x_buffer.size()-2, x_buffer.size()-1),
                calculate_velocity(y_buffer, time_buffer, y_buffer.size()-2, y_buffer.size()-1),
                calculate_velocity(z_buffer, time_buffer, z_buffer.size()-2, z_buffer.size()-1)
            });
        }
        
        double current_noise = std::max({
            calculate_std_dev(x_buffer),
            calculate_std_dev(y_buffer),
            calculate_std_dev(z_buffer)
        });
        
        // Determine adaptive window size
        size_t window_size = min_window_size;
        
        // Increase window size if velocity is low
        if (current_velocity < velocity_threshold) {
            window_size = std::min(max_window_size, 
                                 min_window_size + static_cast<size_t>((velocity_threshold - current_velocity) * 10));
        }
        
        // Increase window size if noise is high
        if (current_noise > noise_threshold) {
            window_size = std::min(max_window_size,
                                 window_size + static_cast<size_t>((current_noise - noise_threshold) * 20));
        }
        
        // Calculate moving average with adaptive window
        x = y = z = 0.0;
        size_t actual_window = std::min(window_size, x_buffer.size());
        for (size_t i = x_buffer.size() - actual_window; i < x_buffer.size(); ++i) {
            x += x_buffer[i];
            y += y_buffer[i];
            z += z_buffer[i];
        }
        
        x /= actual_window;
        y /= actual_window;
        z /= actual_window;
    }
};

// Single ROS publisher for all tags
static ros::Publisher position_pub;
// Adaptive moving average filter instance
static AdaptiveMovingAverageFilter* position_filter = nullptr;
// Flag to control whether smoothing is enabled
static bool smoothing_enabled = true;

// Helper to parse a floating-point field from minimal JSON
static bool parse_json_field(const std::string &s, const std::string &key, double &out)
{
    std::string pattern = "\"" + key + "\"";
    size_t pos = s.find(pattern);
    if (pos == std::string::npos)
        return false;
    size_t colon = s.find(':', pos + pattern.size());
    if (colon == std::string::npos)
        return false;
    size_t start = colon + 1;
    while (start < s.size() && (std::isspace((unsigned char)s[start]) || s[start] == '"'))
        start++;
    size_t end = start;
    while (end < s.size() && (std::isdigit((unsigned char)s[end]) || s[end] == '+' || s[end] == '-' || s[end] == '.' || s[end] == 'e' || s[end] == 'E'))
        end++;
    try
    {
        out = std::stod(s.substr(start, end - start));
        return true;
    }
    catch (...)
    {
        return false;
    }
}

// MQTT message callback
void on_mqtt_message(struct mosquitto *mosq, void *userdata, const struct mosquitto_message *message)
{
    std::string topic(message->topic);
    // We are only interested in `silabs/aoa/position/...`
    if (topic.rfind("silabs/aoa/position/", 0) != 0)
        return;
    
    std::string payload((char*)message->payload, message->payloadlen);
    double x_in, y_in, z_in;
    if (!parse_json_field(payload, "x", x_in) || !parse_json_field(payload, "y", y_in) || !parse_json_field(payload, "z", z_in))
        return;
    
    // Add new sample to the filter with current time
    if (position_filter) {
        position_filter->add_sample(x_in, y_in, z_in, ros::Time::now());
    }
    
    // Get position (either smoothed or raw based on setting)
    double x_out, y_out, z_out;
    if (smoothing_enabled && position_filter) {
        position_filter->get_average(x_out, y_out, z_out);
    } else {
        x_out = x_in;
        y_out = y_in;
        z_out = z_in;
    }
    
    geometry_msgs::PoseStamped pose_stamped;
    pose_stamped.header.stamp = ros::Time::now();
    pose_stamped.header.frame_id = "bluetooth_receiver_box";  // You can adjust this as needed

    pose_stamped.pose.position.x = x_out;
    pose_stamped.pose.position.y = -y_out;  // Note: y is still inverted
    pose_stamped.pose.position.z = z_out;

    pose_stamped.pose.orientation.x = 0.0;
    pose_stamped.pose.orientation.y = 0.0;
    pose_stamped.pose.orientation.z = 0.0;
    pose_stamped.pose.orientation.w = 1.0;

    position_pub.publish(pose_stamped);
}

int main(int argc, char **argv) {
    ros::init(argc, argv, "bt_follow_me");
    ros::NodeHandle nh;

    position_pub = nh.advertise<geometry_msgs::PoseStamped>("/spot/bt_follower/pose", 10);

    // Get MQTT parameters
    std::string mqtt_host;
    int mqtt_port;
    nh.param<std::string>("mqtt_host", mqtt_host, "localhost");
    nh.param<int>("mqtt_port", mqtt_port, 1883);
    
    // Get smoothing parameters
    nh.param<bool>("smoothing_enabled", smoothing_enabled, true);
    
    // Get filter parameters
    size_t min_window_size;
    size_t max_window_size;
    double velocity_threshold;
    double noise_threshold;
    
    nh.param<int>("min_window_size", (int&)min_window_size, 3);
    nh.param<int>("max_window_size", (int&)max_window_size, 10);
    nh.param<double>("velocity_threshold", velocity_threshold, 0.5);
    nh.param<double>("noise_threshold", noise_threshold, 0.1);
    
    // Create filter with parameters
    position_filter = new AdaptiveMovingAverageFilter(
        min_window_size,
        max_window_size,
        velocity_threshold,
        noise_threshold
    );
    
    ROS_INFO("Position smoothing is %s", smoothing_enabled ? "enabled" : "disabled");
    ROS_INFO("Filter parameters: min_window=%zu, max_window=%zu, vel_thresh=%.2f m/s, noise_thresh=%.2f m",
             min_window_size, max_window_size, velocity_threshold, noise_threshold);

    // Initialize mosquitto library
    mosquitto_lib_init();
    struct mosquitto *mosq = mosquitto_new(NULL, true, NULL);
    if (!mosq) {
        ROS_ERROR("Failed to create Mosquitto .");
        return 1;
    }
    mosquitto_message_callback_set(mosq, on_mqtt_message);

    if (mosquitto_connect(mosq, mqtt_host.c_str(), mqtt_port, 60) != MOSQ_ERR_SUCCESS) {
        ROS_ERROR("Unable to connect to MQTT broker at %s:%d", mqtt_host.c_str(), mqtt_port);
        mosquitto_destroy(mosq);
        mosquitto_lib_cleanup();
        return 1;
    }

    mosquitto_subscribe(mosq, NULL, "silabs/aoa/position/#", 0);

    ros::Rate rate(50);
    while (ros::ok()) {
        mosquitto_loop(mosq, -1, 1);
        ros::spinOnce();
        rate.sleep();
    }
    
    mosquitto_disconnect(mosq);
    mosquitto_destroy(mosq);
    mosquitto_lib_cleanup();

    // Clean up
    delete position_filter;
    return 0;
}
