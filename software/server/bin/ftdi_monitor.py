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
import os
import signal
import sys
import time
from serial import Serial
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


# Parse command line arguments
parser = \
    argparse.ArgumentParser(description='AuroraWatch data recording daemon')

parser.add_argument('-c', '--config-file', 
                    default='/etc/awnet.ini',
                    help='Configuration file')
parser.add_argument('-d', '--daemon', action='store_true',
                    help='Run as daemon')
parser.add_argument('--port', metavar='FILE', help='USB device')
parser.add_argument('--filename', metavar='FILE', help='Semaphore file')

args = parser.parse_args()
config = awn.read_config_file(args.config_file)

device = args.port
if not device:
    if config.has_option('dataqualitymonitor', 'port'):
        device = config.read('dataqualitymonitor', 'port')
    else:
        raise Exception('FTDI device not specified')

filename = args.filename
if not filename:
    if config.has_option('dataqualitymonitor', 'filename'):
        device = config.read('dataqualitymonitor', 'filename')
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


ser = Serial(device)
wait_signals = (TIOCM_RNG |
                TIOCM_DSR |
                TIOCM_CD  |
                TIOCM_CTS)
    
ser.setDTR(True)
file_exists = os.path.isfile(filename)
previous_file_exists = file_exists
ser.setDTR(not file_exists)

while True:
    # ioctl(ser.fd, TIOCMIWAIT, TIOCM_CTS)
    r = timeout(ioctl, [ser.fd, TIOCMIWAIT, TIOCM_CTS], timeout_duration=1)

    file_exists = os.path.isfile(filename)
    ser.setDTR(not file_exists)

    if file_exists != previous_file_exists:
        # File existence has changed. Don't allow accept any switch
        # presses for a second.
        time.sleep(1)

    elif r is not None:
        # CTS changed state (or system call interrupted). Read CTS, sample
        # 5 times in 250mS for switch debouncing
        cts_count = 0
        for i in range(5):
            time.sleep(0.050)
            if ser.getCTS():
                cts_count += 1

        if cts_count >= 3:
            file_exists = not file_exists
            ser.setDTR(not file_exists)
            try:
                if file_exists:
                    fh = open(filename, 'a')
                    fh.close()
                else:
                    os.remove(filename)
                # Dont' allow state to be changed immediately
                time.sleep(1)
            except Exception as e:
                print(str(e))
                for i in range(10):
                    ser.setDTR(i % 2)
                    time.sleep(0.2)
            
    previous_file_exists = file_exists
