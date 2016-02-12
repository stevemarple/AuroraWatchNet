#!/usr/bin/env python

### BEGIN INIT INFO
# Provides:          raspimagd
# Required-Start:    udev
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       Raspberry Pi magnetometer data collection daemon
### END INIT INFO

import argparse
import daemon
import daemon.runner
import glob
import logging
import os
import signal
import smbus
import sys
import threading
import time
import traceback

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import aurorawatchnet as awn
from aurorawatchnet.sampler import Sampler
import MCP342x

logger = logging.getLogger(__name__)


class RasPiMagD():
    def __init__(self, progname, device=None, filename=None,
                 pidfile_path=None, pidfile_timeout=None, 
                 username='pi', group='pi', foreground=False):
        self.progname = progname
        self.username = username
        self.group = group
        self.sampler = None

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
        
           
    def run(self, action, daemon_mode=True):
        if (daemon_mode):
            logger.info('Daemon starting')
            # Set up signal handling

        signal.signal(signal.SIGTERM, stop_handler)
        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGUSR1, reload_config_handler)
        data_file = None

        print('test')
        if True:
            try:
                print('Starting sampling thread')
                sampling_interval = 5
                self.sampler = Sampler(action)
                do_every(sampling_interval, self.sampler.sample)
                while take_samples:
                    time.sleep(3)

                # Wait until all other threads have (or should have)
                # completed
                for n in range(sampling_interval + 1):
                    if threading.activeCount() == 1:
                        break
                    time.sleep(1)
              

            except Exception as e:
                print(e)
                logger.error(traceback.format_exc())
                time.sleep(5)

       
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


take_samples = True
def stop_handler(signal, frame):
    global take_samples
    print ('Stopping...')
    take_samples = False
    threads = threading.enumerate()
    for t in threads[1:]:
        t.cancel()        
    
    # If all the other threads have completed then exit; exit anyway
    # after a short time has passed
    t = time.time()
    while time.time() < t + 1 and len(threading.enumerate()) > 2:
        time.sleep(0.1)
    #sys.exit()

magd = None
def reload_config_handler(signal, frame):
    if magd and magd.sampler:
        logger.debug('Reloading config file...')
        magd.sampler.pause()
        logger.debug('TODO: Re-read config file')
        time.sleep(8)
        logger.debug('Config file reloaded')
        magd.sampler.resume()

def do_every (interval, worker_func, iterations = 0):
    if iterations != 1:
        adj = time.time() % 1
        t = threading.Timer(interval - adj,
                            do_every, 
                            [interval, worker_func, 
                             0 if iterations == 0 else iterations-1])
        t.daemon = True
        t.start()
    worker_func()

def read_config_file(filename):
    """Read config file."""
    logger.info('Reading config file ' + filename)

    config = SafeConfigParser()
    config.add_section('daemon')
    config.set('daemon', 'username', 'pi')
    config.set('daemon', 'group', 'pi')

    if filename:
        config_files_read = config.read(filename)
        if filename not in config_files_read:
            raise UserWarning('Could not read ' + filename)
        logger.debug('Successfully read ' + ', '.join(config_files_read))

    return config


def drop_root_privileges(username='nobody', group=None):
    if os.getuid() != 0:
        # Not root
        return

    # Get the UID and GID
    pwnam = pwd.getpwnam(username)

    # Remove group privileges
    os.setgroups([])

    # Set to new GID (whilst still have root privileges)
    if group is None:
        # No group specified, use user's default group
        os.setgid(pwnam.pw_gid)
    else:
        grnam = grp.getgrnam(group)
        os.setgid(grnam.gr_gid)

    # Change to new UID
    os.setuid(pwnam.pw_uid)

    # Set umask
    old_umask = os.umask(0o22)

def get_smbus(bus_number=None):
    candidates = []
    prefix = '/dev/i2c-'
    if bus_number is not None:
        if os.path.exists(bus_number):
            return smbus.SMBus(bus_number )
        else:
            return smbus.SMBus(prefix + str(bus_number))

    for bus in glob.glob(prefix + '*'):
        try:
            n = int(bus.replace(prefix, ''))
            candidates.append(n)
        except:
            pass
        
    if len(candidates) == 1:
        return smbus.SMBus(candidates[0])
    elif len(candidates) == 0:
        raise Exception("Could not find an I2C bus")
    else:
        raise Exception("Multiple I2C busses found")

