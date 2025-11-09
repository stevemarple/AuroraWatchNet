#!/usr/bin/env python

import argparse
import binascii
from curses import ascii
import hmac
import logging
import math
import os
import re
import select
import socket
import struct
import subprocess
import sys
import termios
import time
import traceback
import tty

import aurorawatchnet as awn
import aurorawatchnet.eeprom
import aurorawatchnet.message

logger = logging.getLogger(__name__)

try:
    from configparser import SafeConfigParser as ConfigParser
except ImportError:
    # SafeConfigParser removed from later versions
    from configparser import ConfigParser


class DataMappingException(Exception):
    def __init__(self, message):
        super(DataMappingException, self).__init__(message)


class DuplicatedTagException(Exception):
    def __init__(self, message):
        super(DuplicatedTagException, self).__init__(message)


def log_uncaught_exception(ex_cls, ex, tb):
    # logger.critical(''.join(traceback.format_tb(tb)))
    logger.critical('Uncaught exception', exc_info=(ex_cls, ex, tb))
    t = time.time()
    write_to_log_file(t, iso_timestamp(t) + ' D Uncaught exception:'
                      + ''.join(traceback.format_tb(tb)) + '\n')


def get_file_for_time(t, file_obj, fstr, mode='a+b', buffering=0,
                      extension=None):
    """
    :param t: seconds since unix epoch
    :param file_obj:
    :param fstr:
    :param mode:
    :param buffering:
    :param extension:
    :return:
    """

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


aw_message_file = None


def write_message_to_file(t, message, fstr, savekey=None, extension=None):
    global aw_message_file
    try:
        if savekey:
            awn.message.put_signature(message, savekey,
                                      awn.message.get_retries(message),
                                      awn.message.get_sequence_id(message))

        aw_message_file = get_file_for_time(t, aw_message_file, fstr,
                                            extension=extension)
        aw_message_file.write(message)
        aw_message_file.flush()
        global close_after_write
        if close_after_write:
            aw_message_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print('Could not save message: ' + str(e))


# AuroraWatch realtime file
realtime_file = None


def write_aurorawatch_realtime_data(t, message_tags, fstr, extension):
    global realtime_file
    try:
        data = dict()
        for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
            if tag_name in message_tags:
                comp = struct.unpack(awn.message.tag_data[tag_name]['format'],
                                     str(message_tags[tag_name][0]))
                data[tag_name] = comp[1]

        realtime_file = get_file_for_time(t, realtime_file, fstr,
                                          extension=extension)
        realtime_file.write('{:05d}'.format(int(round(t)) % 86400))
        for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
            if tag_name in message_tags:
                data = struct.unpack(awn.message.tag_data[tag_name]['format'],
                                     str(message_tags[tag_name][0]))[1]
                realtime_file.write(' {:.1f}'.format(1e9 * awn.message.adc_counts_to_tesla(data)))
            else:
                realtime_file.write(' nan')
        realtime_file.write('\n')
        realtime_file.flush()
        global close_after_write
        if close_after_write:
            realtime_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print('Could not write realtime format data: ' + str(e))


# File object to which AuroraWatchNet text data format files are written
awnet_text_file = None


def write_aurorawatchnet_text_data(t, message_tags, fstr, extension):
    global awnet_text_file
    try:
        data = []
        found = False
        for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
            if tag_name in message_tags:
                found = True
                comp = struct.unpack(awn.message.tag_data[tag_name]['format'],
                                     message_tags[tag_name][0])
                data.append(1e9 * awn.message.adc_counts_to_tesla(comp[1] + 0.0))
            else:
                data.append(float('NaN'))

        for tag_name in ['magnetometer_temperature', 'system_temperature']:
            if tag_name in message_tags:
                found = True
                data.append(struct.unpack(awn.message.tag_data[tag_name]['format'],
                                          message_tags[tag_name][0])[0] / 100.0)
            else:
                data.append(float('NaN'))

        if 'supply_voltage' in message_tags:
            found = True
            data.append(struct.unpack(awn.message.tag_data['supply_voltage']['format'],
                                      message_tags['supply_voltage'][0])[0]
                        / 1000.0)
        else:
            data.append(float('NaN'))

        # Write to the file only if relevant tags found
        if found:
            awnet_text_file = get_file_for_time(t, awnet_text_file, fstr,
                                                extension=extension)
            # Write the time
            awnet_text_file.write(b'%.06f' % t)

            awnet_text_file.write(b'\t')
            awnet_text_file.write(b'\t'.join(map(lambda x: str(x).encode('ascii'), data)))
            awnet_text_file.write(b'\n')
            awnet_text_file.flush()
            global close_after_write
            if close_after_write:
                awnet_text_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.exception(e)
        print('Could not write aurorawatchnet format data: ' + str(e))


# File object to which AuroraWatchNet text data format files are written
system_temperature_file = None


def write_system_temperature(t, message_tags, fstr, extension):
    global system_temperature_file
    try:
        data = []
        found = False
        if 'system_temperature' in message_tags:
            found = True
            data.append(struct.unpack(awn.message.tag_data['system_temperature']['format'],
                                      message_tags['system_temperature'][0])[0] / 100.0)
        else:
            data.append(float('NaN'))

        # Write to the file only if relevant tags found
        if found:
            system_temperature_file = get_file_for_time(t, system_temperature_file, fstr,
                                                        extension=extension)
            # Write the time
            system_temperature_file.write(f'{t:.06f}'.encode('ascii'))

            system_temperature_file.write('\t'.encode('ascii'))
            system_temperature_file.write('\t'.join(map(str, data)).encode('ascii'))
            system_temperature_file.write('\n'.encode('ascii'))
            system_temperature_file.flush()
            global close_after_write
            if close_after_write:
                system_temperature_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.exception('Could not write system temperature data')
        print('Could not write system temperature data: ' + str(e))


# AuroraWatch realtime file
cloud_file = None


