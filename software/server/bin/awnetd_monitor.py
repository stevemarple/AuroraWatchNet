#!/usr/bin/env python

### BEGIN INIT INFO
# Provides:          awnetd_monitor
# Required-Start:    udev
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       AuroraWatchNet data quality monitor
### END INIT INFO

# Program to monitor a serial port to detect change of state in CTS,
# indicating a push-switch has been pressed. Switch presses toggle the
# existence or removal of a semaphore file. The serial control line
# DTR is used to indicate the presence of the file, by lighting an LED
# connected to it. Switch debouncing is implemented to confirm the
# switch state. In the case of an error the LED is flashed. DTR can be
# active low or active high. If the LED is wired (via a resistor) between
# DTR and ground then it is active high, if wired between DTR and
# supply it is active low.
#
# The purpose of this program in the AuroraWatchNet system is to allow
# a non-technical user to flag when data quality may be suspect (for
# instance, when grass-cutting at the site is about to commence). By
# using a semaphore file to signal to the recording process it is easy
# to change the data quality status remotely.

import argparse
import daemon
import daemon.runner
import logging
from operator import xor
import os
import re
import signal
import subprocess
import sys
import time
from serial import Serial, SerialException, SerialTimeoutException
from fcntl import  ioctl
from termios import (
    TIOCMIWAIT,
    TIOCM_RNG,
    TIOCM_DSR,
    TIOCM_CD,
    TIOCM_CTS
)

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import aurorawatchnet as awn

logger = logging.getLogger(__name__)

class FtdiMonitor():
    def __init__(self, progname, device=None, filename=None,
                 pidfile_path=None, pidfile_timeout=None, 
                 username='pi', group='pi', foreground=False):
        self.progname = progname
        self.device = device
        self.filename = filename
        self.username = username
        self.group = group

        if foreground:
            self.stdin_path = '/dev/tty'
            self.stdout_path = '/dev/tty'
        else:
            self.stdin_path = '/dev/null'
            self.stdout_path = '/dev/null'

        self.stderr_path = '/dev/null'
        self.pidfile_path = pidfile_path
        if self.pidfile_path is None:
            self.pidfile_path = '/var/run/' + progname + '.pid'
            
        self.pidfile_timeout = pidfile_timeout
        
           
    def run(self, daemon_mode=True):
        if (daemon_mode):
            logger.info('Daemon starting, device=' + device 
                        + ', filename=' + filename)
            # Set up signal handler
            signal.signal(signal.SIGTERM, signal_handler)

        previous_device_state = 'none'
        previous_file_exists = os.path.isfile(filename)

        while True:
            try:
                file_exists = os.path.isfile(filename)
                if file_exists != previous_file_exists:
                    # File existence has changed whilst serial device
                    # is not available, cannot signal the change in
                    # state here.
                    if file_exists:
                        logger.info(filename + ' created externally')
                    else:
                        logger.info(filename + ' removed externally')

                ser = Serial(device)
                logger.info('Opened ' + device)
                ser.setDTR(xor(not file_exists, led_active_low ))

                while True:
                    r = timeout(ioctl, [ser.fd, TIOCMIWAIT, TIOCM_CTS], 
                                timeout_duration=10)

                    file_exists = os.path.isfile(filename)
                    ser.setDTR(xor(not file_exists, led_active_low))

                    if file_exists != previous_file_exists:
                        # File existence has changed, serial device is
                        # available so indicate the change. Don't act
                        # on any switch input since it might be
                        # inverse to what was intended. Wait a short
                        # while before reading the switch again so
                        # that the user can recognise the
                        # externally-induced state change.
                        if file_exists:
                            logger.info(filename + ' created externally')
                            cmd = warning_cmd
                            
                        else:
                            logger.info(filename + ' removed externally')
                            cmd = ok_cmd
                        time.sleep(1)

                    elif r is not None:
                        # CTS changed state (or system call
                        # interrupted). Read CTS, sample 5 times in
                        # 250mS for switch debouncing
                        cts_count = 0
                        for i in range(5):
                            time.sleep(0.050)
                            if ser.getCTS():
                                cts_count += 1

                        if cts_count >= 3:
                            file_exists = not file_exists
                            ser.setDTR(xor(not file_exists, led_active_low))
                            try:
                                if file_exists:
                                    cmd = warning_cmd
                                    fh = open(filename, 'a')
                                    fh.close()
                                    logger.info(filename + ' created')
                                else:
                                    cmd = ok_cmd
                                    os.remove(filename)
                                    logger.info(filename + ' removed')
                                # Dont' allow state to be changed
                                # immediately
                                time.sleep(1)
                            except Exception as e:
                                logger.error(str(e))
                                for i in range(10):
                                    ser.setDTR(xor(i % 2, led_active_low))
                                    time.sleep(0.2)

                    previous_file_exists = file_exists
                    previous_device_state = 'opened'
                    try:
                        if file_exists:
                            cmd = warning_cmd
                        else:
                            cmd = ok_cmd
                        if cmd:
                            logger.info('Running command %s',
                                        repr(cmd))
                            subprocess.check_call(cmd, shell=True)

                    except Exception as e:
                        logger.error(str(e))



            except (SerialTimeoutException, IOError):
                if previous_device_state == 'opened':
                    logger.error('Cannot access ' + device
                                 + ', waiting for it to appear')
                elif previous_device_state == 'none':
                    logger.error('Cannot open ' + device 
                                 + ', waiting for it to appear')
                previous_device_state = 'error'
                previous_file_exists = file_exists
                time.sleep(5)


