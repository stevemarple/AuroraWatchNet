#ifndef AWEEPROM_H
#define AWEEPROM_H

#define EEPROM_MAGIC 0x10
// "AuroraWatch v1.0"

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

// Radio type
#define EEPROM_RADIO_TYPE 0x3A
#define EEPROM_RADIO_TYPE_SIZE 1

#define EEPROM_RADIO_TYPE_XRF 0
#define EEPROM_RADIO_TYPE_RFM12B 1

// Radio band, meaning dependent on radio type
#define EEPROM_RADIO_BAND 0x3B
#define EEPROM_RADIO_BAND_SIZE 1

// Radio channel, dependent on radio type
// XRF uses one byte, 2 bytes available for RFM12B
#define EEPROM_RADIO_CHANNEL 0x3C
#define EEPROM_RADIO_CHANNEL_SIZE 2

#define FLC100_POWER_UP_DELAY_50MS 0x3E
#define FLC100_POWER_UP_DELAY_50MS_SIZE 1

#endif
