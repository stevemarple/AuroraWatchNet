# -*- coding: iso-8859-15 -*-

import random
import re

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
    

def safe_eval(s):
    '''Like eval but prevent access to builtins and locals.

    Certain safe builtins are permitted, including True and False.'''
    return eval(s, {'__builtins__': {'True': True,
                                     'False': False}}, {})


def safe_eval_mull_100(s):
    return 100 * safe_eval(s)


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
                             
# EEPROM address details. The key is derived from the C language name
# and becomes the command line option when generating an EEPROM image
# file. The value is a dict with the following entries:
#    address: The first address in EEPROM.
#    format: struct.pack format string
#    default: optional default value. 
#    help: optional help description for command line switch
#    metavar: optional metavar description for command line switch
#    type: optional type parameter for argparse.add_argument()
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
        'type': safe_eval,
        'choices': [0, 1],
        'default': '0',
        'help': 'Log to (micro)SD card'
        },
    'comms_type': {
        'address': 0x3A,
        'format': 'B',
        'type': safe_eval,
        'choices': [0, 1, 2, 255],
        'default': 0,
        'help': 'Comms type; 0=XRF, 1=RFM12B, 2=W5100 UDP'
        },
    'radio_xrf_band': {
        'address': 0x3B,
        'format': 'B',
        'default': 1,
        'choices': range(1,7),
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
        'type': safe_eval,
        'default': 1,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
        },
    'all_samples': {
        'address': 0x46,
        'format': 'B',
        'type': safe_eval,
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
        'default': '0',
        'help': 'Number of messages without receiving an ACK before rebooting',
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
        'default': [192, 168, 1, 240],
        'help': 'Local IP address',
        'metavar': 'IP_ADDRESS'
        },
    'remote_ip_address': {
        'address': 0x54,
        'format': '4B',
        'type': convert_ip_address,
        'default': [192, 168, 1, 241],
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
        'type': safe_eval,
        'choices': [0, 1],
        'default': True,
        'help': 'Flag indicating if FLC100 sensor(s) fitted',
    },
    'mlx90614_present': {
        'address': 0x5d,
        'format': 'B',
        'type': safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if MLX90614 IR temperature sensor fitted',
    },
    'hih61xx_present': {
        'address': 0x5e,
        'format': 'B',
        'type': safe_eval,
        'choices': [0, 1],
        'default': False,
        'help': 'Flag indicating if HIH61xx humidity sensor fitted',
    },
    'as3935_present': {
        'address': 0x5f,
        'format': 'B',
        'type': safe_eval,
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
        'type': safe_eval,
        'default': 8,
        'help': 'Fan control pin',
    },
    'adc_ref_type': {
        'address': 0x65,
        'format': 'B',
        'type': safe_eval,
        'default': 1,
        'help': 'ADC reference type; 0=Aref, 1=AVcc (default), 2=1V1, 3=2V56',
    },
    'adc_ref_voltage_mv': {
        'address': 0x66,
        'format': '<H',
        'type': safe_eval,
        'default': 3300,
        'help': 'ADC reference voltage (mV)',
    },
    # Support for AS3935 to be added
    
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
        'type': bytearray,
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

}

