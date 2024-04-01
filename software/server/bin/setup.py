#!/usr/bin/env python3

import argparse
import logging
import os
import re
import sys
import site
import subprocess


logger = logging.getLogger(__name__)


def query_sudo_cmd(cmd):
    if args.sudo is not None:
        if args.sudo:
            # Execute without prompting
            subprocess.check_call(cmd)
            return True
        else:
            return False
    else:
        while True:
            try:
                sys.stdout.write('\a\n')
                prompt = 'Ok to run "' + ' '.join(cmd) + '"? '
                response = raw_input(prompt + ' (Y/N) ?')
                if response.lower() == 'y':
                    # User accepted, run cmd
                    subprocess.check_call(cmd)
                    return True
                elif response.lower() == 'n':
                    return False
            except Exception:
                pass


def fix_symlinks(path, links):
    """
    path: the name of a directory
    links: dict of links names and targets
    """
    logger.info('Checking symlinks in ' + path)
    for link_name, t in links.items():
        slink = os.path.join(path, link_name)
        # Check that target exists as expected
        if os.path.exists(t):
            if os.path.lexists(slink):
                if os.path.islink(slink):
                    if os.readlink(slink) == t:
                        logger.debug(slink + ' correct (-> ' + t + ')')
                    else:
                        logger.warning('Deleting incorrect symlink ' + slink)
                        os.unlink(slink)
                else:
                    logger.warning(slink +
                                   ' exists but is not symlink, leaving alone')

            if not os.path.lexists(slink):
                logger.info('Creating symlink ' + slink + ' -> ' + t)
                os.symlink(t, slink)
        else:
            logger.error('Missing ' + t)


user = os.getlogin()

# Parse command line options
parser = \
    argparse.ArgumentParser(description='Set up python etc.')

# Make a sensible guess at the repository paths. Derive the best guess
# by inspecting the users Python site package directory. If that
# doesn't provide a real directory then guess it is directly inside
# the user's home directory. It doesn't matter if guessed wrong, this
# is only the default for the argument parsing.
auroraplot_package_dir = \
    os.path.realpath(os.path.join(site.getusersitepackages(), 
                                  'auroraplot'))
    
default_auroraplot_repo_path = os.path.realpath(
    re.sub(os.path.join('auroraplot', 'auroraplot') + '$', 'auroraplot', 
           auroraplot_package_dir, 1))

if not os.path.isdir(default_auroraplot_repo_path):
    # Does not exist so fall back to being inside of home directory
    default_auroraplot_repo_path = \
        os.path.join(os.path.expanduser('~' + user), 'auroraplot')


# Guess AuroraWatchNet repository path. This is slightly harder since
# the Python site package directory should contain a link to a
# directory within the repository, not the base of the repository.
aurorawatchnet_package_dir = \
    os.path.realpath(os.path.join(site.getusersitepackages(), 
                                  'aurorawatchnet'))
default_awn_repo_path = os.path.realpath(
    re.sub(os.path.join('software', 'server', 'aurorawatchnet') + '$',
           '', aurorawatchnet_package_dir, 1))

if not os.path.isdir(default_awn_repo_path) \
        or os.path.basename(default_awn_repo_path) != 'AuroraWatchNet':
    # Incorrect, fall back to being inside of home directory
    default_awn_repo_path = os.path.join(os.path.expanduser('~' + user),
                                         'AuroraWatchNet')



mcp342x_package_dir = \
    os.path.realpath(os.path.join(site.getusersitepackages(), 
                                  'MCP342x'))
    
default_mcp342x_repo_path = os.path.realpath(
    re.sub(os.path.join('python-MCP342x', 'MCP342x') + '$', 'MCP342x', 
           mcp342x_package_dir, 1))

if not os.path.isdir(default_mcp342x_repo_path):
    # Does not exist so fall back to being inside of home directory
    default_mcp342x_repo_path = \
        os.path.join(os.path.expanduser('~' + user), 'python-MCP342x')


    
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
parser.add_argument('--mcp342x-repository',
                    default=default_mcp342x_repo_path,
                    help='Path to python MCP342x repository',
                    metavar='PATH')
parser.add_argument('--sudo',
                    default=None,
                    action='store_true',
                    help='Fix problems automatically using sudo')
parser.add_argument('--no-sudo',
                    action='store_false',
                    dest='sudo',
                    help='Never use sudo to fix problems')


# Process the command line arguments
args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)