def write_cloud_data(t, message_tags, fstr, extension):
    global cloud_file
    try:
        tag_names = ['cloud_ambient_temperature',
                     'cloud_object1_temperature']
        if config.getboolean('cloud', 'dual_sensor'):
            tag_names.append('cloud_object2_temperature')
        tag_names.extend(['ambient_temperature', 'relative_humidity'])
        data = {}
        found = False
        for tag_name in ['cloud_ambient_temperature',
                         'cloud_object1_temperature',
                         'cloud_object2_temperature',
                         'ambient_temperature',
                         'relative_humidity']:
            if tag_name in message_tags:
                found = True
                data[tag_name] = awn.message.decode_cloud_temp(tag_name, str(message_tags[tag_name][0]))

        if found:
            cloud_file = get_file_for_time(t, cloud_file, fstr,
                                           extension=extension)
            # Write the time
            cloud_file.write('%.06f' % t)

            for tag_name in tag_names:
                if tag_name in message_tags:
                    data = awn.message.decode_cloud_temp(tag_name, str(message_tags[tag_name][0]))
                    cloud_file.write(' {:.2f}'.format(data))
                else:
                    cloud_file.write(' nan')
            cloud_file.write('\n')
            cloud_file.flush()
            global close_after_write
            if close_after_write:
                cloud_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print('Could not save cloud data: ' + str(e))


# AuroraWatch realtime file
raw_mag_samples_file = None


def write_raw_magnetometer_samples(t, message_tags, fstr, extension):
    """
    :param t: timestamp
    :param message_tags:
    :param fstr:
    :param extension:
    :return:

    Output format is timestamp, axes, value, raw sample1, raw sample2 ...
    where for axes 0 = x, 1 = y, 2 = z
    """
    global raw_mag_samples_file
    # try:
    if True:
        raw_mag_samples_file = get_file_for_time(t, raw_mag_samples_file,
                                                 fstr, extension=extension)

        def fmt_sample(n):
            return str(1e9 * awn.message.adc_counts_to_tesla(n))

        n = 0
        for comp in ['x', 'y', 'z']:
            tag_name = 'mag_data_' + comp
            if tag_name in message_tags:
                raw_mag_samples_file.write('%.06f\t' % t)
                raw_mag_samples_file.write(str(n))
                data = struct.unpack(awn.message.tag_data[tag_name]['format'], str(message_tags[tag_name][0]))
                raw_mag_samples_file.write('\t')
                raw_mag_samples_file.write(fmt_sample(data[1]))

                tag_name = 'mag_data_all_' + comp
                if tag_name in message_tags:
                    data = awn.message.decode_tag_array_of_longs(tag_name, len(message_tags[tag_name][0]),
                                                                 message_tags[tag_name][0])
                    raw_mag_samples_file.write('\t')
                    raw_mag_samples_file.write('\t'.join(map(fmt_sample, data)))

                raw_mag_samples_file.write('\n')

        global close_after_write
        if close_after_write:
            raw_mag_samples_file.close()


gnss_file = None


def write_gnss_data(timetamp_s, message_tags, fstr):
    global gnss_file
    tag_name = 'gnss_status'
    try:
        if tag_name in message_tags:
            epoch = awn.message.get_epoch(message)
            if len(message_tags[tag_name]) != 1:
                raise DuplicatedTagException('Tag "%s" occurs more than once' % tag_name)
            gps_t, is_valid, nav_system, num_sat, hdop = awn.message.decode_tag(tag_name, message_tags[tag_name][0], epoch)

            # If the GPS fix is valid then use the GPS fix time for timestamp and to compute the file name, otherwise
            # use the message time. This should stop files with bad time being created when the system starts up with
            # no time.
            t = gps_t if is_valid else int(timetamp_s)

            if 'gnss_location' in message_tags:
                data = awn.message.decode_tag_array_of_longs('gnss_location', len(message_tags['gnss_location'][0]),
                                                             message_tags['gnss_location'][0], epoch)
                if len(data) == 2:
                    data.append(float('NaN'))
            else:
                data = [float('NaN'), float('NaN'), float('NaN')]
            lat = data[0] * 1e-6
            lon = data[1] * 1e-6
            alt = data[2] * 1e-3
            gnss_file = get_file_for_time(t, gnss_file, fstr, mode='a+t', buffering=-1)
            d = f'{t:f}\t{is_valid:d}\t{nav_system}\t{num_sat:02d}\t{hdop:03.1f}\t{lat:10.6f}\t{lon:11.6f}\t{alt:8.3f}\n'
            gnss_file.write(d)
            gnss_file.flush()
            global close_after_write
            if close_after_write:
                gnss_file.close()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.exception(f'Could not save GNSS data: {e}')


generic_adc_data_file = None


def write_generic_adc_data(t, message_tags, fstr, extension, message, config=None):
    global generic_adc_data_file
    try:
        epoch = awn.message.get_epoch(message)
        generic_adc_data_file = get_file_for_time(t, generic_adc_data_file, fstr, extension=extension)
        if config and config.has_option('genericadcdata', 'mapping'):
            mapping = config.get('genericadcdata', 'mapping')
        else:
            mapping = None
        if config and config.has_option('genericadcdata', 'scale_factor'):
            scale_factor = awn.safe_eval(config.get('genericadcdata', 'scale_factor'))
        else:
            scale_factor = 1.0
        if config and config.has_option('genericadcdata', 'offset'):
            offset = awn.safe_eval(config.get('genericadcdata', 'offset'))
        else:
            offset = 0.0
        if config and config.has_option('genericadcdata', 'format'):
            format = config.get('genericadcdata', 'format')
        else:
            format = '%f'

        tag_name = 'adc_data'
        sep = '\t'
        eol = '\n'
        if tag_name in message_tags:
            if len(message_tags[tag_name]) != 1:
                raise DuplicatedTagException('Tag "%s" occurs more than once' % tag_name)
            data = awn.message.decode_tag(tag_name, message_tags[tag_name][0], epoch)

            res = data.pop(0)  # ADC resolution (bits)
            gain = data.pop(0)  # ADC gain
            if mapping is not None:
                if len(data) != len(mapping):
                    raise DataMappingException('Incorrect mapping size')
                data = [data[i] for i in mapping]
            a = []
            a.append('%.06f' % t)
            a.append('%d' % res)
            a.append('%d' % gain)
            for d in  data:
                a.append(format % ((d * scale_factor) + offset))

            generic_adc_data_file.write(sep.join(a))
            generic_adc_data_file.write(eol)

        global close_after_write
        if close_after_write:
            generic_adc_data_file.close()

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(e)
        pass


