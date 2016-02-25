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
import copy
import daemon
import daemon.runner
import glob
import logging
import numpy as np
import os
import signal
import smbus
import struct
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
import aurorawatchnet.message
from MCP342x import MCP342x

logger = logging.getLogger(__name__)

class RasPiMagD():
    def __init__(self, progname, device=None, filename=None,
                 pidfile_path=None, pidfile_timeout=None, 
                 user='pi', group='pi', foreground=False):
        self.progname = progname
        self.user = user
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
        
           
    def run(self, action, daemon_mode=True):
        if (daemon_mode):
            logger.info('Daemon starting')
            # Set up signal handling

        signal.signal(signal.SIGTERM, stop_handler)
        signal.signal(signal.SIGINT, stop_handler)
        data_file = None

        try:
            logger.info('Starting sampling thread')
            
            do_every(config.getfloat('daemon', 'sampling_interval'), 
                     action)
            while take_samples:
                time.sleep(2)

            # Wait until all other threads have (or should have)
            # completed
            for n in range(int(round(config.getfloat('daemon', 'sampling_interval')))
                           + 1):
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


def cancel_sampling_threads():
    threads = threading.enumerate()
    for t in threads[1:]:
        t.cancel()        
    
    # If all the other threads have completed then exit; exit anyway
    # after a short time has passed
    t = time.time()
    while time.time() < t + 1 and len(threading.enumerate()) > 2:
        time.sleep(0.1)
    #sys.exit()


take_samples = True
def stop_handler(signal, frame):
    global take_samples
    logger.info('Stopping sampling threads...')
    take_samples = False
    cancel_sampling_threads()

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


def drop_root_privileges(user='nobody', group=None):
    if os.getuid() != 0:
        # Not root
        return

    # Get the UID and GID
    pwnam = pwd.getpwnam(user)

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
        return smbus.SMBus(bus_number)

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


def get_adc_devices(config, bus):
    '''Return MCP342x devices based on config settings'''

    r = {}
    sec = 'daemon'
    for comp in ('x', 'y', 'z', 'sensor_temperature'):
        if config.has_option(sec, comp + '_address'):
            if not config.has_option(sec, comp + '_channel'):
                raise Exception('Option ' + comp + 
                                '_channel is required in section ' + sec)

            address = awn.safe_eval(config.get(sec, comp + '_address'))
            channel = awn.safe_eval(config.get(sec, comp + '_channel'))

            # Some devices were constructed with single-ended ADC
            # boards. Enable a pseudo double-ended mode where IN+ and
            # IN- are measured by independed single-ended ADC
            # channels.
            pseudo_de = False
            if hasattr(address, '__iter__') or hasattr(channel, '__iter__'):
                if (not hasattr(address, '__iter__') or 
                    not hasattr(channel, '__iter__') or 
                    len(address) != 2 or 
                    len(channel) != 2):
                    raise Exception('Pseudo double-ended configuration '
                                    + 'requires two values for both '
                                    + 'address and channe')
                if comp == 'sensor_temperature':
                    raise Exception('Pseudo double-ended configuration '
                                    + ' for sensor temperature is '
                                    + 'not supported')
                pseudo_de = True
                    
            adc = MCP342x(bus, 
                          address=0,
                          channel=0,
                          resolution=18,
                          gain=1)
            for opt in ('resolution', 'gain', 'scale_factor', 'offset'):
                if config.has_option(sec, comp + '_' + opt):
                    v = awn.safe_eval(config.get(sec, comp + '_' + opt))
                    getattr(adc, 'set_' + opt)(v)
            
            if pseudo_de:
                adc.set_address(address[0])
                adc.set_channel(channel[0])
                adc2 = copy.copy(adc)
                adc2.set_address(address[1])
                adc2.set_channel(channel[1])
                # Offset must be zero otherwise it will be removed later
                adc2.set_offset(0)
                r[comp + '_ref'] = adc2
            else:
                adc.set_address(address)
                adc.set_channel(channel)

            r[comp] = adc
    return r


def get_aggregate_function(config, section, option):
    to_func = {'mean': np.mean,
               'median': np.median}
    
    if config.has_option(section, option):
        s = config.get(section, option)
        if s in to_func:
            return to_func[s]
        else:
            raise Exception('Unknown aggregate function: ' + s)
    else:
        return to_func['mean']
    
def voltage_to_deg_C(voltage, offset, scale):
    return (voltage - offset) / scale

