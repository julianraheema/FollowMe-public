#ifndef FOLLOWME_DISTANCE_H
#define FOLLOWME_DISTANCE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <math.h>

#include "aoa_types.h"
#include "sl_rtl_clib_api.h"

// Initialize distance calculation parameters from config
enum sl_rtl_error_code followme_distance_init(void);

// Calculate average RSSI from IQ report
enum sl_rtl_error_code calculate_avg_RSSI(aoa_iq_report_t *iq_report);

// Calculate distance based on RSSI using path loss model
enum sl_rtl_error_code followme_calculate_distance(float rssi, float* distance_out);

#ifdef __cplusplus
};
#endif

#endif // FOLLOWME_DISTANCE_H