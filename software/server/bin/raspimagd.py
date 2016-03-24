#!/usr/bin/env python

import argparse
import copy
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

bus = None
adc_devices = None

def record_data():
    global bus
    global adc_devices

    if config.has_option('daemon', 'i2c'):
        bus = get_smbus(config.get('daemon', 'i2c'))
    else:
        bus = get_smbus()

    # This should be called after dropping root privileges because
    # it uses safe_eval to convert strings to numbers or
    # lists (not guaranteed safe!)
    adc_devices = get_adc_devices(config, bus)

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    try:
        get_log_file_for_time(time.time(), log_filename)
        logger.info('Starting sampling thread')

        do_every(config.getfloat('daemon', 'sampling_interval'), 
                 record_sample)
        while take_samples:
            time.sleep(2)

        # Wait until all other threads have (or should have)
        # completed
        for n in range(int(round(config.getfloat('daemon', 
                                                 'sampling_interval')))
                       + 1):
            if threading.activeCount() == 1:
                break
            time.sleep(1)


    except Exception as e:
        print(e)
        get_log_file_for_time(time.time(), log_filename)
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
    get_log_file_for_time(time.time(), log_filename)
    logger.info('Stopping sampling threads')
    take_samples = False
    cancel_sampling_threads()

def do_every (interval, worker_func, iterations = 0):
    if iterations != 1:
        # Schedule the next worker thread. Aim to start at the next
        # multiple of sampling interval. Take current time, add 1.25
        # of the interval and then find the nearest
        # multiple. Calculate delay required.
        now = time.time()
        delay = round_to(now + (1.25 * interval), interval) - now
        # Avoid lockups by many threads piling up. Impose a minimum delay
        if delay < 0.1:
            delay = 0.1
        t = threading.Timer(delay,
                            do_every, 
                            [interval, worker_func, 
                             0 if iterations == 0 else iterations-1])
        t.daemon = True
        t.start()
    try:
        worker_func()
    except Exception as e:
        get_log_file_for_time(time.time(), log_filename)
        logger.error(traceback.format_exc())


def round_to(n, nearest):
    return round(n / float(nearest)) * nearest

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
               
              
def get_sample():
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

    # Take CPU temperature as system temperature
    r['system_temperature'] = np.NaN
    with open('/sys/class/thermal/thermal_zone0/temp') as f:
        r['system_temperature'] = float(f.read().strip())/1000

    return r


# Each sampling action is made by a new thread. This function uses a
# lock to avoid contention for the I2C bus. If the lock cannot be
# acquired the attempt is abandoned. The lock is released after the
# sample has been taken. This means two instances of record_sample()
# can occur at the same time, whilst the earlier one writes data and
# possibly sends a real-time data packet over the network. A second
# lock (write_to_csv_file.lock) is used to avoid contention on writing
# results to a file.
def record_sample():
    global data_quality_ok
    global ntp_ok
    data = None
    get_log_file_for_time(time.time(), log_filename, delay=False)
    logger.debug('record_sample(): acquiring lock')
    if record_sample.lock.acquire(False):
        try:
            logger.debug('record_sample(): acquired lock')
            data = get_sample()
        finally:
            logging.debug('record_sample(): released lock')
            record_sample.lock.release()
    else:
        logger.error('record_sample(): could not acquire lock')

    if data is None:
        return

    if (config.has_option('dataqualitymonitor', 'filename') and
        os.path.isfile(config.get('dataqualitymonitor', 
                                  'filename'))):
        # Problem with data quality
        if data_quality_ok:
            # Not known previously, log
            get_log_file_for_time(time.time(), log_filename)
            logger.warning('Data quality warning detected')
            data_quality_ok = False
    elif not data_quality_ok:
            get_log_file_for_time(time.time(), log_filename)
            logger.info('Data quality warning removed')
            data_quality_ok = True
    
    if (config.has_option('ntp_status', 'filename') and 
        config.has_option('ntp_status', 'max_age') and 
        (not os.path.exists(config.get('ntp_status', 'filename')) or 
         time.time() - os.stat(config.get('ntp_status', 'filename')).st_mtime
         > config.get('ntp_status', 'max_age'))):
        # NTP status file is missing/old, assume NTP not running
        if ntp_ok:
            get_log_file_for_time(time.time(), log_filename)
            logger.warning('NTP not running/synchronized')
            ntp_ok = False
    elif not ntp_ok:
        get_log_file_for_time(time.time(), log_filename)
        logger.info('NTP problem resolved')
        ntp_ok = True

    ext = None
    if not data_quality_ok or not ntp_ok:
        ext = config.get('dataqualitymonitor', 'extension')


    if config.has_option('awnettextdata', 'filename'):
        write_to_txt_file(data, ext)

    if config.has_option('raspitextdata', 'filename'):
        write_to_csv_file(data, ext)

    #mesg = create_awn_message(data)
    #awn.message.print_packet(mesg)
    sys.stdout.write(data_to_str(data))

