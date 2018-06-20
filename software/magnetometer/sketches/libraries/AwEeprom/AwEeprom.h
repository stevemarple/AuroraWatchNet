#ifndef AWEEPROM_H
#define AWEEPROM_H

#define EEPROM_MAGIC 0x10
#define EEPROM_MAGIC_STRING "AuroraWatch v1.0"
//                           0123456789abcdef
// eepromWrite=0x10,65,117,114,111,114,97,87,97,116,99,104,32,118,49,46,48
// eepromWrite=0x10,0x41,0x75,0x72,0x6f,0x72,0x61,0x57,0x61,0x74,0x63,0x68,0x20,0x76,0x31,0x2e,0x30

#define EEPROM_HMAC_KEY 0x20
#define EEPROM_HMAC_KEY_SIZE 16

#define EEPROM_SITE_ID 0x30
#define EEPROM_SITE_ID_SIZE 2

// MCP3424 I2C addresses
#define EEPROM_ADC_ADDRESS_LIST 0x32
#define EEPROM_ADC_ADDRESS_LIST_SIZE 3

// MCP3424 I2C channels
#define EEPROM_ADC_CHANNEL_LIST 0x35
#define EEPROM_ADC_CHANNEL_LIST_SIZE 3

#define EEPROM_SD_SELECT 0x38
#define EEPROM_SD_SELECT_SIZE 1

#define EEPROM_USE_SD 0x39
#define EEPROM_USE_SD_SIZE 1

// Comms type
#define EEPROM_COMMS_TYPE 0x3A
#define EEPROM_COMMS_TYPE_SIZE 1

#define EEPROM_COMMS_TYPE_XRF 0
#define EEPROM_COMMS_TYPE_RFM12B 1
#define EEPROM_COMMS_TYPE_W5100_UDP 2

// Radio band, meaning dependent on radio type
#define EEPROM_RADIO_XRF_BAND 0x3B
#define EEPROM_RADIO_XRF_BAND_SIZE 1

// Radio channel, dependent on radio type
// XRF uses one byte, 2 bytes available for RFM12B
#define EEPROM_RADIO_XRF_CHANNEL 0x3C
#define EEPROM_RADIO_XRF_CHANNEL_SIZE 1

// 0x3D spare

#define FLC100_POWER_UP_DELAY_50MS 0x3E
#define FLC100_POWER_UP_DELAY_50MS_SIZE 1

#define EEPROM_RADIO_RFM12B_BAND 0x3F
#define EEPROM_RADIO_RFM12B_BAND_SIZE 1

#define EEPROM_RADIO_RFM12B_CHANNEL 0x40
#define EEPROM_RADIO_RFM12B_CHANNEL_SIZE 2

#define EEPROM_SAMPLING_INTERVAL_16TH_S 0x42
#define EEPROM_SAMPLING_INTERVAL_16TH_S_SIZE 2

// Number of samples to take per sampling interval
#define EEPROM_NUM_SAMPLES 0x44
#define EEPROM_NUM_SAMPLES_SIZE 1

// How to aggregate multiple samples
#define EEPROM_AGGREGATE 0x45
#define EEPROM_AGGREGATE_SIZE 1

// Bit mask values
#define EEPROM_AGGREGATE_USE_MEDIAN 1
#define EEPROM_AGGREGATE_TRIM_SAMPLES 2

// Send all samples?
#define EEPROM_ALL_SAMPLES 0x46
#define EEPROM_ALL_SAMPLES_SIZE 1

// Local/remote node IDs for RFM12B Serial Stream
#define EEPROM_RADIO_LOCAL_ID 0x47
#define EEPROM_RADIO_LOCAL_ID_SIZE 1

#define EEPROM_RADIO_REMOTE_ID 0x48
#define EEPROM_RADIO_REMOTE_ID_SIZE 1

// Maximum number of messages without an acknowledgement
#define EEPROM_MAX_MESSAGES_NO_ACK 0x49
#define EEPROM_MAX_MESSAGES_NO_ACK_SIZE 1

// Maximum number of messages before turning off the LED
#define EEPROM_MAX_MESSAGES_LED 0x4a
#define EEPROM_MAX_MESSAGES_LED_SIZE 1

// MCP7941x calibration value
#define EEPROM_MCP7941X_CAL 0x4b
#define EEPROM_MCP7941X_CAL_SIZE 1

// MCU operating voltage, needed for ADC calculations
#define EEPROM_MCU_VOLTAGE_MV 0x4c
#define EEPROM_MCU_VOLTAGE_MV_SIZE 2