def voltage_to_deg_C(voltage, offset, scale):
    return (voltage - offset) / scale

def voltage_to_tesla(voltage, sensitivity=20000):
    # sensitivity in V/T
    return voltage / float(sensitivity)

def get_file_for_time(t, file_obj, fstr, mode='a+b', buffering=0, 
                      extension=None):
    '''
    Get a file object to save data, with the name defined by the time
    and format string

    t -- seconds since unix epoch
    file_obj --  existing file object (or None)
    fstr -- strftime format string
    buffering buffering value passed to file open
    extension -- any extension appended to the file name
    '''
    tmp_name = time.strftime(fstr, time.gmtime(t))
    if extension is not None:
        tmp_name += extension

    if file_obj is not None:
        if file_obj.closed:
            file_obj = None
        elif file_obj.name != tmp_name:
            # Filename has changed
            file_obj.close()
            file_obj = None
        
    if file_obj is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            os.makedirs(p)

        file_obj = open(tmp_name, mode, buffering)
    
    return file_obj
               

def write_data(fh, t, h, d, z, f, temp):
    # Round time to nearest millisecond, calculate milliseconds and
    # print separately since strftime does not support it
    t_ms = round(t * 1e3)
    t2 = t_ms / 1e3
    ms = int(t_ms % 1000)
    tm = time.gmtime(t2)
    fh.write('%s.%03d %+09.02f %+09.02f %+09.02f %09.02f %+06.02f\n' % 
             (time.strftime('%Y %m %d %H %M %S', tm), 
              ms, h, d, z, f, temp))

                
sample_num = 0
def get_sample():
    global sample_num
    n = str(sample_num) + ' '
    sample_num += 1
    print(n + ' get_sample()')
    t1 = time.time()
    #time.sleep(4)
    temp = temp_ADC.convert_and_read(scale_factor= 244.85798237022533) - 50
    t2 = time.time()

    # r = ((t1+t2)/2., 1., 3., 4., 5., temp)
    r = (t1, 1., 3., 4., 5., temp)
    print(n + repr(r))
    print(n + 'end get_sample()')
    return r

if __name__ == '__main__':

    logger = logging.getLogger(__name__)
    # Parse command line arguments
    progname = os.path.basename(sys.argv[0]).partition('.')[0]
    default_config_file = \
        os.path.join(os.path.sep, 'etc', 'awnet.ini')

    parser = \
        argparse.ArgumentParser(description='Raspberry Pi magnetometer daemon')

    parser.add_argument('-c', '--config-file', 
                        default=default_config_file,
                        help='Configuration file')
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

    config = read_config_file(args.config_file)
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)

    log_formatter = logging.Formatter(args.log_format)
    if config.has_option('logging', 'filename'):
        log_filehandle = logging.FileHandler(config.get('daemon', 
                                                        'logfile'))
        log_filehandle.setFormatter(log_formatter)
        logger.addHandler(log_filehandle)
    else:
        log_filehandle = None

    # Is this the best place to drop privileges?
    drop_root_privileges(username=config.get('daemon', 'username'),
                         group=config.get('daemon', 'group'))

    if config.has_option('daemon', 'pidfile'):
        pidfile_path = config.get('daemon', 'pidfile')
    else:
        pidfile_path = None

    if config.has_option('daemon', 'i2c'):
        bus = get_smbus(config.get('daemon', 'i2c'))
    else:
        bus = get_smbus()
    
    temp_ADC = MCP342x.MCP342x(bus, 0x68)
    temp_ADC.set_channel(3)
    temp_ADC.set_resolution(18)

    magd = RasPiMagD(progname, 
                     pidfile_path=pidfile_path, 
                     username=config.get('daemon', 'username'),
                     foreground=args.foreground)

    if args.foreground:
        print('Running in foreground')
        logger.info('running in foreground')
        magd.run(get_sample, daemon_mode=False)
    else:
        
        daemon_runner = daemon.runner.DaemonRunner(magd)
        if log_filehandle:
            daemon_runner.daemon_context.files_preserve=[log_filehandle.stream]
        try:
            daemon_runner.do_action()
        except Exception as e:
            logger.error('Daemon terminating with exception: ' + str(e) 
                         + ', type: ' + str(type(e)))

