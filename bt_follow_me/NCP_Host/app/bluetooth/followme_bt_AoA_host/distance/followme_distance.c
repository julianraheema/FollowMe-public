/***************************************************************************//**
 * @file
 * @brief Distance calculation and RSSI filtering
 *******************************************************************************/

#include "followme_distance.h"
#include "followme_positioning.h"
#include "antenna_array.h"
#include "aoa_parse.h"
#include "math.h"

// Default values if not specified in config
static const float DEFAULT_A = -66.43;
static const float DEFAULT_ETA = 1.63;

// Global parameters read from config
static float g_A = DEFAULT_A;
static float g_eta = DEFAULT_ETA;

enum sl_rtl_error_code followme_distance_init(void)
{
  sl_status_t status;
  float config_value;

  // Try to read A from config, use default if not found
  status = aoa_parse_float_config(&config_value, "A", NULL);
  if (status == SL_STATUS_OK) {
    g_A = config_value;
  }

  // Try to read eta from config, use default if not found
  status = aoa_parse_float_config(&config_value, "eta", NULL);
  if (status == SL_STATUS_OK) {
    g_eta = config_value;
  }

  return SL_RTL_ERROR_SUCCESS;
}

enum sl_rtl_error_code calculate_avg_RSSI(aoa_iq_report_t *iq_report)
{
  enum sl_rtl_error_code ec;

  int rssi_preamble = iq_report->rssi;
  int num_antennas = ANTENNA_ARRAY_MAX_PIN_PATTERN_SIZE;             //for BRD4191A
  int num_ref_samples = ANTENNA_ARRAY_MAX_PATTERN_SIZE - 2;
  int antenna_samples[(num_antennas - 1) * 2];

  double *powers = (double *)malloc((num_antennas) * sizeof(double));
    if (powers == NULL) {
        ec = SL_RTL_ERROR_OUT_OF_MEMORY;
        return ec;
  };

  double *rssi_values = (double *)malloc(num_antennas * sizeof(double));
    if (rssi_values == NULL) {
        free(powers);
        ec = SL_RTL_ERROR_OUT_OF_MEMORY;
        return ec;
  }

  // Skip reference samples
  for (int i = 0; i < ((num_antennas) * 2); i++){
    antenna_samples[i] = iq_report->samples[i + num_ref_samples];
  };

  // Calculate the power for each antenna's IQ pair
  for (int i = 0; i < (num_antennas); i++){
    int I = antenna_samples[i * 2];
    int Q = antenna_samples[i * 2 + 1];
    powers[i] = (double)(I * I + Q * Q);
  }

  double reference_power = powers[0];
  double reference_rssi = (double)rssi_preamble;
  double reference_power_dbm = 10.0 * log10(reference_power);

  // Calculate RSSI for each antenna based on the reference
  for (int i = 0; i < num_antennas; i++) {
        rssi_values[i] = 10.0 * log10(powers[i]) - reference_power_dbm + reference_rssi;
  }

  // Calculate average RSSI
  double sum_rssi = 0.0;
  for (int i = 0; i < num_antennas; i++) {
    sum_rssi += rssi_values[i];
  }

  // Calculate weighted average RSSI
  double rssi_min = rssi_values[0];
  for (int i = 1; i < num_antennas; i++) {
    if (rssi_values[i] < rssi_min) {
      rssi_min = rssi_values[i];
    }
  }

  double denom = 0.0;
  for (int i = 0; i < num_antennas; i++) {
    denom += rssi_values[i] - rssi_min;
  }

  double average_rssi_weighted = 0.0;
  for (int i = 0; i < num_antennas; i++) {
    average_rssi_weighted += ((rssi_values[i] - rssi_min) / denom) * rssi_values[i];
  }
  

  //RSSI threshold filtering
  static int C_threshold = 5;
  static int RSSI_avg_threshold_diff = 5;
  static int RSSI_threshold_diff = 8;
  static double last_valid_rssi = 0.0;
  static int count = 0;

  if (fabs(average_rssi_weighted - rssi_preamble) < RSSI_threshold_diff){
    // Add new RSSI to packet
    if (fabs(average_rssi_weighted - last_valid_rssi) < RSSI_avg_threshold_diff || count > C_threshold){
      count = 0;
      iq_report->avg_rssi = average_rssi_weighted;
      last_valid_rssi = average_rssi_weighted;
    } else {
      // Skip irregular measurement
      count++;
      iq_report->avg_rssi = last_valid_rssi;
    }
  } else {
    // Discard outlier measurement
    iq_report->avg_rssi = last_valid_rssi;
  }

  if (iq_report->avg_rssi == 0){
    iq_report->avg_rssi = rssi_preamble;
  }

  free(powers);
  free(rssi_values);

  ec = SL_RTL_ERROR_SUCCESS;

  return ec;
}

enum sl_rtl_error_code followme_calculate_distance(float rssi, float* distance_out)
{
  enum sl_rtl_error_code ec;

  *distance_out = pow(10, (g_A - rssi) / (10 * g_eta));

  ec = SL_RTL_ERROR_SUCCESS;
  return ec;
}