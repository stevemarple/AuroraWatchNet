#!/usr/bin/env python
import argparse
import logging
import os
import sys
if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import subprocess

parser = argparse.ArgumentParser(description=\
                                     'Upload AuroraWatch magnetometer data.')

parser.add_argument('--log-level', 
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='warning',
                    help='Control how much detail is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')
parser.add_argument('-n', '--dry-run',
                    action='store_true',
                    default=False,
                    help='Test without uploading')
parser.add_argument('-v', '--verbose',
                    default=False,
                    action='store_true',
                    help='Be verbose')

args = parser.parse_args()
logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                    format=args.log_format)

config_file = '/etc/awnet.ini'
if not os.path.exists(config_file):
    logging.error('Missing config file ' + config_file)
    exit(1)

try:
    config = SafeConfigParser()
    config.read(config_file)
    site = config.get('magnetometer', 'site').upper()
    site_lc = site.lower()
except Exception as e:
    print('Bad config file ' + config_file + ': ' + str(e))
    raise

cmd = ['rsync', '--archive']
# Options
if args.verbose:
    cmd.append('--verbose')

if args.dry_run:
    cmd.append('--dry-run')

src_dir = os.path.join(os.sep, 'data', 'aurorawatchnet', site_lc)

user_name = 'awn_' + site_lc
# Append src directory. Trailing slash is important, it means the
# contents of the directory.
cmd.append(src_dir + os.sep) 
cmd.append(user_name + '@awn-data:/data/aurorawatchnet/' \
               + site_lc)

if args.verbose:
    print(' '.join(cmd))

subprocess.call(cmd)

