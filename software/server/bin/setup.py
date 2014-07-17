#!/usr/bin/env python

import argparse
import os
import site
import logging

logger = logging.getLogger(__name__)

# Parse command line options
parser = \
    argparse.ArgumentParser(description='Set up python etc.')

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


if not os.path.isdir(site.getusersitepackages()):
    logger.info('Creating directory ' + site.getusersitepackages())
    os.makedirs(site.getusersitepackages())
else:
    logger.debug('Directory ' + site.getusersitepackages()
                 + ' already exists')

module_paths = ['auroraplot',
                os.path.join('AuroraWatchNet', 'software', 
                             'server', 'aurorawatchnet')]
    
for mpath in module_paths:
    link_name = os.path.join(site.getusersitepackages(), 
                             os.path.basename(mpath))
    link_target = os.path.join(os.path.expanduser('~'), mpath)
    logger.debug('Test link ' + link_name + ' -> ' + link_target)
    if not os.path.lexists(link_name):
        # Create link
        logger.info('Creating link ' + link_name + ' -> ' + link_target)
        os.symlink(link_target, link_name)

