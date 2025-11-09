#!/usr/bin/env python

# Program to monitor a serial port to detect change of state in CTS,
# indicating a push-switch has been pressed. Switch presses toggle the
# existence or removal of a semaphore file. The serial control line
# DTR is used to indicate the presence of the file, by lighting an LED
# connected to it. Switch debouncing is implemented to confirm the
# switch state. In the case of an error the LED is flashed.
#
# The purpose of this program in the AuroraWatchNet system is to allow
# a non-technical use to flag when data quality may be suspect (for
# instance, when grass-cutting at the site is about to commence). By
# using a semaphore file to signal to the recording process it is easy
# to change the data quality status remotely.

import argparse
import logging
import os
import signal
import sys
import time
from serial import Serial
from fcntl import ioctl
import termios

try:
    from configparser import SafeConfigParser as ConfigParser
except ImportError:
    # SafeConfigParser removed from later versions
    from configparser import ConfigParser

import aurorawatchnet as awn

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


def init_serial_device(device):
    ser = Serial(device)
    return ser


if __name__ == '__main__':

    logger = logging.getLogger(__name__)

    # Parse command line arguments
    default_config_filename = None
    for f in ('/etc/ftdi_monitor.ini', '/etc/awnet.ini'):
        if os.path.exists(f):
            default_config_filename = f

    parser = \
        argparse.ArgumentParser(description='AuroraWatch data recording daemon')

    # If an expected default does not exist then make it a required argument
    parser.add_argument('-c', '--config-file',
                        default=default_config_filename,
                        required=False if default_config_filename else True,
                        help='Configuration file')
    parser.add_argument('-d', '--daemon', action='store_true',
                        help='Run as daemon')
    parser.add_argument('--log-level',
                        choices=['debug', 'info', 'warning',
                                 'error', 'critical'],
                        default='info',
                        help='Control how much detail is printed',
                        metavar='LEVEL')
    parser.add_argument('--port', metavar='FILE', help='USB device')
    parser.add_argument('--filename', metavar='FILE', help='Semaphore file')

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    config = awn.read_config_file(args.config_file)

    device = args.port
    if not device:
        if config.has_option('dataqualitymonitor', 'port'):
            device = config.get('dataqualitymonitor', 'port')
        else:
            raise Exception('FTDI device not specified')

    filename = args.filename
    if not filename:
        if config.has_option('dataqualitymonitor', 'filename'):
            filename = config.get('dataqualitymonitor', 'filename')
        elif config.has_option('dataqualitymonitor', 'directory'):
            # Generate filename based on serial device in use
            filename = os.path.join(config.get('dataqualitymonitor', 'directory'),
                                    'ftdi_monitor' + '_' + os.path.basename(device))
            logger.info('using %s as semaphore file', filename)
        else:
            raise Exception('Filename not specified')

    if args.daemon:
        import daemon
        pidfile = None
        if config.has_option('dataqualitymonitor', 'pidfile'):
            import lockfile
            pidfile = lockfile.FileLock(config.get('dataqualitymonitor', 'pidfile'),
                                        threaded=False)
            if pidfile.is_locked():
                print('daemon already running')
                exit(1)
        daemon.DaemonContext(pidfile=pidfile).open()

    ser = init_serial_device(device)
    file_exists = os.path.isfile(filename)
    previous_file_exists = file_exists
    ser.setDTR(file_exists)

    while True:
        try:
            r = timeout(ioctl, [ser.fd, termios.TIOCMIWAIT, termios.TIOCM_CTS], timeout_duration=1)

            file_exists = os.path.isfile(filename)
            ser.setDTR(file_exists)

            if file_exists != previous_file_exists:
                # File existence has changed.
                if file_exists:
                    logger.info('state changed: %s created externally', filename)
                else:
                    logger.info('state changed: %s removed externally', filename)
                # Don't accept any switch presses for a second.
                time.sleep(1)

            elif r is not None:
                # CTS changed state (or system call interrupted). Read CTS, sample
                # 5 times in 250ms for switch debouncing
                cts_count = 0
                for i in range(5):
                    time.sleep(0.050)
                    if ser.getCTS():
                        cts_count += 1

                if cts_count >= 3:
                    # Toggle state
                    file_exists = not file_exists
                    ser.setDTR(file_exists)
                    action = 'create/remove'
                    try:
                        if file_exists:
                            action = 'create'
                            fh = open(filename, 'a')
                            fh.close()
                        else:
                            action = 'remove'
                            os.remove(filename)
                        # Don't allow state to be changed immediately
                        logger.info('state changed: %s %sd due to button press', filename, action)
                        time.sleep(1)
                    except Exception as e:
                        logger.exception('could not %s file %s', action, filename)
                        print(str(e))
                        for i in range(10):
                            ser.setDTR(i % 2)
                            time.sleep(0.2)
                elif cts_count:
                    logger.debug('button press failed debounce check')

            previous_file_exists = file_exists

        except IOError as e:
            logger.exception('IO error')
            while True:
                # Try to resume (eg if device was unplugged)
                try:
                    ser.close()
                    ser = init_serial_device(device)
                    file_exists = os.path.isfile(filename)
                    ser.setDTR(file_exists)
                    logger.info('reopened device %s', device)
                    break
                except IOError:
                    time.sleep(1)
