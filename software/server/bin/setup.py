#!/usr/bin/env python

import argparse
import os
import site
import logging

logger = logging.getLogger(__name__)

# Parse command line options
parser = \
    argparse.ArgumentParser(description='Set up python etc.')

parser.add_argument('-c', '--config-file', 
                    default='/etc/awnet.ini',
                    help='Configuration file',
                    metavar='FILE')
parser.add_argument('--log-level', 
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='info',
                    help='Control how much details is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')

# Process the command line arguments
args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)


# Check current username
user = os.getlogin()
if user == 'root':
    logger.error('This program should not be run as root')
    sys.exit(1)
elif user != 'pi':
    logger.warning('User is not pi')


# Set up python user site packages directory before attempting to
# import any AuroraWatchNet packages or modules.
if not os.path.isdir(site.getusersitepackages()):
    logger.info('Creating directory ' + site.getusersitepackages())
    os.makedirs(site.getusersitepackages())
else:
    logger.debug('Directory ' + site.getusersitepackages()
                 + ' already exists')

package_paths = ['auroraplot',
                 os.path.join('AuroraWatchNet', 'software', 
                              'server', 'aurorawatchnet')]
    
for mpath in package_paths:
    link_name = os.path.join(site.getusersitepackages(), 
                             os.path.basename(mpath))
    link_target = os.path.join(os.path.expanduser('~'), mpath)
    # Test if file, directory or symbolic link exists. If it is a link
    # assume the target is correct.
    if os.path.lexists(link_name):
        logger.debug(link_name + ' already exists')
    else:
        # Create suitable link
        logger.info('Creating link ' + link_name + ' -> ' + link_target)
        os.symlink(link_target, link_name)


import aurorawatchnet as awn
# Check user can read config file
try:
    config = awn.read_config_file(args.config_file)
except Exception as e:
    config.error('Cannot read config file ' + args.config_file 
                 + ', ' + str(e))