// Divider network for Vin
#define EEPROM_VIN_DIVIDER 0x4e
#define EEPROM_VIN_DIVIDER_SIZE 1

// 0x4f: reserved for possible numerator definition in the Vin divider
// network

#define EEPROM_LOCAL_IP_ADDRESS 0x50
#define EEPROM_LOCAL_IP_ADDRESS_SIZE 4

#define EEPROM_REMOTE_IP_ADDRESS 0x54
#define EEPROM_REMOTE_IP_ADDRESS_SIZE 4

#define EEPROM_LOCAL_IP_PORT 0x58
#define EEPROM_LOCAL_IP_PORT_SIZE 2

#define EEPROM_REMOTE_IP_PORT 0x5a
#define EEPROM_REMOTE_IP_PORT_SIZE 2

#define EEPROM_FLC100_PRESENT 0x5c
#define EEPROM_FLC100_PRESENT_SIZE 1

#define EEPROM_MLX90614_PRESENT 0x5d
#define EEPROM_MLX90614_PRESENT_SIZE 1

#define EEPROM_HIH61XX_PRESENT 0x5e
#define EEPROM_HIH61XX_PRESENT_SIZE 1

#define EEPROM_AS3935_PRESENT 0x5f
#define EEPROM_AS3935_PRESENT_SIZE 1

// Temperature where fan switched on/off (in hundredths deg C)
#define EEPROM_FAN_TEMPERATURE 0x60
#define EEPROM_FAN_TEMPERATURE_SIZE 2

// Hysteresis about the switch point
#define EEPROM_FAN_HYSTERESIS  0x62
#define EEPROM_FAN_HYSTERESIS_SIZE 2

// Pin used for fan control
#define EEPROM_FAN_PIN 0x64
#define EEPROM_FAN_PIN_SIZE 1

// ADC voltage reference
// 0 = AREF, 1 = AVcc, 2 = 1V1, 3 = 2V56
#define EEPROM_ADC_REF_TYPE 0x65
#define EEPROM_ADC_REF_TYPE_SIZE 1

#define EEPROM_ADC_REF_TYPE_EXTERNAL 0
#define EEPROM_ADC_REF_TYPE_AVCC 1
#define EEPROM_ADC_REF_TYPE_INTERNAL1V1 2
#define EEPROM_ADC_REF_TYPE_INTERNAL2V56 3

// Supersedes EEPROM_MCU_VOLTAGE_MV
#define EEPROM_ADC_REF_VOLTAGE_MV 0x66
#define EEPROM_ADC_REF_VOLTAGE_MV_SIZE 2

#define EEPROM_AS3935_AFE_GAIN 0x68
#define EEPROM_AS3935_AFE_GAIN_SIZE 1

#define EEPROM_AS3935_NOISE_FLOOR 0x69
#define EEPROM_AS3935_NOISE_FLOOR_SIZE 1

#define EEPROM_AS3935_WATCHDOG 0x6A
#define EEPROM_AS3935_WATCHDOG_SIZE 1

#define EEPROM_AS3935_MIN_LIGHT 0x6B
#define EEPROM_AS3935_MIN_LIGHT_SIZE 1

#define EEPROM_AS3935_SPIKE_REJ 0x6C
#define EEPROM_AS3935_SPIKE_REJ_SIZE 1

#define EEPROM_AS3935_MASK_DIST 0x6D
#define EEPROM_AS3935_MASK_DIST_SIZE 1

#define EEPROM_AS3935_TUN_CAP 0x6E
#define EEPROM_AS3935_TUN_CAP_SIZE 1

// Anti-dew heater for cloud detector
#define EEPROM_HEATER_PIN 0x6F
#define EEPROM_HEATER_PIN_SIZE 1

#define EEPROM_LOCAL_MAC_ADDRESS 0x70
#define EEPROM_LOCAL_MAC_ADDRESS_SIZE 6

// MCP3424 ADC resolution
#define EEPROM_ADC_RESOLUTION_LIST 0x76
#define EEPROM_ADC_RESOLUTION_LIST_SIZE 3

// MCP3424 ADC gain
#define EEPROM_ADC_GAIN_LIST 0x79
#define EEPROM_ADC_GAIN_LIST_SIZE 3

// 0x7C - 0x7F (inclusive) spare

// Null-terminated
#define EEPROM_REMOTE_HOSTNAME 0x80
#define EEPROM_REMOTE_HOSTNAME_SIZE 64