generic_data_files = {}


def write_generic_data(t, message_tags, extension, message, config=None):
    global generic_data_files
    epoch = awn.message.get_epoch(message)
    if not config:
        return

    sep = '\t'
    eol = '\n'

    # Add other generic data tags here as they are introduced
    for tag_name in ('gen_data_s32', ):
        try:
            if tag_name in message_tags:
                # There can be multiple copies of this tag, probably having different data IDs
                for tag_data in message_tags[tag_name]:
                    data = awn.message.decode_tag(tag_name, tag_data, epoch)
                    data_id = data.pop(0)
                    sec = 'genericdata:' + str(data_id)
                    if not config.has_section(sec) or not config.has_option(sec, 'filename'):
                        continue
                    fstr = config.get(sec, 'filename')

                    # Include scale factor, offset etc
                    data = manipulate_generic_data_array(sec, data, message_tags, epoch)

                    if config.has_option(sec, 'format'):
                        format = config.get(sec, 'format')
                    else:
                        format = '%f'

                    if data_id not in generic_data_files:
                        generic_data_files[data_id] = None
                    generic_data_files[data_id] = get_file_for_time(t, generic_data_files[data_id], fstr, extension=extension)
                    a = []
                    a.append('%.06f' % t)
                    for d in data:
                        # a.append(format % ((d * scale_factor) + offset))
                        a.append(format % d)

                    generic_data_files[data_id].write(sep.join(a).encode('ascii'))
                    generic_data_files[data_id].write(eol.encode('ascii'))

                    global close_after_write
                    if close_after_write:
                        generic_data_files[data_id].close()

        except KeyboardInterrupt:
            raise
        except Exception:
            print(traceback.format_exc())
            pass


def manipulate_generic_data_array(sec, data, message_tags, epoch):
    if config.has_option(sec, 'mapping'):
        mapping = config.get(sec, 'mapping')
    else:
        mapping = None
    if config.has_option(sec, 'scale_factor'):
        scale_factor = awn.safe_eval(config.get(sec, 'scale_factor'))
    else:
        scale_factor = 1.0
    if config.has_option(sec, 'offset'):
        offset = awn.safe_eval(config.get(sec, 'offset'))
    else:
        offset = 0.0

    if mapping is not None:
        if len(data) != len(mapping):
            raise DataMappingException('Incorrect mapping size')
        data = [data[i] for i in mapping]

    r = []
    for d in  data:
        r.append((d * scale_factor) + offset)

    if config.has_option(sec, 'appendtags'):
        for app_sec in config.get(sec, 'appendtags').split():
            a = app_sec.split(':')
            app_data_type = a[0]
            app_data_id = int(a[1])
            if app_data_type == 'genericdata':
                for tag_name in ('gen_data_s32',):
                    if tag_name in message_tags:
                        # There can be multiple tags of this type, but not necessarily with the correct data id
                        for tag_data in message_tags[tag_name]:
                            tmp_data = awn.message.decode_tag(tag_name, tag_data, epoch)
                            tmp_data_id = tmp_data.pop(0)
                            if tmp_data_id == app_data_id:
                                # Found the data to append
                                r.extend(manipulate_generic_data_array(app_sec, tmp_data, message_tags, epoch))

    return r


def iso_timestamp(t):
    """
    Create and ISO timestamp with microseconds. Uses UTC.
    :param t:
    :return:
    """
    us_str = '.%06d' % (int((t * 1e6) % 1e6))  # microseconds fraction
    return time.strftime('%Y-%m-%dT%H:%M:%S' + us_str, time.gmtime(t))


aw_log_file = None


def write_to_log_file(t, s):
    global config
    global aw_log_file
    if not config.has_option('logfile', 'filename'):
        return

    try:
        # Open as text, flush ourselves when finished here.
        aw_log_file = get_file_for_time(t, aw_log_file,
                                        config.get('logfile', 'filename'), mode='a+', buffering=-1)
        if isinstance(s, str):
            aw_log_file.write(s)
        else:
            aw_log_file.write(s.encode('ascii'))

        aw_log_file.flush()
        global close_after_write
        if close_after_write:
            aw_log_file.close()
    except KeyboardInterrupt:
        raise
    except Exception:
        logger.exception('Could not write to log file')


def log_message_events(t, message_tags, epoch, is_response=False):
    """
    Write important events in a message or its response to a log file.

    :param t:
    :param message_tags:
    :param epoch:
    :param is_response:
    :return:
    """
    global config
    global aw_log_file
    if not config.has_option('logfile', 'filename'):
        return

    # Generate the lines to write before attempting to open the file
    # to avoid creating empty files.
    lines = []
    ts = iso_timestamp(t)
    if is_response:
        prefix = ts + ' R '
    else:
        prefix = ts + ' M '

    tags_to_log = ['time_adjustment', 'reboot_flags', 'reboot',
                   'current_firmware', 'read_eeprom', 'eeprom_contents',
                   'upgrade_firmware', 'get_firmware_page', 'firmware_page', 'log_message']
    for tag_name in tags_to_log:
        if tag_name in message_tags:
            for tag_payload in message_tags[tag_name]:
                if tag_name == 'log_message' and isinstance(tag_payload, (bytes, bytearray)):
                    tag_payload = tag_payload.decode('ascii')
                data_repr = awn.message.format_tag_payload(tag_name, tag_payload, epoch,
                                                           '\n' + prefix + tag_name + ' ')
                lines.append(prefix + tag_name + ' ' + data_repr + '\n')


    # TODO
    # if ('upgrade_firmware' in message_tags and
    #     'firmware_page' not in message_tags):

    if lines:
        write_to_log_file(t, ''.join(lines))


