# -*- coding: iso-8859-15 -*-

import random
import re
import struct

import aurorawatchnet as awn


# Parse the struct pack format string
# Returns array: order, quantity, type. Quantity is not he same as
# returned by struct.calcsize().
def parse_unpack_format(fmt):
    m = re.split('^([@=<>!]?)(\d*)([xcbB?hHiIlLqQfdspP])', fmt)
    if len(m) != 5:
        raise Exception('Bad format: ' + fmt)
    if m[1] == '':
        m[1] = '@' # Native order assumed if not given
    if m[2] == '':
        m[2] = 1
    else:
        m[2] = int(m[2])
    return m[1:4]
    
def safe_eval_mull_100(s):
    return 100 * awn.safe_eval(s)


def convert_bytearray(b):
    return b


def convert_ip_address(s):
    return s.replace('.', ',')


def lookup_address(address):
    for k in eeprom.keys():
        if eeprom[k]['address'] == address:
            return k
    return None

def make_hmac_key(key=None):
    '''Generate a HMAC key, returns an array of ints'''

    # Calculate key length from the pattern, not the size reserved for it
    hmac_key_length = parse_unpack_format(eeprom['hmac_key']['format'])[1]
    if key is None:
        # Create  a random key
        k = []
        for i in range(hmac_key_length):
            k.append(random.randint(0, 255))
        return k
    elif key == 'blank':
        return [0xFF] * hmac_key_length


def get_eeprom_addresses():
    r = {}
    for k in eeprom:
        r[eeprom[k]['address']] = k
    return r


def compute_eeprom_setting_sizes():
    global eeprom
    for k in eeprom:
        s = struct.Struct(eeprom[k]['format'])
        eeprom[k]['size'] = s.size


def find_next_address(address):
    for a in sorted(eeprom_address_to_setting_name.keys()):
        if a > address:
            return a
    return None

    
# EEPROM address details. The key is derived from the C language name
# and becomes the command line option when generating an EEPROM image
# file. The value is a dict with the following entries:
#    address: The first address in EEPROM.
#    format: struct.pack format string
#    default: optional default value. 
#    help: optional help description for command line switch
#    metavar: optional metavar description for command line switch
#    type: optional type parameter given to argparse add_argument()
#    choices: optional choices parameter for argparse.add_argument()
#

