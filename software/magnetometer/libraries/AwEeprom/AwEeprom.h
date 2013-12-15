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

#define EEPROM_ADC_ADDRESS_LIST 0x32
#define EEPROM_ADC_ADDRESS_LIST_SIZE 3

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

#endif