def log_exception():
    t = time.time()
    message = ['Exception:']
    message.extend(traceback.format_exc().rstrip('\n').split('\n'))
    prefix = iso_timestamp(t) + ' D '
    write_to_log_file(t, ''.join(map(lambda s: prefix + s + '\n', message)))


def send_rt_message(host_info, message, response):
    awn.message.put_signature(message, host_info['key'],
                              awn.message.get_retries(message),
                              awn.message.get_sequence_id(message))
    sendto_or_log_error(rt_socket, message,
                        (host_info['ip'], host_info['port']))

    if response is not None:
        awn.message.put_signature(response, host_info['key'],
                                  awn.message.get_retries(response),
                                  awn.message.get_sequence_id(response))
        sendto_or_log_error(rt_socket, response,
                            (host_info['ip'], host_info['port']))


def sendto_or_log_error(sock, data, address):
    try:
        return sock.sendto(data, address)
    except KeyboardInterrupt:
        raise
    except Exception:
        logger.exception('Failed to send UDP packet')
        log_exception()
        return None


def open_control_socket():
    if config.has_option('controlsocket', 'filename'):
        if config.get('controlsocket', 'filename').lower() == 'none':
            return None
        if os.path.exists(config.get('controlsocket', 'filename')):
            os.remove(config.get('controlsocket', 'filename'))
        control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(config.get('controlsocket', 'filename'))
        # control_socket.setblocking(False)
        control_socket.listen(1)
    else:
        port_str = config.get('controlsocket', 'port')
        if port_str.lower() == 'none':
            return None
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # ord('A') = 65, ord('W') = 87
        control_socket.bind(('localhost', int(port_str)))
        control_socket.setblocking(False)
        control_socket.listen(0)
    return control_socket


# Process any CR or LF terminated messages which are in the buffer. Return a
# list of processed commands and any unused part of the buffer.
def handle_control_message(buf, pending_tags):
    responses = []

    while '\n' in buf:
        r = None
        unknown_control_message = False
        [cmd, buf] = buf.split(sep='\n', maxsplit=1)
        if cmd == '' or cmd.startswith('#'):
            continue

        if cmd.startswith('sampling_interval='):
            val = float(cmd.replace('sampling_interval=', '', 1)) * 16
            # pending_tags['sampling_interval'] = struct.pack('!L', val)
            pending_tags['sampling_interval'] = \
                struct.pack(awn.message.tag_data['sampling_interval']['format'],
                            val)
            r = 'sampling_interval:' + str(val / 16)

        elif cmd.startswith('upgrade_firmware='):
            version = str(cmd.replace('upgrade_firmware=', '', 1))
            try:
                handle_cmd_upgrade_firmware(version)
                r = 'upgrade_firmware:' + version
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f'Cannot process upgrade firmware control message {cmd!r}')
                logger.exception(e)

        elif cmd == 'reboot=TRUE':
            pending_tags['reboot'] = []
            r = 'reboot:TRUE'

        elif cmd.startswith('read_eeprom='):
            if 'eeprom_contents' in pending_tags:
                # The EEPROM write and EEPROM read both result in the same
                # tag being returned; allow only one at once.
                logger.warning('Incoming control message requested "read_eeprom" but a write_eeprom command is pending')
                r = 'ERROR: EEPROM write pending, cannot read'
            elif 'read_eeprom' in pending_tags:
                logger.warning('Incoming control message requested "read_eeprom" but a read_eeprom command is already pending')
                r = 'ERROR: an EEPROM read is already pending'
            else:
                edata = str(cmd.replace('read_eeprom=', '', 1)).split(',')
                address = int(edata[0], 0)
                sz = int(edata[1], 0)
                if sz < 1:
                    r = 'ERROR: bad value for size'
                else:
                    pending_tags['read_eeprom'] = struct \
                        .pack(awn.message.tag_data['read_eeprom']['format'],
                              address, sz)
                    r = 'read_eeprom:' + str(address) + ',' + str(sz)

        elif cmd.startswith('write_eeprom='):
            if 'read_eeprom' in pending_tags:
                # The EEPROM write and EEPROM read both result in the same
                # tag being returned; allow only one at once.
                logger.warning('Incoming control message requested "write_eeprom" but a read_eeprom command is pending')
                r = 'ERROR: EEPROM read pending, cannot write'
            elif 'eeprom_contents' in pending_tags:
                logger.warning('Incoming control message requested "write_eeprom" but a write_eeprom command is already pending')
                r = 'ERROR: EEPROM write command is already pending'
            else:
                edata = [int(x, 0) for x in
                         str(cmd.replace('write_eeprom=', '', 1)).split(',')]
                if len(edata) > 1:
                    pending_tags['eeprom_contents'] = \
                        struct.pack('!H' + str(len(edata) - 1) + 'B',
                                    *edata)
                    r = 'write_eeprom:' + ','.join(map(str, edata))
                else:
                    r = 'ERROR: no data to send'

        elif cmd.startswith('num_samples='):
            num_ctrl = map(int,
                           str(cmd.replace('num_samples=', '', 1)).split(','))
            pending_tags['num_samples'] = \
                struct.pack(awn.message.tag_data['num_samples']['format'],
                            num_ctrl[0], num_ctrl[1])
            r = 'num_samples:' + str(num_ctrl[0]) + ',' + str(num_ctrl[1])

        elif cmd.startswith('all_samples='):
            flag = (int(cmd.replace('all_samples=', '', 1)) != 0)
            pending_tags['all_samples'] = \
                struct.pack(awn.message.tag_data['all_samples']['format'],
                            flag)
            r = 'all_samples:' + str(flag)
        elif cmd.startswith('rio_freeze_scan='):
            scan_num = int(cmd.replace('rio_freeze_scan=', '', 1))
            if scan_num < 0 or scan_num > 255:
                scan_num = 255
            pending_tags['rio_freeze_scan'] = struct.pack(awn.message.tag_data['rio_freeze_scan']['format'], scan_num)
            r = 'rio_freeze_scan:' + str(scan_num)
        elif cmd.startswith('rio_connect='):
            rio_connect = int(cmd.replace('rio_connect=', '', 1))
            pending_tags['rio_connect'] = struct.pack(awn.message.tag_data['rio_freeze_scan']['format'], rio_connect)
        elif cmd == 'pending_tags':
            r = 'pending_tags:' + describe_pending_tags()
        elif cmd == 'clear_pending_tags':
            r = 'clear_pending_tags'
        else:
            unknown_control_message = True
            logger.error(f'Unknown control message {cmd!r}')
            r = f'ERROR: unknown control message {cmd!r}'

        if not unknown_control_message:
            print(f'Received control message {cmd!r}')
        if r:
            responses.append(r)

    return responses, buf