def voltage_to_tesla(voltage, sensitivity=20000):
    # sensitivity in V/T
    return voltage / float(sensitivity)
               

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
    sampnum = str(sample_num) + ' '
    sample_num += 1
    print(sampnum + ' get_sample()')

    t = time.time()
    adc_list = []
    for comp in ('x', 'y', 'z'):
        if comp in adc_devices:
            adc_list.append(adc_devices[comp])
        if comp + '_ref' in adc_devices:
            adc_list.append(adc_devices[comp + '_ref'])

    mag_agg = get_aggregate_function(config, 'daemon', 'aggregate')
    md = MCP342x.convert_and_read_many(adc_list, 
                                       samples=config.getint('daemon', 
                                                             'oversampling'))
                                       #aggregate=mag_agg)

    r = {'sample_time': t}

    if 'sensor_temperature' in adc_devices:
        temp_adc = adc_devices['sensor_temperature']
        temp_oversampling = config.getint('daemon', 
                                          'sensor_temperature_oversampling')
        temp_agg = get_aggregate_function(config, 'daemon', 
                                          'sensor_temperature_aggregate')
    
        r['sensor_temperature'] = \
            temp_data = temp_adc.convert_and_read(samples=temp_oversampling,
                                                  aggregate=temp_agg)
    
    n = 0
    for comp in ('x', 'y', 'z'):
        if comp in adc_devices:
            r[comp + '_all_samples'] = md[n]
            r[comp] = mag_agg(md[n])
            n += 1
            if comp + '_ref' in adc_devices:
                for m in range(len(md[n])):
                    r[comp + '_all_samples'][m] -= md[n][m]
                r[comp] -= mag_agg(md[n])
                n += 1
        else:
            r[comp] = np.NaN

    print(sampnum + repr(r))
    print(sampnum + 'end get_sample()')
    return r


data_file = None
def record_sample():
    global data_file

    data = None
    # Ensure that only one thread attempts to access the I2C bus at
    # any time. It doesn't matter if the writing of data, or sending
    # it over the network, overlaps with the taking of the next
    # sample.
    logger.debug('Acquiring lock')
    if record_sample.lock.acquire(False):
        try:
            logger.debug('Acquired lock')
            data = get_sample()
        finally:
            logging.debug('Released lock')
            record_sample.lock.release()
    else:
        logger.debug('Could not acquire lock')

    if data is None:
        return

    comment_char = '#'
    separator = ','
    header = comment_char + 'sample_time'
    fstr = '{sample_time:.3f}'
    for c in ('x', 'y', 'z', 'sensor_temperature'):
        if c in data:
            header += separator + c
            fstr += '{separator}{' + c + ':.3f}'
    header += '\n'
    fstr += '\n'
    data['separator'] = separator
    data_file = awn.get_file_for_time(data['sample_time'], 
                                      data_file,
                                      config.get('raspitextdata', 'filename'),
                                      header=header)
    data_file.write(fstr.format(**data))

    mesg = create_awn_message(data)
    awn.message.print_packet(mesg)

    logger.debug('******* END: record_sample()')

record_sample.lock = threading.Lock()


def create_awn_message(data):
    site_id = config.getint('magnetometer', 'siteid')
    mesg = bytearray(1024)
    timestamp = [int(data['sample_time']),
                 int((data['sample_time'] % 1) * 32768)]
    awn.message.put_header(mesg, site_id, timestamp)
    mag_agg = get_aggregate_function(config, 'daemon', 'aggregate')
    for comp in ('x', 'y', 'z'):
        if comp in data:
            # Resolution and gain are lower nibble of config
            res_gain = adc_devices[comp].get_config() & 0x0f
            tag_id = awn.message.tag_data['mag_data_' + comp]['id']

            ba = struct.pack(awn.message.tag_data['mag_data_'+comp]['format'],
                             res_gain, data[comp])
            awn.message.put_data(mesg, tag_id, ba)
            
            key = 'mag_data_all_' + comp
            # if key in data and len(data[key]) > 1:
            #     tag_id = awn.message.tag_data['mag_data_all_' + comp]['id']
            #     data_len = 

    if 'sensor_temperature' in data:
        tag_id = awn.message.tag_data['magnetometer_temperature']['id']
        ba = struct.pack(awn.message.tag_data[\
                'magnetometer_temperature']['format'],
                         int(round(data['sensor_temperature'] * 100)))
        awn.message.put_data(mesg, tag_id, ba)
        

    awn.message.put_signature(mesg, hmac_key, 0, 0)
    return mesg[:awn.message.get_packet_length(mesg)]


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

    config = awn.read_config_file(args.config_file)
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


    if config.has_option('daemon', 'pidfile'):
        pidfile_path = config.get('daemon', 'pidfile')
    else:
        pidfile_path = None

    if config.has_option('daemon', 'i2c'):
        bus = get_smbus(config.get('daemon', 'i2c'))
    else:
        bus = get_smbus()

    # Is this the best place to drop privileges?
    drop_root_privileges(user=config.get('daemon', 'user'),
                         group=config.get('daemon', 'group'))
    
    hmac_key = config.get('magnetometer', 'key').decode('hex')

    # This should be called after dropping root privileges because it
    # uses safe_eval to convert strings to numbers or lists. Whilst
    # safe_eval ought to be safe it doesn't need root privileges.
    adc_devices = get_adc_devices(config, bus)
    magd = RasPiMagD(progname, 
                     pidfile_path=pidfile_path, 
                     user=config.get('daemon', 'user'),
                     foreground=args.foreground)

    if args.foreground:
        logger.info('running in foreground')
        magd.run(record_sample, daemon_mode=False)
    else:
        
        daemon_runner = daemon.runner.DaemonRunner(magd)
        if log_filehandle:
            daemon_runner.daemon_context.files_preserve=[log_filehandle.stream]
        try:
            daemon_runner.do_action()
        except Exception as e:
            logger.error('Daemon terminating with exception: ' + str(e) 
                         + ', type: ' + str(type(e)))

