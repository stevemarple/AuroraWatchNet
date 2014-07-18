#!/usr/bin/env python

import argparse
import os
import re
import sys
import site
import logging

logger = logging.getLogger(__name__)

user = os.getlogin()

# Parse command line options
parser = \
    argparse.ArgumentParser(description='Set up python etc.')

# Make a sensible guess at the repository paths. Derive the best guess
# by inspecting the users Python site package directory. If that
# doesn't provide a real directory then guess it is directly inside
# the user's home directory. It doesn't matter if guessed wrong, this
# is only the default for the argument parsing.

default_auroraplot_repo_path = \
    os.path.realpath(os.path.join(site.getusersitepackages(), 'auroraplot'))
if not os.path.isdir(default_auroraplot_repo_path):
    # Does not exist so fall back to being inside of home directory
    default_auroraplot_repo_path = \
        os.path.join(os.path.expanduser('~' + user), 'auroraplot')



# Guess AuroraWatchNet repository path. This is slightly harder since
# the Python site package directory should contain a link to a
# directory within the repository, not the base of the repository.
os.path.isdir(site.getusersitepackages())
aurorawatchnet_dir = \
    os.path.realpath(os.path.join(site.getusersitepackages(), 
                                  'aurorawatchnet'))
default_awn_repo_path = os.path.realpath( \
    re.sub(os.path.join('software', 'server', 'aurorawatchnet') + '$',
           '', aurorawatchnet_dir, 1))


if not os.path.isdir(default_awn_repo_path) \
        or os.path.basename(default_awn_repo_path) != 'AuroraWatchNet':
    # Incorrect, fall back to being inside of home directory
    default_awn_repo_path = os.path.join(os.path.expanduser('~' + user),
                                         'AuroraWatchNet')

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
parser.add_argument('--aurorawatchnet-repository',
                    default=default_awn_repo_path,
                    help='Path to AuroraWatchNet repository',
                    metavar='PATH')
parser.add_argument('--auroraplot-repository',
                    default=default_auroraplot_repo_path,
                    help='Path to auroraplot repository',
                    metavar='PATH')


# Process the command line arguments
args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)


logger.debug('Best guess for auroraplot repository: ' 
             + default_auroraplot_repo_path)
logger.debug('Best guess for AuroraWatchNet repository: ' 
             + default_awn_repo_path)

# Check current username
if user == 'root':
    logger.error('This program should not be run as root')
    sys.exit(1)
elif user != 'pi':
    logger.warning('User is not pi')


# Check all required python modules/packages are installed
missing_packages = []
for package in ['serial']:
    try:
        __import__(package)
    except ImportError as e:
        missing_packages.append(package)
        
if missing_packages:
    logger.error('Please install the following missing python packages: '
                 + ', '.join(missing_packages))
    sys.exit(1)


# Set up python user site packages directory before attempting to
# import any AuroraWatchNet packages or modules.
if not os.path.isdir(site.getusersitepackages()):
    logger.info('Creating directory ' + site.getusersitepackages())
    os.makedirs(site.getusersitepackages())
else:
    logger.debug('Directory ' + site.getusersitepackages()
                 + ' already exists')

package_paths = [args.auroraplot_repository,
                 os.path.join(args.aurorawatchnet_repository, 
                              'software', 'server', 'aurorawatchnet')]
    
for path in package_paths:
    link_name = os.path.join(site.getusersitepackages(), 
                             os.path.basename(path))
    link_target = path
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


# Check contents of ~/bin
bin_dir = os.path.join(os.path.expanduser('~' + user), 'bin')
# Check ~/bin/awnetd.py is correct
awnetd_py = os.path.join(args.aurorawatchnet_repository, 'software',
                         'server', 'aurorawatchnet',  'awnetd.py')
awnetd_py_symlink = os.path.join(bin_dir, 'awnetd.py')
if os.path.lexists(awnetd_py_symlink):
    if os.readlink(awnetd_py_symlink) == awnetd_py:
        logger.debug(awnetd_py_symlink + ' correct (-> ' + awnetd_py + ')')
    else:
        logger.info('Deleting incorrect symlink ' + awnetd_py_symlink)
        os.unlink(awnetd_py_symlink)

if not os.path.lexists(awnetd_py_symlink):
    logger.info('Creating symlink ' + awnetd_py_symlink + ' -> ' +
                awnetd_py)
    os.symlink(awnetd_py, awnetd_py_symlink)