def get_firmware_details(version):
    filename = os.path.join(config.get('firmware', 'path'),
                            version + '.bin')
    crc_filename = os.path.join(config.get('firmware', 'path'),
                                version + '.crc')

    if not os.path.exists(filename):
        raise Exception('firmware file ' + filename + ' does not exist')
    if not os.path.exists(crc_filename):
        raise Exception('CRC file ' + crc_filename + ' does not exist')
    firmware_file = open(filename)
    firmware = firmware_file.read()
    firmware_file.close()

    if len(firmware) % awn.message.firmware_block_size != 0:
        raise Exception('firmware file ' + filename + ' not a multiple  of '
                        + str(awn.message.firmware_block_size) + ' bytes')

    # Be paranoid about the CRC file
    crc_file = open(crc_filename)
    crc_contents = crc_file.read()
    crc_file.close()
    crc_lines = crc_contents.splitlines()
    if len(crc_lines) != 1:
        raise Exception('Bad file format for ' + crc_filename)
    crc_cols = crc_lines[0].split()
    stated_crc_hex = crc_cols[0]
    stated_version = crc_cols[1]
    stated_crc = int(struct.unpack('>H',
                                   binascii.unhexlify(stated_crc_hex))[0])

    # The CRC check must be computed over the entire temporary
    # application section; extend as necessary
    temp_app_size = int((131072 - 4096) / 2)
    if len(firmware) < temp_app_size:
        padding = chr(0xFF) * (temp_app_size - len(firmware))
        padded_firmware = firmware + padding
    elif len(firmware) > temp_app_size:
        raise Exception('Firmware image too large ('
                        + str(len(firmware)) + ' bytes)')
    else:
        padded_firmware = firmware

    actual_crc = awn.message.crc16(padded_firmware)
    if actual_crc != stated_crc:
        raise Exception('Firmware CRC does not match with '
                        + crc_filename + ' ' + str(actual_crc)
                        + ' ' + str(stated_crc))
    if version != stated_version:
        raise Exception('Version does not match with ' + crc_filename)
    return stated_crc, int(len(firmware) / awn.message.firmware_block_size)


def handle_cmd_upgrade_firmware(version):
    if len(version) > awn.message.firmware_version_max_length:
        raise Exception('Bad version')

    version_str = str(version)
    # crc, num_pages = get_firmware_details(version.decode('ascii'))
    crc, num_pages = get_firmware_details(version_str)
    padded_version = version + ('\0' * (awn.message.firmware_version_max_length
                                        - len(version)))
    args = list(padded_version)
    args.append(num_pages)
    args.append(crc)
    pending_tags['upgrade_firmware'] = \
        struct.pack(awn.message.tag_data['upgrade_firmware']['format'], *args)


# Deal with any item requested in the incoming packet
def handle_packet_requests(message_tags):
    try:
        if 'get_firmware_page' in message_tags:
            # Write the page to requested tags
            packet_req_get_firmware_page(message_tags['get_firmware_page'][0])
    #    except Exception as e:
    #       None
    finally:
        pass


def packet_req_get_firmware_page(data):
    global requested_tags
    unpacked_data = struct.unpack(awn.message.tag_data['get_firmware_page']['format'], data)
    version = ''.join(unpacked_data[0:awn.message.firmware_version_max_length])
    version_str = version.split('\0', 1)[0]

    page_number, = unpacked_data[awn.message.firmware_version_max_length:]
    image_filename = os.path.join(config.get('firmware', 'path'),
                                  version_str + '.bin')
    try:
        image_file = open(image_filename)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error('Could not open ' + image_filename + ': ' + str(e))
        raise

    # Ensure file is closed in the case of any error
    try:
        image_file.seek(awn.message.firmware_block_size * page_number)
        fw_page = image_file.read(awn.message.firmware_block_size)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error('Could not get firmware page')
        logger.exception(e)
        return
    finally:
        # Ensure file is closed in all circumstances
        image_file.close()

    args = list(version)
    args.append(page_number)
    args.extend(list(fw_page))
    requested_tags['firmware_page'] = \
        struct.pack(awn.message.tag_data['firmware_page']['format'], *args)


def get_termios_baud_rate(baud):
    rates = {'9600': termios.B9600,
             '19200': termios.B19200,
             '38400': termios.B38400,
             '57600': termios.B57600,
             '115200': termios.B115200}

    if baud in rates:
        return rates[baud]
    else:
        return None


def readline_with_timeout(file_obj, timeout=None):
    """
    Read a line, with optional timeout.

    :param file_obj:
    :param timeout:
    :return:

    Read size bytes from the file. If a timeout is set it may return less characters as requested.
    With no timeout it will block until the requested number of bytes is read.
    """
    r = ''
    while True:
        start = time.time()
        ready, _, _ = select.select([file_obj], [], [], timeout)
        if ready:
            buf = file_obj.read(1)
            if buf == '\r' or buf == '\n':
                break  # done
            r += buf
        if timeout is not None:
            # subtract elapsed time so far
            timeout -= (time.time() - start)
            if timeout <= 0:
                break
    return r


