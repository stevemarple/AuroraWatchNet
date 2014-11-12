#!/usr/bin/python

import argparse
import logging
import os
import random
import struct
import sys

import aurorawatchnet as awn
import aurorawatchnet.eeprom

logger = logging.getLogger(__name__)

eeprom = awn.eeprom.eeprom



# Parse command line options
parser = argparse.ArgumentParser(description='Create EEPROM image.')
parser.add_argument('--file', 
                    required=True,
                    help='EEPROM binary image file', 
                    metavar='FILENAME')
parser.add_argument('--log-level', 
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='warning',
                    help='Control how much detail is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')

# find the size of the EEPROM data
eeprom_size = 0
for k in eeprom:
    sz = struct.calcsize(eeprom[k]['format'])
    if eeprom[k]['address'] + sz > eeprom_size:
        eeprom_size = eeprom[k]['address'] + sz

# Create a blank EEPROM image of the correct size
#eeprom_data = [0xFF] * eeprom_size
#eeprom_data = ['\xFF'] * eeprom_size
eeprom_data = bytearray('\xFF') * eeprom_size

# Add command line options based on EEPROM settings
for k in sorted(eeprom.keys()):
    parser.add_argument('--' + k.replace('_','-'), 
                        type=eeprom[k].get('type'),
                        choices=eeprom[k].get('choices'),
                        help=eeprom[k].get('help'),
                        metavar=eeprom[k].get('metavar'))

# Process the command line arguments
args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)


# Calculate key length from the pattern, not the size reserved for it
hmac_key_length = awn.eeprom.parse_unpack_format(eeprom['hmac_key']['format'])[1]
generated_key = None
if args.hmac_key is None:
    # Create a random key
    generated_key = []
    for i in range(hmac_key_length):
        generated_key.append(random.randint(0, 255))
    args.hmac_key = ','.join(map(hex, generated_key))
elif args.hmac_key == 'blank':
    args.hmac_key = ','.join(['0xFF'] * hmac_key_length)
                            


# Apply settings defined from command line arguments, else use the
# default setting if defined.
for k in eeprom:
    logger.info('Processing option ' + k)
    s = getattr(args, k) # Get from command line
    if s is None:
        # Not set, get default value
        s = eeprom[k].get('default')

    if s is not None:
        # There is a value to set

        # If the argparse type conversion was employed then convert
        # back to a string
        s = str(s)

        # Parse struct format string into order, quantity, type
        pfmt = awn.eeprom.parse_unpack_format(eeprom[k]['format'])

        if pfmt[2] in ('c', 's', 'p'):
            # String data
            data = s
        else:
            # Convert into numeric data
            data = awn.eeprom.safe_eval(s)

        if pfmt[1] > 1:
            # Multiple values required
            struct.pack_into(eeprom[k]['format'], eeprom_data,
                             eeprom[k]['address'], *data)
        else:
            struct.pack_into(eeprom[k]['format'], eeprom_data,
                             eeprom[k]['address'], data)


eeprom_image_filename = args.file + '.bin'
fh = open(eeprom_image_filename, 'wb')
fh.write(eeprom_data)
fh.close()
print('Wrote ' + str(eeprom_size) + ' bytes to ' + eeprom_image_filename)

# Print out and save key details
hmac_key = awn.eeprom.safe_eval(args.hmac_key)
hex02x = lambda n : '%02x' % n
hex0x02x = lambda n : '0x%02x' % n
op_dict = {'key_pretty': ','.join(map(hex0x02x, hmac_key)),
           'key_inifile': ''.join(map(hex02x, hmac_key)),
           'binfile': eeprom_image_filename,
           'filename': args.file}


key_doc = '''HMAC-MD5 key:
%(key_pretty)s

Add the line below to the "[magnetometer]" section of the ini file:
key = %(key_inifile)s

Write the EEPROM data with
avrdude -P usb -p atmega1284p -c dragon_jtag -U eeprom:w:%(binfile)s:r
or
avrdude -P /dev/ttyXXX -p atmega1284p -c avr109 -b 38400 -U eeprom:w:%(binfile)s:r
(substitute /dev/ttyXXX by correct device name)
'''
print(key_doc % op_dict)
fh = open(args.file + '.key', 'w')
fh.write(key_doc % op_dict)
fh.close()

# Save command line arguments
fh = open(args.file + '.txt', 'w')
fh.write('# Called as: \n')
fh.write(' '.join(sys.argv))
fh.write('\n')
fh.write('# Current working directory: ' + os.getcwd() + '\n')
fh.close()



