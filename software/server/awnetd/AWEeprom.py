# -*- coding: iso-8859-15 -*-

import re

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
    
# Use eval but without allowing the user to access builtin functions
# or locals
def safe_eval(s):
    return eval(s, {'__builtins__': None}, {})


# EEPROM address details. The key is derived from the C language name
# and becomes the command line option when genreating an EEPROM image
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
        'format': '<H'
        },
    'adc_address_list': {
        'address': 0x32,
        'format': '3B',
        'default': [0x6E, 0x6A, 0x6C],
        'help': 'List of ADC I2C addresses',
        },
    'adc_channel_list': {
        'address': 0x35,
        'format': '3B',
        'default': [1, 1, 1],
        'help': 'List of ADC channel numbers (1-4)'
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
    'radio_type': {
        # 0 = XRF, 1 = RFM12B, 255 = autoselect
        'address': 0x3A,
        'format': 'B',
        'type': safe_eval,
        'choices': [0, 1, 255],
        'default': 255,
        'help': 'XRF radio type; 1=XRF, 2=RFM12B, 255=autoselect'
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
        'default': 1,
        'choices': [0, 1, 2],
        'help': 'Aggregate function for multiple samples; 0=mean, 1=median, 2=trimmed mean',
        },
    'all_samples': {
        'address': 0x46,
        'format': 'B'
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
    'max_message_no_ack': {
        'address': 0x49,
        'format': 'B',
        'default': '0',
        'help': 'Number of messages without receiving an ACK before rebooting',
        'metavar': 'NUMBER'
        },
    }