def debug_print(level, mesg):
    global args
    if args.verbosity >= level:
        print(mesg)


def describe_pending_tags():
    global pending_tags
    r = []
    for k in pending_tags.keys():
        if k == 'eeprom_contents':
            address = struct.unpack('!H', pending_tags[k][0:2])[0]
            address_name = awn.eeprom.lookup_address(address)
            if address_name is None:
                # address_name = 'EEPROM ' + hex(address) + ': '
                # fmt = 'B' * (len(pending_tags[k]) - 2)
                # address_name = 'EEPROM (unknown address ' + hex(address) + ')'
                name = k + '(unknown address, ' + hex(address) + ')'
            else:
                name = k + '(' + address_name + ')'
            r.append(name)
        else:
            r.append(k)
    return ','.join(r)


def add_current_time_tag(message):
    if (config.has_option('ntp_status', 'filename') and
            config.has_option('ntp_status', 'max_age') and
            (not os.path.exists(config.get('ntp_status', 'filename')) or
             time.time() - os.stat(config.get('ntp_status', 'filename')).st_mtime
             > config.getfloat('ntp_status', 'max_age'))):
        # NTP status file is missing/old, assume NTP not running
        return
    awn.message.put_current_epoch_time(message)
    return


def fork_exec_cmd(cmd):
    """
    Fork and run a command.

    :param cmd:
    :return:
    """
    t = time.time()
    write_to_log_file(t,
                      '%s D Running command "%s"\n' % (iso_timestamp(t), cmd))
    if os.fork() == 0:
        # Child process
        try:
            subprocess.check_call(data_quality_cmd,
                                  shell=True)
        finally:
            # Ensure child terminates if exec()
            # failed. Don't call any cleanup code.
            os._exit(1)


# ==========================================================================
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
sys.excepthook = log_uncaught_exception

daemon_start_time = time.time()
# Parse command line arguments
parser = \
    argparse.ArgumentParser(description='AuroraWatch data recording daemon')

parser.add_argument('-c', '--config-file',
                    default='/etc/awnet.ini',
                    help='Configuration file')
parser.add_argument('-d', '--daemon', action='store_true',
                    help='Run as daemon')
parser.add_argument('--acknowledge', action='store_true',
                    default=None,
                    help='Transmit acknowledgement')
parser.add_argument('--no-acknowledge', action='store_false',
                    dest='acknowledge',
                    default=None,
                    help="Don't transmit acknowledgement")
parser.add_argument('--read-only', action='store_true',
                    default=None,
                    help='Open device file read-only (implies --no-acknowledge)')
parser.add_argument('--ignore-digest', action='store_true',
                    help='Ignore HMAC-MD5 digest')
parser.add_argument('--device', metavar='FILE', help='Device file')
parser.add_argument('-v', '--verbose', dest='verbosity', action='count',
                    default=0, help='Increase verbosity')

args = parser.parse_args()

config = awn.read_config_file(args.config_file)

rt_transfer = awn.get_rt_transfer_info(config)
if rt_transfer:
    rt_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
else:
    rt_socket = None

# Should the device be opened read-only? Some need setup strings
# writing to them even if acknowledgements are not sent.
if args.read_only is not None:
    read_only = args.read_only
elif config.has_option('daemon', 'read_only'):
    read_only = config.getboolean('daemon', 'read_only')
else:
    read_only = False

# Should acknowledgements be sent?
if read_only:
    # Can never acknowledge in read-only mode
    acknowledge = False
elif args.acknowledge is not None:
    acknowledge = args.acknowledge
elif config.has_option('daemon', 'acknowledge'):
    acknowledge = config.getboolean('daemon', 'acknowledge')
else:
    acknowledge = True

# Do not ignore digest when acknowledgements are required
if args.ignore_digest and acknowledge:
    print('--ignore-digest requires --no-acknowledge or --read-only')

if args.daemon:
    import daemon

    pidfile = None
    if config.has_option('daemon', 'pidfile'):
        import lockfile

        pidfile = lockfile.FileLock(config.get('daemon', 'pidfile'),
                                    threaded=False)
        if pidfile.is_locked():
            print('daemon already running')
            exit(1)
    daemon.DaemonContext(pidfile=pidfile).open()

comms_block_size = int(config.get('serial', 'blocksize'))

close_after_write = config.getboolean('daemon', 'close_after_write')
daemon_connection = config.get('daemon', 'connection')
control_socket = None

if args.device:
    device_filename = args.device
    daemon_connection = 'serial'  # Implied by the command line argument
else:
    device_filename = config.get('serial', 'port')

if device_filename == '-':
    device = os.sys.stdin
    device_socket = None
    acknowledge = False  # Cannot send acknowledgements

elif daemon_connection == 'ethernet':
    # Connect via ethnernet
    device = None
    local_port = int(config.get('ethernet', 'local_port'))
    local_ip = config.get('ethernet', 'local_ip')
    device_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
    device_socket.bind((local_ip, local_port))
    device_socket.setblocking(False)
    control_socket = open_control_socket()
    comms_block_size = 0

    write_to_log_file(daemon_start_time, iso_timestamp(daemon_start_time) + ' D Daemon started\n')

else:
    if read_only:
        device = open(device_filename, 'rb', 0)
    else:
        device = open(device_filename, 'a+b', 0)
        write_to_log_file(daemon_start_time, iso_timestamp(daemon_start_time) + ' D Daemon started\n')

    device_socket = None

if device_filename == '-' or acknowledge is False:
    control_socket = None