eeprom = {
    'magic': {
        'address': 0x10,
        'format': '16c',
        'default': 'AuroraWatch v1.0',
        'help': 'String to identify EEPROM contents and version',
        'metavar': 'STRING'
        },
    'hmac_key': {
        'address': 0x20,
        'format': '16B',
        'help': 'HMAC-MD5 encryption key',
        },
    'site_id': {
        'address': 0x30,
        'format': '<H',
        'help': 'site ID',
        },
    'adc_address_list': {
        'address': 0x32,
        'format': '3B',
        'default': [0x6E, 0x6A, 0x6C],
        'help': 'List of MCP3424 ADC I2C addresses',
        },
    'adc_channel_list': {
        'address': 0x35,
        'format': '3B',
        'default': [1, 1, 1],
        'help': 'List of MCP3424 ADC channel numbers (1-4)'
        },
    'sd_select': {
        'address': 0x38,
        'format': 'B',
        'default': 22, # Built-in microSD card on Calunium v2
        'help': '(micro)SD card select pin'
        },
    'use_sd': {
        'address': 0x39,
        'format': '?',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': '0',
        'help': 'Log to (micro)SD card'
        },
    'comms_type': {
        'address': 0x3A,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1, 2, 255],
        'default': 0,
        'help': 'Comms type; 0=XRF, 1=RFM12B, 2=W5100 UDP'
        },
    'radio_xrf_band': {
        'address': 0x3B,
        'format': 'B',
        'default': 1,
        'choices': list(range(1,7)),
        'help': 'XRF radio band (not implemented)',
        },
    'radio_xrf_channel': {
        'address': 0x3C,
        'format': 'B',
        'help': 'XRF radio channel',
        'metavar': 'CHANNEL_NUMBER',
        },
    'flc100_power_up_delay_50ms': {
        'address': 0x3E,
        'format': 'B',
        'default': 25,
        'help': 'FLC100 power-up delay (units of 50ms)',
        'metavar': 'DURATION_50ms',
        },
    'radio_rfm12b_band': {
        'address': 0x3F,
        'format': 'B',
        'help': 'RFM12B radio band; 1=433MHz, 2=868MHz, 3=915MHz',
        'metavar': 'BAND_NUMBER',
        },
    'radio_rfm12b_channel': {
        'address': 0x40,
        'format': '<H',
        'help': 'RFM12B radio channel',
        'metavar': 'CHANNEL_NUMBER',
        },
    'sampling_interval_16th_s': {
        'address': 0x42,
        'format': '<H',
        'default': 480,
        'help': 'sampling interval in 16th of a second',
        'metavar': 'DURATION'
        },
    'num_samples': {
        'address': 0x44,
        'format': 'B',
        'default': 1,
        'help': 'Number of magnetometer samples to take per sampling interval',
        'metavar': 'NUMBER',
        },
    # How to aggregate multiple samples
    # Bitmask values: 1=median, 2: trimmed
    'aggregate': {
        'address': 0x45,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 1,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
        },
    'all_samples': {
        'address': 0x46,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'help': 'Send all data samples (not just aggregate)',
        },
    'radio_local_id': {
        'address': 0x47,
        'format': 'B',
        'help': 'Local ID for RFM12B radio',
        'metavar': 'LOCAL_ID',
        },
    'radio_remote_id': {
        'address': 0x48,
        'format': 'B',
        'help': 'Remote ID for RFM12B radio',
        'metavar': 'REMOTE_ID',
        },
    'max_messages_no_ack': {
        'address': 0x49,
        'format': 'B',
        'type': int,
        'default': 0,
        'help': 'Maximum number of messages without receiving an acknowledgement before rebooting (DEPRECATED)',
        'metavar': 'NUMBER'
        },
    'max_messages_led': {
        'address': 0x4a,
        'format': 'B',
        'default': '20',
        'help': 'Number of messages before turning off LED',
        'metavar': 'NUMBER'
        },
    'mcp7941x_cal': {
        'address': 0x4b,
        'format': 'b',
        'default': 0,
        'help': 'MCP7941x calibration value',
        'metavar': 'NUMBER'
        },
    'mcu_voltage_mv': {
        'address': 0x4c,
        'format': '<H',
        'default': 3300,
        'help': 'MCU operating voltage (mV)',
        'metavar': 'NUMBER'
        },
    'vin_divider': {
        'address': 0x4e,
        'format': 'B',
        'default': 1,
        'help': 'Input voltage divider',
        'metavar': 'NUMBER'
        },
    # 0x4f: reserved for possible numerator definition in the Vin
    # divider network
    'local_ip_address': {
        'address': 0x50,
        'format': '4B',
        'type': convert_ip_address,
        'default': [0, 0, 0, 0],
        'help': 'Local IP address',
        'metavar': 'IP_ADDRESS'
        },
    'remote_ip_address': {
        'address': 0x54,
        'format': '4B',
        'type': convert_ip_address,
        'default': [255, 255, 255, 255],
        'help': 'Remote IP address',
        'metavar': 'IP_ADDRESS'
        },
    'local_ip_port': {
        'address': 0x58,
        'format': '<H',
        'default': 6588,
        'help': 'Local IP port',
        'metavar': 'NUMBER'
        },
    'remote_ip_port': {
        'address': 0x5a,
        'format': '<H',
        'default': 6588,
        'help': 'Remote IP port',
        'metavar': 'NUMBER'
        },
    'flc100_present': {
        'address': 0x5c,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if FLC100 sensor(s) fitted',
    },
    'mlx90614_present': {
        'address': 0x5d,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if MLX90614 IR temperature sensor fitted',
    },
    'hih61xx_present': {
        'address': 0x5e,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if HIH61xx humidity sensor fitted',
    },
    'as3935_present': {
        'address': 0x5f,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if AS3935 lightning sensor fitted',
    },
    'fan_temperature': {
        'address': 0x60,
        'format': '<h',
        'type': safe_eval_mull_100,
        'default': 3500,
        'help': 'Fan temperature setpoint (deg C)',
    },
    'fan_temperature_hysteresis': {
        'address': 0x62,
        'format': '<H',
        'type': safe_eval_mull_100,
        'default': 250,
        'help': 'Fan temperature setpoint hysteresis (deg C)',
    },
    'fan_pin': {
        'address': 0x64,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 8,
        'help': 'Fan control pin',
    },
    'adc_ref_type': {
        'address': 0x65,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 1,
        'help': 'ADC reference type; 0=Aref, 1=AVcc (default), 2=1V1, 3=2V56',
    },
    'adc_ref_voltage_mv': {
        'address': 0x66,
        'format': '<H',
        'type': awn.safe_eval,
        'default': 3300,
        'help': 'ADC reference voltage (mV)',
    },
    # Support for AS3935 to be added
    

    'heater_pin': {
        'address': 0x6f,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 18,
        'help': 'Heater control pin',
    },
    'local_mac_address': {
        'address': 0x70,
        'format': '6B',
        'default': [0x02, 0x00, 0x00, 0x00, 0x00, 0x00],
        'help': 'Local MAC address',
        'metavar': 'MAC_ADDRESS'
        },
    'adc_resolution_list': {
        'address': 0x76,
        'format': '3B',
        'default': [18, 18, 18],
        'help': 'List of MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
        },
    'adc_gain_list': {
        'address': 0x79,
        'format': '3B',
        'default': [1, 1, 1],
        'help': 'List of MCP3424 ADC gain',
        'metavar': 'GAIN'
        },
    'remote_hostname': {
        'address': 0x80,
        'format': '64s',
        'type': convert_bytearray,
        'help': 'Remote hostname',
        'metavar': 'HOSTNAME'
        },
    'netmask': {
        'address': 0xc0,
        'format': '4B',
        'type': convert_ip_address,
        'default': [255, 255, 255, 0],
        'help': 'Network mask',
        },
    'gateway': {
        'address': 0xc4,
        'format': '4B',
        'type': convert_ip_address,
        'default': [0, 0, 0, 0],
        'help': 'Network gateway IP',
        'metavar': 'IP_ADDRESS',
        },
    'dns1': {
        'address': 0xc8,
        'format': '4B',
        'type': convert_ip_address,
        'default': [8, 8, 8, 8], # Google primary public DNS server
        'help': 'Primary DNS',
        'metavar': 'IP_ADDRESS',
        },
    'dns2': {
        'address': 0xcc,
        'format': '4B',
        'type': convert_ip_address,
        'default': [8, 8, 4, 4], # Google secondary public DNS server
        'help': 'Secondary DNS',
        'metavar': 'IP_ADDRESS',
        },
    'dns3': {
        'address': 0xd0,
        'format': '4B',
        'type': convert_ip_address,
        'default': [0, 0, 0, 0],
        'help': 'Tertiary DNS',
        'metavar': 'IP_ADDRESS',
        },
    'console_baud_rate': {
        'address': 0xd4,
        'format': '<I',
        'type': int,
        'default': 115200,
        'help': 'Console baud rate',
        'metavar': 'BAUD',
        },
    'max_time_no_ack': {
        'address': 0xd8,
        'format': 'H',
        'type': int,
        'default': 3 * 3600,
        'help': 'Maximum time (in seconds) without receiving an acknowledgement before rebooting',
        'metavar': 'NUMBER',
        },

    'data_quality_input_pin': {
        'address': 0xda,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 14,
        'help': 'Data quality input pin',
        },
    'data_quality_input_active_low': {
        'address': 0xdb,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if input is active low',
        },
    # Reserved
    # 'data_quality_output_pin': {
    #     'address': 0xdc,
    #     'format': 'B',
    #     'type': awn.safe_eval,
    #     'default': 255,
    #     'help': 'Data quality output pin',
    #     },

    'rio_present': {
        'address': 0xdd,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if riometer ADC board is used',
    },
    'use_gnss': {
        'address': 0xde,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1],
        'default': True,
        'help': 'Flag indicating if GNSS should be used whenever possible',
    },
    'rtcx_device_type': {
        'address': 0xdf,
        'format': 'B',
        'type': awn.safe_eval,
        'choices': [0, 1, 2, 255],
        'default': 255,
        'help': 'RTCx device type (0=DS1307, 1=MCP7941x, 2=PCF85263, 255=auto)',
    },
    'rtcx_device_address': {
        'address': 0xe0,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 255,
        'help': '7 bit I2C address for RTCx device',
    },
    'gnss_default_baud_rate': {
        'address': 0xe1,
        'format': '<I',
        'type': int,
        'choices': [4800, 9600, 19200, 38400, 76800, 115200, 230400],
        'default': 115200,
        'help': 'Default GNSS module baud rate after power-on',
    },
    'gnss_desired_baud_rate': {
        'address': 0xe5,
        'format': '<I',
        'type': int,
        'choices': [4800, 9600, 19200, 38400, 76800, 115200, 230400],
        'default': 115200,
        'help': 'Desired GNSS module baud rate after configuration',
    },

    # Reserved 0x100 - 0x1FF for settings relating to generic ADC logging
    'generic_adc_address_list': {
        'address': 0x100,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F],
        'help': 'List of MCP3424 ADC I2C addresses',
    },

    # Reserved 0x200 - 0x3FF for settings specific to riometer logger

    # Riometer housekeeping #0 (0x200 - 0x214)
    # Default to recording Vin and +5V only (ADC1 and ADC2)
    'rio_housekeeping_0_adc_channel_list': {
        'address': 0x200,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [2, 2, 2, 2, 2, 2, 2, 2],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_0_adc_gain_list': {
        'address': 0x208,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_0_num_samples': {
        'address': 0x210,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_0_aggregate': {
        'address': 0x212,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_0_adc_resolution': {
        'address': 0x213,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_0_adc_mask': {
        'address': 0x214,
        'format': 'B',
        'default': 0b00000011,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },

    # Riometer housekeeping #1 (0x220 - 0x234)
    # Default to measuring temperature on ADC board only (ADC3)
    'rio_housekeeping_1_adc_channel_list': {
        'address': 0x220,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [2, 2, 2, 2, 2, 2, 2, 2],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_1_adc_gain_list': {
        'address': 0x228,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_1_num_samples': {
        'address': 0x230,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_1_aggregate': {
        'address': 0x232,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_1_adc_resolution': {
        'address': 0x233,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_1_adc_mask': {
        'address': 0x234,
        'format': 'B',
        'default': 0b00000100,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },

    # Riometer housekeeping #2 (0x240 - 0x254)
    'rio_housekeeping_2_adc_channel_list': {
        'address': 0x240,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_2_adc_gain_list': {
        'address': 0x248,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_2_num_samples': {
        'address': 0x250,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_2_aggregate': {
        'address': 0x252,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_2_adc_resolution': {
        'address': 0x253,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_2_adc_mask': {
        'address': 0x254,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    
    # Riometer housekeeping #3 (0x260 - 0x274)
    'rio_housekeeping_3_adc_channel_list': {
        'address': 0x260,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_3_adc_gain_list': {
        'address': 0x268,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_3_num_samples': {
        'address': 0x270,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_3_aggregate': {
        'address': 0x272,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_3_adc_resolution': {
        'address': 0x273,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_3_adc_mask': {
        'address': 0x274,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    
    # Riometer housekeeping #4 (0x280 - 0x294)
    'rio_housekeeping_4_adc_channel_list': {
        'address': 0x280,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_4_adc_gain_list': {
        'address': 0x288,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_4_num_samples': {
        'address': 0x290,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_4_aggregate': {
        'address': 0x292,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_4_adc_resolution': {
        'address': 0x293,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_4_adc_mask': {
        'address': 0x294,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    
    # Riometer housekeeping #5 (0x2a0 - 0x2b4)
    'rio_housekeeping_5_adc_channel_list': {
        'address': 0x2a0,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_5_adc_gain_list': {
        'address': 0x2a8,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_5_num_samples': {
        'address': 0x2b0,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_5_aggregate': {
        'address': 0x2b2,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_5_adc_resolution': {
        'address': 0x2b3,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_5_adc_mask': {
        'address': 0x2b4,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    
    # Riometer housekeeping #6 (0x2c0 - 0x2d4)
    'rio_housekeeping_6_adc_channel_list': {
        'address': 0x2c0,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_6_adc_gain_list': {
        'address': 0x2c8,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_6_num_samples': {
        'address': 0x2d0,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_6_aggregate': {
        'address': 0x2d2,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_6_adc_resolution': {
        'address': 0x2d3,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_6_adc_mask': {
        'address': 0x2d4,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    
    # Riometer housekeeping #7 (0x2e0 - 0x2f4)
    'rio_housekeeping_7_adc_channel_list': {
        'address': 0x2e0,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [4, 4, 4, 4, 4, 4, 4, 4],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_housekeeping_7_adc_gain_list': {
        'address': 0x2e8,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_housekeeping_7_num_samples': {
        'address': 0x2f0,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_housekeeping_7_aggregate': {
        'address': 0x2f2,
        'format': 'B',
        'type': int,
        'default': 0,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_housekeeping_7_adc_resolution': {
        'address': 0x2f3,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_housekeeping_7_adc_mask': {
        'address': 0x2f4,
        'format': 'B',
        'default': 0,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },

    # Riometer data (0x300 - 0x314)
    # The settings for the riometer data follows the same scheme as for housekeeping data. However the settings apply
    # for all scan steps.
    'rio_riometer_adc_channel_list': {
        'address': 0x300,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC I2C addresses',
    },
    'rio_riometer_adc_gain_list': {
        'address': 0x308,
        'format': '8B',
        'type': awn.safe_eval,
        'default': [1, 1, 1, 1, 1, 1, 1, 1],
        'help': 'List of MCP3424 ADC PGA gain values',
    },
    'rio_riometer_num_samples': {
        'address': 0x310,
        'format': 'H',
        'type': int,
        'default': 1,
        'help': 'Number of riometer data samples to take per sampling interval',
    },
    'rio_riometer_aggregate': {
        'address': 0x312,
        'format': 'B',
        'type': int,
        'default': 1,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
    },
    'rio_riometer_adc_resolution': {
        'address': 0x313,
        'format': 'B',
        'default': 14,
        'help': 'MCP3424 ADC resolution (bits)',
        'metavar': 'BITS'
    },
    'rio_riometer_adc_mask': {
        'address': 0x314,
        'format': 'B',
        'default': 0xff,
        'help': 'Mask indicating which ADCs should be used for sampling riometer data (LSB = first ADC in list)',
    },
    # Generic riometer information
    'rio_num_rows': {
        'address': 0x320,
        'format': 'B',
        'type': int,
        'default': 8,
        'choices': list(range(1,8)),
        'help': 'Number of riometer rows',
    },
    'rio_num_columns': {
        'address': 0x321,
        'format': 'B',
        'type': int,
        'default': 8,
        'choices': list(range(1, 8)),
        'help': 'Number of riometer columns',
    },
    'rio_scan_pins': {
        'address': 0x322,
        'format': '3B',
        'type': awn.safe_eval,
        'default': [255, 255, 255], # Off
        'help': 'GPIO pin numbers for scan control',
    },
    'rio_presample_delay_ms': {
        'address': 0x325,
        'format': 'H',
        'type': int,
        'default': 10,
        'help': 'Delay before riometer sampling starts (ms)',
        'metavar': 'MILLISECONDS',
    },
    'rio_row_scan_interval_ms': {
        'address': 0x327,
        'format': 'H',
        'type': int,
        'default': 120,
        'help': 'Interval between riometer row scans (ms)',
        'metavar': 'MILLISECONDS',
    },
    'rio_gpio_address': {
        'address': 0x329,
        'format': 'B',
        'type': awn.safe_eval,
        'default': 255,
        'help': '7 bit I2C address for riometer MCP23008 IO expander',
    },
    'rio_scan_mapping': {
        'address': 0x32a,
        'format': '8B',
        'type': awn.safe_eval,
        'default': list(range(8)),
        'help': 'Map internal riometer scan number (0-7) to 3 bit output value',
    },

}

compute_eeprom_setting_sizes()
eeprom_address_to_setting_name = get_eeprom_addresses()