# Inspired by
# http://stackoverflow.com/questions/492519/timeout-on-a-python-function-call
def timeout(func, args=(), kwargs={}, timeout_duration=1, default=None):

    class TimeoutError(Exception):
        pass

    def handler(signum, frame):
        raise TimeoutError()

    # set the timeout handler
    signal.signal(signal.SIGALRM, handler) 
    signal.alarm(timeout_duration)
    try:
        result = func(*args, **kwargs)
    except TimeoutError as exc:
        result = default
    finally:
        signal.alarm(0)

    return result


def signal_handler (signum, frame):
    logger.info('Daemon terminating with signal ' + str(signum))
    sys.exit(0)


if __name__ == '__main__':

    # Parse command line arguments
    progname = os.path.basename(sys.argv[0]).partition('.')[0]
    default_config_file = \
        os.path.join(os.path.sep, 'etc', progname + '.ini')
    if not os.path.exists(default_config_file):
        default_config_file = \
            os.path.join(os.path.sep, 'etc', 'awnet.ini')

    parser = \
        argparse.ArgumentParser(description='AuroraWatch data quality monitor')

    parser.add_argument('-c', '--config-file', 
                        default=default_config_file,
                        help='Configuration file')
    parser.add_argument('--port', metavar='FILE', help='USB device')
    parser.add_argument('--filename', metavar='FILE', help='Semaphore file')
    parser.add_argument('--log-level', 
                        choices=['debug', 'info', 'warning', 
                                 'error', 'critical'],
                        default='info',
                        help='Control how much detail is printed',
                        metavar='LEVEL')
    parser.add_argument('--log-format',
                        default='%(levelname)s:%(message)s',
                        help='Set format of log messages',
                        metavar='FORMAT')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--foreground', action='store_true',
                       help='Run in foreground (not daemon)')

    group.add_argument('action', nargs='?',
                       choices=['start', 'stop', 'restart'],
                       metavar='start|stop|restart',
                       help='Daemon action')
    args = parser.parse_args()
    if not args.foreground and len(sys.argv) > 2:
        # Fix sys.argv for the daemon to parse
        sys.argv = [sys.argv[0], args.action]

    config = awn.read_config_file(args.config_file)

    logger.setLevel(getattr(logging, args.log_level.upper()))
    log_formatter = logging.Formatter(args.log_format)
    if config.has_option('dataqualitymonitor', 'logfile'):
        log_filehandle = logging.FileHandler(config.get('dataqualitymonitor', 
                                                        'logfile'))
        log_filehandle.setFormatter(log_formatter)
        logger.addHandler(log_filehandle)
    else:
        log_filehandle = None

    awn.drop_root_privileges(username=config.get('dataqualitymonitor', 
                                                 'username'),
                             group=config.get('dataqualitymonitor', 
                                              'group'))

    device = args.port
    if not device:
        if config.has_option('dataqualitymonitor', 'port'):
            device = config.get('dataqualitymonitor', 'port')
        else:
            raise Exception('FTDI device not specified')

    filename = args.filename
    if not filename:
        if config.has_option('dataqualitymonitor', 'directory'):
            directory = config.get('dataqualitymonitor', 'directory')
            if not os.path.exists(directory):
                os.makedirs(directory)
            elif not os.path.isdir(directory):
                raise Exception('Data quality directory exists but is not a directory (%s)', directory)
            filename = os.path.join(directory, 'data_quality_monitor_' 
                                    + os.path.basename(device))
        elif config.has_option('dataqualitymonitor', 'filename'):
            filename = config.get('dataqualitymonitor', 'filename')
        else:
            raise Exception('Filename not specified')

    if config.has_option('dataqualitymonitor', 'pidfile'):
        pidfile_path = config.get('dataqualitymonitor', 'pidfile')
    else:
        pidfile_path = None
    if config.has_option('dataqualitymonitor', 'led_active_low'):
        led_active_low = config.getboolean('dataqualitymonitor', 
                                           'led_active_low')
    else:
        led_active_low = True

    if config.has_option('dataqualitymonitor', 'warning_command'):
        warning_cmd = config.get('dataqualitymonitor', 'warning_command')
    else:
        warning_cmd = None
    if config.has_option('dataqualitymonitor', 'ok_command'):
        ok_cmd = config.get('dataqualitymonitor', 'ok_command')
    else:
        ok_cmd = None

    fm = FtdiMonitor(progname, device=device, filename=filename,
                     pidfile_path=pidfile_path, 
                     username=config.get('dataqualitymonitor', 'username'),
                     foreground=args.foreground)

    if args.foreground:
        logger.info('running in foreground')
        logger.info('device:' + fm.device)
        logger.info('filename:' + fm.filename)
        fm.run(False)
    else:
        
        daemon_runner = daemon.runner.DaemonRunner(fm)
        if log_filehandle:
            daemon_runner.daemon_context.files_preserve=[log_filehandle.stream]
        try:
            daemon_runner.do_action()
        except Exception as e:
            logger.error('Daemon terminating with exception: ' + str(e) 
                         + ', type: ' + str(type(e)))