elif device:
    if device.isatty():
        if args.verbosity:
            print('Reading from ' + device_filename)
        tty.setraw(device, termios.TCIOFLUSH)
        term_attr = termios.tcgetattr(device)
        term_attr[4] = term_attr[5] = get_termios_baud_rate(config.get('serial', 'baudrate'))
        termios.tcsetattr(device, termios.TCSANOW, term_attr)

        # Discard any characters already present in the device
        termios.tcflush(device, termios.TCIOFLUSH)

        device_setup_cmds = config.get('serial', 'setup').split(';')
        if len(device_setup_cmds):
            debug_print(2, 'Setup device... ')
            device.flush()
            time.sleep(1)
            device.write('+++')
            device.flush()
            time.sleep(1.2)
            termios.tcflush(device, termios.TCIFLUSH)

            # print(readline_with_timeout(device, 1))
            for cmd in device_setup_cmds:
                device.write(cmd)
                device.write('\r')
                debug_print(3, cmd)
                debug_print(3, readline_with_timeout(device, 1))

            device.write('ATDN\r')
            device.flush()
            debug_print(3, 'ATDN')
            debug_print(3, readline_with_timeout(device, 1))
            debug_print(2, '... done')

        control_socket = open_control_socket()

    else:
        # Plain files should be opened read-only
        device.close()
        device = open(device_filename, 'r', 0)
        control_socket = None
        acknowledge = False

control_socket_conn = None
control_buffer = ''

# Pending tags are persistent and are removed when acknowledged
pending_tags = {}

select_list = []
if device is not None:
    select_list.append(device)
if device_socket is not None:
    select_list.append(device_socket)

if control_socket is not None:
    select_list.append(control_socket)

if not config.has_option('magnetometer', 'key'):
    print('Config file missing key from magnetometer section')
    exit(1)

hmac_key = binascii.unhexlify(config.get('magnetometer', 'key'))
if len(hmac_key) != 16:
    print('key must be 32 characters long')
    exit(1)

saved_hmac_key = None
if config.has_option('awpacket', 'key'):
    saved_hmac_key = binascii.unhexlify(config.get('awpacket', 'key'))
    if len(saved_hmac_key) != 16:
        print('key must be 32 characters long')
        exit(1)

buf = bytearray()