logger.debug('Best guess for auroraplot repository: ' 
             + default_auroraplot_repo_path)
logger.debug('Best guess for AuroraWatchNet repository: ' 
             + default_awn_repo_path)
logger.debug('Best guess for MCP342x repository: ' 
             + default_mcp342x_repo_path)

logger.info('auroraplot repository: ' + args.auroraplot_repository)
logger.info('AuroraWatchNet repository: ' + args.aurorawatchnet_repository)
logger.info('MCP342x repository: ' + args.mcp342x_repository)

# Check current username
if user == 'root':
    logger.error('This program should not be run as root')
    sys.exit(1)
elif user != 'pi':
    logger.warning('User is not pi')


# Check all required python modules/packages are installed
missing_packages = []
for package in ['serial', 'daemon', 'lockfile']:
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

package_links = {
    'auroraplot': os.path.join(args.auroraplot_repository, 'auroraplot'),
    'aurorawatchnet':  os.path.join(args.aurorawatchnet_repository, 
                                    'software', 'server', 'aurorawatchnet'),
    'MCP342x': os.path.join(args.mcp342x_repository, 'MCP342x'),
    }
fix_symlinks(site.getusersitepackages(), package_links)

import aurorawatchnet as awn
# Check user can read config file
try:
    config = awn.read_config_file(args.config_file)
except Exception as e:
    logger.error('Cannot read config file ' + args.config_file
                 + ', ' + str(e))

bin_dir = os.path.join(os.path.expanduser('~' + user), 'bin')

if not os.path.exists(bin_dir):
    os.mkdir(bin_dir)

# Check contents of ~/bin has the correct symlinks
bin_links = {'awnetd.py': os.path.join(args.aurorawatchnet_repository, 
                                       'software', 'server', 
                                       'bin',  'awnetd.py'),
             'awnetd_monitor.py': os.path.join(args.aurorawatchnet_repository, 
                                               'software', 'server', 
                                               'bin',  'awnetd_monitor.py'),
             'check_ntp_status': os.path.join(args.aurorawatchnet_repository, 
                                              'software', 'server', 
                                              'bin',  'check_ntp_status'),
             'log_ip': os.path.join(args.aurorawatchnet_repository, 
                                    'software', 'server', 'bin', 'log_ip'),
             'network_watchdog': os.path.join(args.aurorawatchnet_repository, 
                                              'software', 'server', 'bin', 
                                              'network_watchdog'),
             'raspimagd.py': os.path.join(args.aurorawatchnet_repository, 
                                          'software', 'server', 
                                          'bin',  'raspimagd.py'),
             'send_cmd.py': os.path.join(args.aurorawatchnet_repository, 
                                         'software', 'server', 'bin', 
                                         'send_cmd.py'),
             'upload_data.py': os.path.join(args.aurorawatchnet_repository, 
                                            'software', 'server', 'bin', 
                                            'upload_data.py'),
             }

fix_symlinks(bin_dir, bin_links)

daemon_name = config.get('daemon', 'name')
if daemon_name == 'awnetd':
    # Check /etc/init.d/awnetd
    symlink = '/etc/init.d/awnetd'
    target = os.path.join(args.aurorawatchnet_repository, 
                      'software', 'server', 'bin',  'awnetd.sh')
elif daemon_name == 'raspimagd':
    # Check /etc/init.d/raspimagd
    symlink = '/etc/init.d/raspimagd'
    target = os.path.join(args.aurorawatchnet_repository, 
                          'software', 'server', 'bin',  'raspimagd.sh')
else:
    logger.error('Meaning of daemon name = ' + daemon_name + ' is not understood')
    sys.exit(1)

logger.info('Checking symlink ' + symlink + ' -> ' + target)
if not os.path.lexists(symlink) or os.readlink(symlink) != target:
    logger.error('Service startup link ' + symlink + ' missing or incorrect')
    query_sudo_cmd(['sudo', 'ln', '-s', '-f', target, symlink])

# # Check /etc/init.d/awnetd_monitor
# symlink = '/etc/init.d/awnetd_monitor'
# target = os.path.join(args.aurorawatchnet_repository, 
#                       'software', 'server', 'bin',  'awnetd_monitor.py')

# if not os.path.lexists(symlink) or os.readlink(symlink) != target:
#     logger.error('Service startup link ' + symlink + ' missing or incorrect')
#     query_sudo_cmd(['sudo', 'ln', '-s', '-f', target, symlink])