#define EEPROM_NETMASK 0xC0
#define EEPROM_NETMASK_SIZE 4

#define EEPROM_GATEWAY 0xC4
#define EEPROM_GATEWAY_SIZE 4

#define EEPROM_NUM_DNS 3

#define EEPROM_DNS1 0xC8
#define EEPROM_DNS1_SIZE 4

#define EEPROM_DNS2 0xCC
#define EEPROM_DNS2_SIZE 4

#define EEPROM_DNS3 0xD0
#define EEPROM_DNS3_SIZE 4

#define EEPROM_CONSOLE_BAUD_RATE 0xD4
#define EEPROM_CONSOLE_BAUD_RATE_SIZE 4

// Maximum number of messages without an acknowledgement
#define EEPROM_MAX_TIME_NO_ACK 0xD8
#define EEPROM_MAX_TIME_NO_ACK_SIZE 2

#define EEPROM_DATA_QUALITY_INPUT_PIN 0xDA
#define EEPROM_DATA_QUALITY_INPUT_PIN_SIZE 1

#define EEPROM_DATA_QUALITY_INPUT_ACTIVE_LOW 0xDB
#define EEPROM_DATA_QUALITY_INPUT_ACTIVE_LOW_SIZE 1

// Reserved
//#define EEPROM_DATA_QUALITY_OUTPUT_PIN 0xDC
//#define EEPROM_DATA_QUALITY_OUTPUT_PIN_SIZE 1

#define EEPROM_RIO_PRESENT 0xDD
#define EEPROM_RIO_PRESENT_SIZE 1

#define EEPROM_USE_GNSS 0xDE
#define EEPROM_USE_GNSS_SIZE 1

// The device type ID as defined by RTCx
#define EEPROM_RTCX_DEVICE_TYPE 0xDF
#define EEPROM_RTCX_DEVICE_TYPE_SIZE 1

// The 7 bit device address on the I2C bus
#define EEPROM_RTCX_DEVICE_ADDRESS 0xE0
#define EEPROM_RTCX_DEVICE_ADDRESS_SIZE 1


// ##### ##### ##### ##### ##### #####
// Reserved 0x100 - 0x1FF for settings relating to generic ADC logging
#define EEPROM_GENERIC_ADC_ADDRESS_LIST 0x100
#define EEPROM_GENERIC_ADC_ADDRESS_LIST_SIZE 8


// ##### ##### ##### ##### ##### #####
// Reserved 0x200 - 0x3FF for settings specific to riometer logger

// The housekeeping data is collected before each scan step, of which there is a maximum of 8. For each set of
// housekeeping data define the channel and gain are defined independently for each ADC in use. Other information
// (number of samples, aggregate method, and resolution are common for all ADCs used in a given housekeeping scan).
// etc for each possible ADC (as defined in EEPROM_GENERIC_ADC_ADDRESS_LIST). A mask determines which of the 
// possible 8 ADCs are used for each scan step.

// EEPROM_RIO_HOUSEKEEPING_0_x (0x200 - 0x214)
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST 0x200
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE 8

#define EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST 0x208
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE 8

#define EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES 0x210
#define EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE 2

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE 0x212
#define EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE 1
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION 0x213
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE 1

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK 0x214
#define EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE 1


// The offset where housekeeping scan #1 settings start relative to housekeeping scan #0.
#define EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP 0x20