data_quality_extension = None
# Remember previous value of data quality flag (excludes message retries).
previous_rt_data_quality = False
running = True
while running:
    try:
        if control_socket_conn is None:
            inputready, outputready, exceptready = select.select(select_list, [], [])
        else:
            select_list2 = select_list[:]
            select_list2.append(control_socket_conn)
            inputready, outputready, exceptready = select.select(select_list2, [], [])
    except KeyboardInterrupt:
        print('Interrupted by user')
        now = time.time()
        write_to_log_file(now, iso_timestamp(now) + ' D Daemon stopped (keyboard interrupt)\n')
        break
    except select.error as e:
        print('select error: ' + str(e))
        break
    except socket.error as e:
        print('socket error: ' + str(e))
        break

    for fd in inputready:
        # print('FD: ' + str(fd))

        if fd in [device, device_socket]:
            if fd == device:
                # Serial/file device, read and process one byte at a time
                s = device.read(1)
                remote_addr = None
            else:
                # Network device. Read all data from the packet. Don't
                # carry over data from old packets because
                # validate_packet() only gets called once and old data
                # is not currently removed fast enough. Ensure that
                # the start of the packet is put into the start of the
                # buffer so that validate_packet() immediately sees
                # the new data.
                buf = bytearray()
                s, remote_addr = device_socket.recvfrom(1024)

            if len(s) == 0:
                # end of file
                running = False
                break
            elif len(s) == 1:
                buf.append(s)
            else:
                buf.extend(s)
            #            if ascii.isprint(s):
            #                print(s)
            #            else:
            #                print(hex(ord(s)))

            message = awn.message.validate_packet(buf, hmac_key, args.ignore_digest)
            response = None

            if message is not None:
                message_received = time.time()
                data_quality_warning = False
                if config.has_option('dataqualitymonitor', 'directory'):
                    # Any file/directory counts as a warning
                    try:
                        data_quality_warning = bool(os.listdir(config.get('dataqualitymonitor', 'directory')))
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        pass
                elif config.has_option('dataqualitymonitor', 'filename'):
                    data_quality_warning = \
                        os.path.isfile(config.get('dataqualitymonitor',
                                                  'filename'))

                if awn.message.is_data_quality_flag_set(message):
                    data_quality_warning = True

                if data_quality_warning:
                    if data_quality_extension is None:
                        write_to_log_file(message_received,
                                          iso_timestamp(message_received) + ' D Data quality warning detected\n')

                    data_quality_extension = config.get('dataqualitymonitor', 'extension')
                elif data_quality_extension is not None:
                    write_to_log_file(message_received,
                                      iso_timestamp(message_received) + ' D Data quality warning removed\n')
                    data_quality_extension = None

                if not awn.message.get_retries(message):
                    data_quality_cmd = None
                    if awn.message.is_data_quality_flag_set(message) \
                            and not previous_rt_data_quality \
                            and config.has_option('daemon', 'warning_command'):
                        data_quality_cmd = config.get('daemon', 'warning_command')
                    elif not awn.message.is_data_quality_flag_set(message) \
                            and previous_rt_data_quality \
                            and config.has_option('daemon', 'ok_command'):
                        data_quality_cmd = config.get('daemon',
                                                      'ok_command')

                    previous_rt_data_quality = \
                        awn.message.is_data_quality_flag_set(message)
                    if data_quality_cmd:
                        fork_exec_cmd(data_quality_cmd)

                if (device and device.isatty()) or device_socket:
                    message_time = message_received
                else:
                    message_time = None
                if args.verbosity:
                    # print('=============')
                    # if device.isatty():
                    #     print('Valid message received ' + str(time.time()))
                    awn.message.print_packet(message, message_time=message_time)

                timestamp = awn.message.get_timestamp(message)
                epoch = awn.message.get_epoch(message)
                epoch_adjustment = (epoch - 1970) * awn.message.SECONDS_PER_AVG_YEAR
                timestamp_s = timestamp[0] + timestamp[1] / 32768.0
                timestamp_s += epoch_adjustment
                message_tags = awn.message.parse_packet(message)
                awn.message.tidy_pending_tags(pending_tags, message_tags)

                if acknowledge:
                    # Not a file, so send a acknowledgement
                    flags = awn.message.flags['response'] | awn.message.epoch_flags[awn.message.get_epoch(message)]
                    response = bytearray(1024)
                    awn.message.put_header(response,
                                           site_id=awn.message.get_site_id(message),
                                           timestamp=timestamp,
                                           flags=flags)
                    # awn.message.put_current_epoch_time(response)
                    # Add current time, subject to NTP running
                    add_current_time_tag(response)

                    # Handle packet requests. These tags live only for the
                    # duration between receiving the request and sending the
                    # response.
                    requested_tags = {}
                    handle_packet_requests(message_tags)
                    for tag_name in requested_tags:
                        awn.message.put_data(response,
                                             awn.message.tag_data[tag_name]['id'],
                                             requested_tags[tag_name])

                    for tag_name in pending_tags:
                        if tag_name != 'reboot':
                            awn.message.put_data(response, awn.message.tag_data[tag_name]['id'], pending_tags[tag_name])

                    # Send the reboot command last
                    if 'reboot' in pending_tags:
                        awn.message.put_data(response,
                                             awn.message.tag_data['reboot']['id'],
                                             pending_tags['reboot'])

                    # Add padding to round up to a multiple of block size
                    if comms_block_size:
                        padding_length = (comms_block_size -
                                          ((awn.message.get_packet_length(response) +
                                            awn.message.signature_block_length) % comms_block_size))
                        awn.message.put_padding(response, padding_length)

                    awn.message.put_signature(response, hmac_key,
                                              awn.message.get_retries(message),
                                              awn.message.get_sequence_id(message))

                    # Trim spare bytes from end of buffer
                    del response[awn.message.get_packet_length(response):]
                    if fd == device:
                        device.write(response)
                    else:
                        count = device_socket.sendto(response, remote_addr)

                    if args.verbosity:
                        # print('Response: ------')
                        awn.message.print_packet(response,
                                                 message_time=message_time)

                if config.has_option('awpacket', 'filename'):
                    # Save the message and response
                    write_message_to_file(timestamp_s, message,
                                          config.get('awpacket', 'filename'),
                                          savekey=saved_hmac_key,
                                          extension=data_quality_extension)
                    if response is not None:
                        write_message_to_file(timestamp_s, response,
                                              config.get('awpacket', 'filename'),
                                              savekey=saved_hmac_key,
                                              extension=data_quality_extension)

                if (config.has_option('aurorawatchrealtime', 'filename') and
                        not awn.message.is_response_message(message)):
                    write_aurorawatch_realtime_data(timestamp_s,
                                                    message_tags,
                                                    config.get('aurorawatchrealtime', 'filename'),
                                                    data_quality_extension)

                # Keep logfile of important events
                if config.has_option('logfile', 'filename'):
                    log_message_events(timestamp_s, message_tags, epoch,
                                       is_response=awn.message.is_response_message(message))
                    if response is not None:
                        response_tags = awn.message.parse_packet(response)
                        log_message_events(timestamp_s, response_tags, epoch,
                                           is_response=True)

                if (config.has_option('cloud', 'filename') and
                        not awn.message.is_response_message(message)):
                    write_cloud_data(timestamp_s, message_tags,
                                     config.get('cloud', 'filename'),
                                     data_quality_extension)

                if (config.has_option('awnettextdata', 'filename') and
                        not awn.message.is_response_message(message)):
                    write_aurorawatchnet_text_data(timestamp_s,
                                                   message_tags,
                                                   config.get('awnettextdata',
                                                              'filename'),
                                                   data_quality_extension)

                if (config.has_option('system_temperature', 'filename') and
                    not awn.message.is_response_message(message)):
                    write_system_temperature(timestamp_s,
                                             message_tags,
                                             config.get('system_temperature', 'filename'),
                                             data_quality_extension)

                if (config.has_option('magnetometerrawsamples', 'filename')
                        and not awn.message.is_response_message(message)):
                    write_raw_magnetometer_samples(timestamp_s, message_tags,
                                                   config.get('magnetometerrawsamples', 'filename'),
                                                   data_quality_extension)

                if config.has_option('gnss', 'filename') and not awn.message.is_response_message(message):
                    write_gnss_data(timestamp_s, message_tags,
                                    config.get('gnss', 'filename'))

                if not awn.message.is_response_message(message):
                    write_generic_data(timestamp_s, message_tags, data_quality_extension, message, config)

                # Deprecated?
                if config.has_option('genericadcdata', 'filename') and not awn.message.is_response_message(message):
                    write_generic_adc_data(timestamp_s, message_tags,
                                           config.get('genericadcdata', 'filename'),
                                           data_quality_extension, message, config)

                # Realtime transfer must be last since it alters the
                # message and response signature. Don't forward any
                # messages is there is an issue with data quality.
                if data_quality_extension is None:
                    for rt in rt_transfer:
                        send_rt_message(rt, message, response)

            else:
                response = None

        elif fd == control_socket:
            if control_socket_conn is not None:
                try:
                    control_socket_conn.shutdown(socket.SHUT_RDWR)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    pass
            control_socket_conn = None
            try:
                (control_socket_conn, client_address) = control_socket.accept()
                control_socket_conn.settimeout(10)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error('Control socket error')
                logger.exception(e)
                control_socket_conn = None

        elif fd == control_socket_conn:
            try:
                s = control_socket_conn.recv(1024)
                if s:
                    s = s.decode('ascii')
                    control_buffer += s
                    mesg, control_buffer = handle_control_message(control_buffer, pending_tags)
                    if mesg:
                        fd.send(('\n'.join(mesg) + '\n').encode('ascii'))
                else:
                    # EOF on control socket connection
                    control_socket_conn.shutdown(socket.SHUT_RDWR)
                    control_socket_conn.close()
                    control_socket_conn = None
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error('Could not process control messages in {control_buffer!r}')
                logger.exception(e)
                control_socket_conn = None
        else:
            print('Other: ' + str(fd))