record_sample.lock = threading.Lock()


def data_to_str(data, separator=',', comments='#', want_header=False):
    separator = ','
    header = comments + 'sample_time'
    fstr = '{sample_time:.3f}'
    d = dict(sample_time=data['sample_time'], separator=separator)
    for c in ('x', 'y', 'z', 'sensor_temperature'):
        if c in data:
            d[c] = data[c]
            header += separator + c
            fstr += '{separator}{' + c + ':.3f}'
    header += '\n'
    fstr += '\n'
    s = fstr.format(**d)
    if want_header:
        return s, header
    else:
        return s

def write_to_csv_file(data, extension):
    # Acquire lock, wait if necessary
    logger.debug('write_to_csv_file(): acquiring lock')
    with write_to_csv_file.lock:
        logger.debug('write_to_csv_file(): acquired lock')
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
        write_to_csv_file.data_file = \
            awn.get_file_for_time(data['sample_time'], 
                                  write_to_csv_file.data_file,
                                  config.get('raspitextdata', 'filename'),
                                  extension=extension,
                                  header=header)
        write_to_csv_file.data_file.write(fstr.format(**data))


write_to_csv_file.lock = threading.Lock()
write_to_csv_file.data_file = None

# Write data in standard AuroraWatchNet format
def write_to_txt_file(data, extension):
    # Acquire lock, wait if necessary
    logger.debug('write_to_txt_file(): acquiring lock')
    with write_to_txt_file.lock:
        logger.debug('write_to_txt_file(): acquired lock')
        comment_char = '#'
        separator = ','
        fstr = '%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\n'
        write_to_txt_file.data_file = \
            awn.get_file_for_time(data['sample_time'], 
                                  write_to_txt_file.data_file,
                                  config.get('awnettextdata', 'filename'),
                                  extension=extension)

        x = data['x'] if 'x' in data else np.NaN
        y = data['y'] if 'y' in data else np.NaN
        z = data['z'] if 'z' in data else np.NaN
        write_to_txt_file.data_file.write(fstr % (data['sample_time'],
                                                  x, y, z,
                                                  data['sensor_temperature'],
                                                  data['system_temperature'],
                                                  np.NaN))

write_to_txt_file.lock = threading.Lock()
write_to_txt_file.data_file = None


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
        

    hmac_key = config.get('magnetometer', 'key').decode('hex')
    awn.message.put_signature(mesg, hmac_key, 0, 0)
    return mesg[:awn.message.get_packet_length(mesg)]


def get_log_file_for_time(t, fstr, 
                          mode='a', 
                          delay=True, 
                          name=__name__):
    if fstr is None:
        return
    fh = get_log_file_for_time.fh
    tmp_name = time.strftime(fstr, time.gmtime(t))

    if fh is not None:
        if fh.stream and fh.stream.closed:
            fh = None
        elif fh.stream.name != tmp_name:
            # Filename has changed
            fh.close()
            fh = None
        
    if fh is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            os.makedirs(p)

        fh = logging.FileHandler(tmp_name, mode=mode, delay=delay)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                                      datefmt='%Y-%m-%dT%H:%M:%SZ')
        fh.setFormatter(formatter)
        logger = logging.getLogger(name)
        for h in logger.handlers:
            # Only remove file handlers 
            if isinstance(h, logging.FileHandler):
                logger.removeHandler(h)
        logger.addHandler(fh)


get_log_file_for_time.fh = None


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

    args = parser.parse_args()

    config = awn.read_config_file(args.config_file)
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format, datefmt='%Y-%m-%dT%H:%M:%SZ')

    log_filename = None
    if config.has_option('logfile', 'filename'):
        log_filename = config.get('logfile', 'filename')
        
    get_log_file_for_time(time.time(), log_filename)
    logger.info(progname + ' started')

    data_quality_ok = True
    ntp_ok = True
    record_data()

