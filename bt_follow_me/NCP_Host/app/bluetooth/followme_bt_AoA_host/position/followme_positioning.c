/***************************************************************************//**
 * @file
 * @brief Single locator positioning calculation, combining AoA + RSSI
 *******************************************************************************/

#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

#include "followme_distance.h"
#include "followme_positioning.h"
#include "aoa_angle_config.h"
#include "app_log.h"
#include "app_assert.h"

enum sl_rtl_error_code followme_position(aoa_state_t *aoa_state,
                                         aoa_iq_report_t *iq_report,
                                         aoa_angle_t *angle,
                                         aoa_position_t *position,
                                         aoa_id_t config_id,
                                         aoa_angle_mode_t angle_mode)
{
  enum sl_rtl_error_code ec;
  
  if (angle_mode == RTL) {

    // Average RSSI over all antennas calculation
    ec = calculate_avg_RSSI(iq_report);

    // Calculate AoA using the provided AoA state and IQ report.
    ec = aoa_calculate(aoa_state, iq_report, angle, config_id);

    // Check if the estimation is still in progress.
    if (ec == SL_RTL_ERROR_ESTIMATION_IN_PROGRESS) {
      // No valid angles are available yet.
      return ec;
    }

      // Ensure that the angle calculation was successful.
      app_assert(ec == SL_RTL_ERROR_SUCCESS, "[E: %d] Failed to calculate angle." APP_LOG_NL, ec);

} else {
    // Future AoA algorithms imple
}
  
  //call na position_calculate
  ec = followme_position_calculate(aoa_state, 
                                   angle,
                                   position,
                                   config_id,
                                   iq_report);

  return ec;
}

enum sl_rtl_error_code followme_position_calculate(aoa_state_t *aoa_state,
                                                   aoa_angle_t *angle,
                                                   aoa_position_t *position,
                                                   aoa_id_t config_id,
                                                   aoa_iq_report_t *iq_report)
{
  enum sl_rtl_error_code ec;

  float x;
  float y;
  float z;
  float compound;
  float phi, theta, rho;
  static float sum_x, stdev_x;
  static float sum_y, stdev_y;
  static float sum_z, stdev_z;
  static float mean_x, mean_y, mean_z;
  static unsigned int n_pos;

  n_pos++;

  //Spherical coordinates
  phi = 90 - (angle->elevation);
  theta = 180 + (angle->azimuth);
  rho = (angle->distance);

  //Position calculate
  x = rho*sin(phi * M_PI / 180.0) * cos(theta * M_PI / 180.0);
  y = rho*sin(phi * M_PI / 180.0) * sin(theta * M_PI / 180.0);
  z = rho*cos(phi * M_PI / 180.0);

  //Compound angle calculate
  compound = acos(sin(theta * M_PI / 180.0) * sin(phi * M_PI / 180.0)) * (180.0 / M_PI);
  
  //Assign values
  position->x = x;
  position->y = y;
  position->z = z;
  position->compound = compound;
  position->rssi = iq_report->rssi;
  position->avg_rssi = iq_report->avg_rssi;

  //Standard deviation calculate, first 10 data points rejected
  sum_x += x;
  mean_x = sum_x/(n_pos);

  sum_y += y;
  mean_y = sum_y/(n_pos);

  sum_z += z;
  mean_z = sum_z/(n_pos);

  if (n_pos > 10){
    stdev_x = sqrt((pow((x - mean_x),2))/ (n_pos-1));
    stdev_y = sqrt((pow((y - mean_y),2))/ (n_pos-1));
    stdev_z = sqrt((pow((z - mean_z),2))/ (n_pos-1));
    position->x_stdev = stdev_x;
    position->y_stdev = stdev_y;
    position->z_stdev = stdev_z;
  }

  ec = SL_RTL_ERROR_SUCCESS;
  return ec;
}