// EEPROM_RIO_HOUSEKEEPING_1_x (0x220 - 0x234)
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_1_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_1_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_1_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_1_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 1))
#define EEPROM_RIO_HOUSEKEEPING_1_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_2_x (0x240 - 0x254)
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_2_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_2_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_2_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_2_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 2))
#define EEPROM_RIO_HOUSEKEEPING_2_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_3_x (0x260 - 0x274)
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_3_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_3_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_3_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_3_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 3))
#define EEPROM_RIO_HOUSEKEEPING_3_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_4_x (0x280 - 0x294)
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_4_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_4_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_4_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_4_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 4))
#define EEPROM_RIO_HOUSEKEEPING_4_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_5_x (0x2a0 - 0x2b4)
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_5_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_5_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_5_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_5_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 5))
#define EEPROM_RIO_HOUSEKEEPING_5_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_6_x (0x2c0 - 0x2d4)
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_6_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_6_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_6_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_6_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 6))
#define EEPROM_RIO_HOUSEKEEPING_6_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_HOUSEKEEPING_7_x (0x2e0 - 0x2f4)
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_CHANNEL_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_CHANNEL_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_7_ADC_GAIN_LIST (EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_GAIN_LIST_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST_SIZE

#define EEPROM_RIO_HOUSEKEEPING_7_NUM_SAMPLES (EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_NUM_SAMPLES_SIZE EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES_SIZE

// How to aggregate multiple samples
#define EEPROM_RIO_HOUSEKEEPING_7_AGGREGATE (EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_AGGREGATE_SIZE EEPROM_RIO_HOUSEKEEPING_0_AGGREGATE_SIZE
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_HOUSEKEEPING_7_ADC_RESOLUTION (EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_RESOLUTION_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION_SIZE

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_MASK (EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + (EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP * 7))
#define EEPROM_RIO_HOUSEKEEPING_7_ADC_MASK_SIZE EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK_SIZE


// EEPROM_RIO_RIOMETER (0x300 - 0x314)
// The settings for the riometer data follows the same scheme as for housekeeping data. However the settings apply
// for all scan steps.
#define EEPROM_RIO_RIOMETER_ADC_CHANNEL_LIST 0x300
#define EEPROM_RIO_RIOMETER_ADC_CHANNEL_LIST_SIZE 8

#define EEPROM_RIO_RIOMETER_ADC_GAIN_LIST 0x308
#define EEPROM_RIO_RIOMETER_ADC_GAIN_LIST_SIZE 8

#define EEPROM_RIO_RIOMETER_NUM_SAMPLES 0x310
#define EEPROM_RIO_RIOMETER_NUM_SAMPLES_SIZE 2

// How to aggregate multiple samples
#define EEPROM_RIO_RIOMETER_AGGREGATE 0x312
#define EEPROM_RIO_RIOMETER_AGGREGATE_SIZE 1
// Bit mask values are identical to that used for EEPROM_AGGREGATE

#define EEPROM_RIO_RIOMETER_ADC_RESOLUTION 0x313
#define EEPROM_RIO_RIOMETER_ADC_RESOLUTION_SIZE 1

// Use a mask to define which ADCs should be used at each step. If the LSB is set then ADC0 (first in address list) will
// be used. If bit 2^n is set then ADC number n is used.
#define EEPROM_RIO_RIOMETER_ADC_MASK 0x314
#define EEPROM_RIO_RIOMETER_ADC_MASK_SIZE 1




#define EEPROM_RIO_NUM_ROWS 0x320
#define EEPROM_RIO_NUM_ROWS_SIZE 1
#define EEPROM_RIO_NUM_ROWS_MAX 8

#define EEPROM_RIO_NUM_COLUMNS 0x321
#define EEPROM_RIO_NUM_COLUMNS_SIZE 1
#define EEPROM_RIO_NUM_COLUMNS_MAX 8


// MCP3424 I2C addresses
//#define EEPROM_RIO_ADC_ADDRESS_LIST 0x102
//#define EEPROM_RIO_ADC_ADDRESS_LIST_SIZE 8

// MCP3424 I2C channels
//#define EEPROM_RIO_ADC_CHANNEL_LIST 0x10A
//#define EEPROM_RIO_ADC_CHANNEL_LIST_SIZE 8

// Pins controlling row scanning. MSB pin first.
#define EEPROM_RIO_SCAN_PINS 0x322
#define EEPROM_RIO_SCAN_PINS_SIZE 3

#define EEPROM_RIO_PRESAMPLE_DELAY_MS 0x325
#define EEPROM_RIO_PRESAMPLE_DELAY_MS_SIZE 2

#define EEPROM_RIO_ROW_SCAN_INTERVAL_MS 0x327
#define EEPROM_RIO_ROW_SCAN_INTERVAL_MS_SIZE 2

//// MCP3424 ADC resolution. Same for all riometer channels.
//#define EEPROM_RIO_ADC_RESOLUTION 0x119
//#define EEPROM_RIO_ADC_RESOLUTION_SIZE 1

//// MCP3424 ADC gain. Same for all riometer channels.
//#define EEPROM_RIO_ADC_GAIN 0x11A
//#define EEPROM_RIO_ADC_GAIN_SIZE 1

// Address of the MCP23008 IO expander. If address outside of valid range it is not used.
#define EEPROM_RIO_GPIO_ADDRESS 0x329
#define EEPROM_RIO_GPIO_ADDRESS_SIZE 1

#endif
