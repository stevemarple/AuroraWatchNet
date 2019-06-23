#!/usr/bin/python

import argparse
import logging
import re
import socket
import struct
import sys
import time

#import AWEeprom
#from AWEeprom import eeprom
import aurorawatchnet as awn
import aurorawatchnet.eeprom as eeprom



if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

logger = logging.getLogger(__name__)


# Valid commands and information about each
# TODO: use a standard naming convention
aw_cmds = {
    'sampling_interval' : {
        # 'format': 'f',
        'help': 'Sampling interval',
        'metavar': 'SECONDS',
    },
    'upgrade_firmware': {
        'help': 'Upgrade firmware',
        'metavar': 'FIRMWARE_VERSION',
    },
    'reboot': {
        'help': 'Reboot microcontroller',
        'metavar': 'TRUE',
        'choices': ['TRUE'],
    },
    'rio_freeze_scan': {
        'help': 'Freeze riometer scanning at given state',
        'metavar': 'STATE',
        'type': int,
    },
    'rio_unfreeze_scan': {
        'dest': 'rio_freeze_scan',
        'action': 'store_const',
        'const': 255,
        'help': 'Resume normal riometer scanning',
    },
    'rio_connect': {
        'help': 'Connect riometers from Butler matrix',
        'action': 'store_const',
        'const': 1,
    },
    'rio_disconnect': {
        'help': 'Disconnect riometers from Butler matrix',
        'action': 'store_const',
        'const': '0',
        'dest': 'rio_connect',
    },
}

# Add options for EEPROM settings, prefix with 'eeprom_'. Do not pass
# the default EEPROM value as the default argparse value!

for k in eeprom.eeprom.keys():
    # aw_cmds['eeprom_' + k] = eeprom.eeprom[k]
    aw_cmds['eeprom_' + k] = {}
    for k2 in eeprom.eeprom[k]:
        if k2 not in ['default']:
            aw_cmds['eeprom_' + k][k2] = eeprom.eeprom[k][k2]
    
# Parse command line options
parser = \
    argparse.ArgumentParser(description='Send commands to recording daemon.',
                            epilog='EEPROM settings only take effect ' + 
                            'after a reboot.')
parser.add_argument('-c', '--config-file', 
                    default='/etc/awnet.ini',
                    help='Configuration file',
                    metavar='FILE')
parser.add_argument('--host', 
                    default='localhost',
                    help='Hostname where daemon is running')
parser.add_argument('--log-level', 
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='warning',
                    help='Control how much details is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')
parser.add_argument('-v', '--verbose', 
                    action='count',
                    help='Be verbose')

for k in sorted(aw_cmds.keys()):
    parse_args = {}
    for k2 in aw_cmds[k]:
        if k2 not in ['format', 'address', 'size']:
            parse_args[k2] = aw_cmds[k][k2]
#    print(k + ': ' + repr(parse_args))
    parser.add_argument('--' + k.replace('_', '-'), **parse_args)
    # if aw_cmds[k].has_key('action'):
    #     parser.add_argument('--' + k.replace('_', '-'),
    #                         action=aw_cmds[k].get('action'),
    #                         help=aw_cmds[k].get('help'))
    # else:
    #     parser.add_argument('--' + k.replace('_', '-'),
    #                         type=aw_cmds[k].get('type'),
    #                         choices=aw_cmds[k].get('choices'),
    #                         help=aw_cmds[k].get('help'),
    #                         metavar=aw_cmds[k].get('metavar'))

eeprom_settings_group = parser.add_mutually_exclusive_group()
read_cmds = []
for k in sorted(eeprom.eeprom.keys()):
    eeprom_settings_group.add_argument('--read-eeprom-' + k.replace('_', '-'),
                                       action='store_true',
                                       help='Read setting: ' + \
                                           eeprom.eeprom[k].get('help'))
    read_cmds.append(k)
                                       
# Process the command line arguments
args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)

config = awn.read_config_file(args.config_file)
user_cmds = []

for k in aw_cmds:
    cmd_name = k
    if 'dest' in aw_cmds[k]:
        cmd_name = aw_cmds[k]['dest']

    s = getattr(args, cmd_name)
    if s is None:
        continue

    cmd = { }
    # If the argparse type conversion was employed then convert
    # back to a string
    s = str(s)

    m = re.match('^eeprom_(.*)', cmd_name)
    if m:
        cmd['name'] = 'write_eeprom'
        eeprom_setting = m.group(1)
        # Parse struct format string into order, quantity, type
        pfmt = eeprom.parse_unpack_format( \
            eeprom.eeprom[eeprom_setting]['format'])
        if pfmt[2] in ('c', 's', 'p'):
            # String data
            data = s
        else:
            # Convert into numeric data
            data = awn.safe_eval(s)

        # Pack data into suitable bytearrays matching the EEPROM layout
        if pfmt[1] > 1 and pfmt[2] not in ('s', 'p'):
            # Multiple values required
            eeprom_data = struct.pack(eeprom.eeprom[eeprom_setting]['format'],
                                      *data)
        else:
            eeprom_data = struct.pack(eeprom.eeprom[eeprom_setting]['format'],
                                           data)
            
        # Convert the bytewise values into a string, remembering to
        # prepend the address
        cmd['value'] = str(eeprom.eeprom[eeprom_setting]['address']) + \
            ',' + ','.join([str(ord(x)) for x in eeprom_data])
    else:
        cmd['name'] = cmd_name
        cmd['value'] = s

    user_cmds.append(cmd)


for k in read_cmds:
    if getattr(args, 'read_eeprom_' + k):
        user_cmds.append({
                'name': 'read_eeprom',
                'value': str(eeprom.eeprom[k]['address']) + ',' + \
                    str(struct.calcsize(eeprom.eeprom[k]['format']))})
        

host = args.host
port = int(config.get('controlsocket', 'port'))
logger.debug('Control socket: ' + str(port))

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((host, port))
s.settimeout(5)
for cmd in user_cmds:
    cmd_str = cmd['name'] + '=' + cmd['value']
    if args.verbose:
        print("Sending '" + cmd_str + "'")
    s.send(cmd_str + '\n')
    response = s.recv(256)
    if args.verbose:
        print("Received '" + response.rstrip('\r\n') + "'")

# Enquire about pending tags
s.send('pending_tags\n')
pending_tags = s.recv(256).rstrip('\r\n')
pending_actions = pending_tags.split(':')[1].replace(',', ', ')
if pending_actions != '':
    print('Pending commands: ' + pending_actions)
else:
    print('No commands pending')

s.shutdown(socket.SHUT_RDWR)
s.close()

