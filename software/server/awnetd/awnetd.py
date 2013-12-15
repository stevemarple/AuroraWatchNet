#!/usr/bin/env python

import argparse
import binascii
from curses import ascii 
import math
import os
import re
import select
import socket
import struct
import sys
import termios
import time
import tty

import hmac
import AW_Message
import AWEeprom

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser



def read_config_file(config_file):
    global config
    global site_ids
    config = SafeConfigParser()
    
    config.add_section('daemon')
    config.set('daemon', 'pidfile', '/tmp/test.pid')
    config.set('daemon', 'user', 'nobody')
    config.set('daemon', 'group', 'nogroup')
    config.set('daemon', 'connection', 'serial')

    config.add_section('controlsocket')
    # ord('A') = 65, ord('W') = 87 
    config.set('controlsocket', 'port', '6587')

    config.add_section('serial')
    config.set('serial', 'port', '/dev/ttyACM0')
    config.set('serial', 'baudrate', '9600')
    config.set('serial', 'blocksize', '12')
    config.set('serial', 'setup', '')
    
    # For ethernet
    config.add_section('ethernet')
    config.set('ethernet', 'local_port', '6588')
    config.set('ethernet', 'local_ip', '')

#    config.add_section('magnetometer')
#    config.set('magnetometer', 'datatransferdelay', '2')

    config.add_section('firmware')
    config.set('firmware', 'path', '/tmp/firmware')
    
    # TOD: Handle multiple stations 
    config.add_section('s')
    config.set('s', 'path', '/s/aurorawatch/net')
    if config_file:
        config_files_read = config.read(config_file)
        print('## Config files read: ' + ', '.join(config_files_read))

    if config.has_option('s', 'siteids'):
        site_ids = config.get('s', 'siteids').split()
    else:
        site_ids = []


def get_file_for_time(timestamp, file_obj, fstr, buffering=-1):
    seconds = timestamp[0] + timestamp[1]/32768.0
    tmp_name = time.strftime(fstr, time.gmtime(seconds))
    if file_obj is not None and tmp_name != file_obj.name:
        # Filename has changed
        file_obj.close()
        file_obj = None
        
    if file_obj is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            os.makedirs(p)

        file_obj = open(tmp_name, 'a+', buffering)
    
    return file_obj

aw_message_file = None
def write_message_to_file(timestamp, message, fstr):
    global aw_message_file        
    try:
        aw_message_file = get_file_for_time(timestamp, aw_message_file, fstr)
        aw_message_file.write(message);
        aw_message_file.flush()
    except Exception as e:
        print('Could not save message: ' + str(e))
    
# AuroraWatch realtime file
realtime_file = None
def write_aurorawatch_realtime_data(timestamp, data):
    global realtime_file
    seconds = long(round(timestamp[0] + (timestamp[1]/32768.0)))
    tmp_name = time.strftime(config.get('aurorawatchrealtime', 
                                       'filename'),
                            time.gmtime(seconds))
    if realtime_file is not None and tmp_name != realtime_file.name:
        # Filename has changed
        realtime_file.close()
        realtime_file = None
            
    if realtime_file is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            try:
                os.makedirs(p)
            except Exception as e:
                print('Could not make directory ' + p + str(e))
                return
        
        try:
            realtime_file = open(tmp_name, 'a+', 1)
        except Exception as e:
            print('Exception was ' + str(e))
            realtime_file = None
    
    if realtime_file is not None:
        realtime_file.write('{:05d}'.format(seconds % 86400))
        for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
            if tag_name in data:
                realtime_file.write(' {:.1f}'.format(1e9 * AW_Message.adc_counts_to_tesla(data[tag_name])))
            else:
                realtime_file.write(' nan')
        realtime_file.write('\n')

# File object to which AuroraWatchNet text data format files are written    
awnet_text_file = None
def write_aurorawatchnet_text_data(timestamp, message_tags):
    if not config.has_option('awnettextdata', 'filename'):
        return
    
    global awnet_text_file
    unix_time = timestamp[0] + timestamp[1]/32768.0
    
    tmp_name = time.strftime(config.get('awnettextdata', 'filename'),
                            time.gmtime(unix_time))
    if awnet_text_file is not None and tmp_name != awnet_text_file.name:
        # Filename has changed
        awnet_text_file.close()
        awnet_text_file = None
            
    if awnet_text_file is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            try:
                os.makedirs(p)
            except Exception as e:
                print('Could not make directory ' + p + str(e))
                return
        
        try:
            awnet_text_file = open(tmp_name, 'a+', 1)
        except Exception as e:
            print('Exception was ' + str(e))
            awnet_text_file = None
    
    if awnet_text_file is not None:
        data = [ ]
        for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
            if tag_name in message_tags:
                comp = struct.unpack(AW_Message.tag_data[tag_name]['format'], 
                                     str(message_tags[tag_name][0]))
                data.append(1e9 * AW_Message.adc_counts_to_tesla(comp[1] + 0.0))
            else:
                data.append(float('NaN'));
        
        for tag_name in ['magnetometer_temperature', 'system_temperature']:
            if tag_name in message_tags:
                data.append(struct.unpack(AW_Message.tag_data[tag_name] \
                                              ['format'], 
                                          str(message_tags[tag_name][0]))[0] / 
                            100.0)
            else:
                data.append(float('NaN'))

        if 'battery_voltage' in message_tags:
            data.append(struct.unpack(AW_Message.tag_data['battery_voltage']['format'], 
                                      str(message_tags['battery_voltage'][0]))[0] 
                        / 1000.0)
        else:
            data.append(float('NaN'))
        
        awnet_text_file.write(str(timestamp[0]))
        # strip zero before decimal point 
        awnet_text_file.write(str(timestamp[1]/32768.0).lstrip('0'))
        awnet_text_file.write('\t')
        awnet_text_file.write('\t'.join(map(str, data)))
        awnet_text_file.write('\n')

# AuroraWatch realtime file
cloud_file = None
def write_cloud_data(timestamp, data):
    global cloud_file
    global config
    unix_time = timestamp[0] + timestamp[1]/32768.0
    tmp_name = time.strftime(config.get('cloud', 'filename'),
                            time.gmtime(unix_time))
    if cloud_file is not None and tmp_name != cloud_file.name:
        # Filename has changed
        cloud_file.close()
        cloud_file = None
            
    if cloud_file is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            try:
                os.makedirs(p)
            except Exception as e:
                print('Could not make directory ' + p + str(e))
                return
        
        try:
            cloud_file = open(tmp_name, 'a+', 1)
        except Exception as e:
            print('Exception was ' + str(e))
            cloud_file = None
        
    if cloud_file is not None:
        tag_names = ['cloud_ambient_temperature', 
                     'cloud_object1_temperature']
        if config.getboolean('cloud', 'dual_sensor'):
            tags.append('cloud_object2_temperature')
        tag_names.extend(['ambient_temperature', 'relative_humidity'])

        # Write the time
        cloud_file.write(str(timestamp[0]))
        # strip zero before decimal point 
        cloud_file.write(str(timestamp[1]/32768.0).lstrip('0'))

        for tag_name in tag_names:
            if tag_name in data:
                cloud_file.write(' {:.2f}'.format(data[tag_name]))
            else:
                cloud_file.write(' nan')
        cloud_file.write('\n')
    
    
def open_control_socket():
    if config.has_option('controlsocket', 'filename'):
        if os.path.exists(config.get('controlsocket', 'filename')):
            os.remove(config.get('controlsocket', 'filename'))
        control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(config.get('controlsocket', 'filename'))
        # control_socket.setblocking(False)
        control_socket.listen(1)
    else:
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # ord('A') = 65, ord('W') = 87 
        control_socket.bind(('localhost', 
                             int(config.get('controlsocket', 'port'))))
        control_socket.setblocking(False)
        control_socket.listen(0)
    return control_socket


# Process any CR or LF terminated messages which are in the buffer    
def handle_control_message(buf, pending_tags):
    r = []
    while len(buf):
        cmds = buf.splitlines()
        if cmds[0] == buf:
            # no newlines
            # return None
            break;
        
        cmd = cmds[0]
        # Assign back to the input reference
        buf[:] = '\n'.join(cmds[1:])
        
        if cmd == '' or cmd.startswith('#'):
            continue
        
        if cmd.startswith('sampling_interval='):
            val = float(cmd.replace('sampling_interval=', '', 1)) * 16
            # pending_tags['sampling_interval'] = struct.pack('!L', val)
            pending_tags['sampling_interval'] = \
                struct.pack(AW_Message.tag_data['sampling_interval']['format'],
                            val)
            r.append('sampling_interval:' + str(val / 16))
        
        elif cmd.startswith('upgrade_firmware='):
            version = str(cmd.replace('upgrade_firmware=', '', 1))
            try:
                handle_cmd_upgrade_firmware(version)
                r.append('upgrade_firmware:' + version)
            except Exception as e:
                r.append('ERROR: ' + str(e))
                    
        elif cmd == 'reboot=TRUE':
            pending_tags['reboot'] = [];
            r.append('reboot:TRUE')
        
        elif cmd.startswith('read_eeprom='):
            if 'eeprom_contents' in pending_tags:
                # The EEPROM write and EEPROM read both result in the same 
                # tag being returned; allow only one at once.
                r.append('ERROR: EEPROM write pending, cannot read')
            else:
                edata = str(cmd.replace('read_eeprom=', '', 1)).split(',')
                address = int(edata[0], 0)
                sz = int(edata[1], 0)
                if sz < 1:
                    r.append('ERROR: bad value for size')
                else:
                    pending_tags['read_eeprom'] = struct\
                        .pack(AW_Message.tag_data['read_eeprom']['format'],
                              address, sz)
                    r.append('read_eeprom:' + str(address) + ',' + str(sz))
        
        elif cmd.startswith('write_eeprom='):
            if 'read_eeprom' in pending_tags:
                # The EEPROM write and EEPROM read both result in the same 
                # tag being returned; allow only one at once.
                r.append('ERROR: EEPROM read pending, cannot write')
            else:
                edata = [ int(x, 0) for x in 
                         str(cmd.replace('write_eeprom=', '', 1)).split(',') ]
                if len(edata) > 1:
                    pending_tags['eeprom_contents'] = \
                        struct.pack('!H' + str(len(edata)-1) + 'B',
                                    *edata)
                                    #edata[0], len(edata)-1, *edata[1:])
                    r.append('write_eeprom:' + ','.join(map(str, edata)))                  
                else:
                    r.append('ERROR: no data to send')
        
        elif cmd.startswith('num_samples='):
            num_ctrl = map(int, 
                          str(cmd.replace('num_samples=', '', 1)).split(','))
            pending_tags['num_samples'] = \
                struct.pack(AW_Message.tag_data['num_samples']['format'], 
                            num_ctrl[0], num_ctrl[1])
            r.append('num_samples:' + str(num_ctrl[0]) + ',' + str(num_ctrl[1]))
        
        elif cmd.startswith('all_samples='):
            flag = (int(cmd.replace('all_samples=', '', 1)) != 0)
            pending_tags['all_samples'] = \
                struct.pack(AW_Message.tag_data['all_samples']['format'],
                            flag)
            r.append('all_samples:' + str(flag))
        elif cmd == 'pending_tags':
            r.append('pending_tags:' + describe_pending_tags())
        else:
            r.append('ERROR: do not understand '' + str(cmd) + ''')
    print('\n'.join(r))
    return r


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
    firmware = firmware_file.read();
    firmware_file.close()
    
    if len(firmware) % AW_Message.firmware_block_size != 0:
        raise Exception('firmware file ' + filename + ' not a multiple  of '
                        + str(AW_Message.firmware_block_size) + ' bytes')

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
    stated_crc = int(struct.unpack('>H', binascii.unhexlify(stated_crc_hex))[0])
    
    # The CRC check must be computed over the entire temporary 
    # application section; extend as necessary
    temp_app_size = (131072 - 4096) / 2;
    if len(firmware) < temp_app_size:
        padding = chr(0xFF) * (temp_app_size - len(firmware))
        padded_firmware = firmware + padding
    elif len(firmware) > temp_app_size:
        raise Exception('Firmware image too large (' + str(len(firmware)) + ' bytes)')
    else:
        padded_firmware = firmware
    
    actual_crc = AW_Message.crc16(padded_firmware)
    if actual_crc != stated_crc:
        raise Exception('Firmware CRC does not match with ' + crc_filename + ' ' + str(actual_crc) + ' ' + str(stated_crc))
    if version != stated_version:
        raise Exception('Version does not match with ' + crc_filename)
    return stated_crc, len(firmware) / AW_Message.firmware_block_size

def handle_cmd_upgrade_firmware(version):
    if len(version) > AW_Message.firmware_version_max_length:
        raise Exception('Bad version')
    
    version_str = str(version)
    # crc, num_pages = get_firmware_details(version.decode('ascii'))
    crc, num_pages = get_firmware_details(version_str)
    padded_version = version + ('\0' * (AW_Message.firmware_version_max_length
                                      - len(version)))
    args = list(padded_version)
    args.append(num_pages)
    args.append(crc)
    pending_tags['upgrade_firmware'] = \
        struct.pack(AW_Message.tag_data['upgrade_firmware']['format'], *args)
    
    
# Deal with any item requested in the incoming packet
def handle_packet_requests(message_tags):
    try:
        if 'get_firmware_page' in message_tags:
            # Write the page to requested tags
            packet_req_get_firmware_page(message_tags['get_firmware_page'][0])
#    except Exception as e:
#       None 
    finally:
        None
    
def packet_req_get_firmware_page(data):
    global requested_tags
    unpacked_data = \
        struct.unpack(AW_Message.tag_data['get_firmware_page']['format'],
                      buffer(data)) 
    version = ''.join(unpacked_data[0:AW_Message.firmware_version_max_length])
    version_str = version.split('\0', 1)[0]
                                                         
    page_number, = unpacked_data[AW_Message.firmware_version_max_length:]
    image_filename = AW_Message.get_image_filename(version_str)
    image_file = open(image_filename)
    
    # Ensure file is closed in the case of any error
    try:   
        image_file.seek(AW_Message.firmware_block_size * page_number)
        fw_page = image_file.read(AW_Message.firmware_block_size)
    except:
        print('SOME ERROR')
        # Some error, so don't try adding to requested_tags
        return
    finally:
        # Ensure file is closed in all circumstances
        image_file.close()

    args = list(version)
    args.append(page_number)
    args.extend(list(fw_page))
    requested_tags['firmware_page'] = \
        struct.pack(AW_Message.tag_data['firmware_page']['format'], *args) 


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
    '''Read size bytes from the file. If a timeout is set it may
    return less characters as requested. With no timeout it will block
    until the requested number of bytes is read.'''
    r = ''
    while True:
        start = time.time()
        ready,_,_ = select.select([file_obj],[],[], timeout)
        if ready:
            buf = file_obj.read(1)
            if buf == '\r' or buf == '\n':
                break # done
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
             address_name = AWEeprom.lookup_address(address)
             if address_name is None:
                 #address_name = 'EEPROM ' + hex(address) + ': '
                 #fmt = 'B' * (len(pending_tags[k]) - 2)
                 # address_name = 'EEPROM (unknown address ' + hex(address) + ')'
                 name = k + '(unknown address, ' + hex(address) + ')'
             else:
                 name = k + '(' + address_name + ')'
             r.append(name)
        else:
             r.append(k)
    return ','.join(r)

# ==========================================================================

# Parse command line arguments
parser = \
    argparse.ArgumentParser(description='AuroraWatch data recording daemon')

parser.add_argument('-c', '--config-file', 
                    default='/etc/awnet.ini',
                    help='Configuration file')
parser.add_argument('--acknowledge', action='store_true',
                    default=True,
                    help='Transmit acknowledgement');
parser.add_argument('--no-acknowledge', action='store_false',
                    dest='acknowledge',
                    help="Don't transmit acknowledgement")
parser.add_argument('--read-only', action='store_true',
                    help='Open device file read-only (implies --no-acknowledge)')
parser.add_argument('--device', metavar='FILE', help='Device file')
parser.add_argument('-v', '--verbose', dest='verbosity', action='count', 
                     default=0, help='Increase verbosity')

args = parser.parse_args()
if args.read_only:
    args.acknowledge = False

read_config_file(args.config_file)
if site_ids:
    print('Site IDs: ' + ', '.join(site_ids))
else:
    print('Site IDs: none')
    
print('Done')
comms_block_size = int(config.get('serial', 'blocksize'))

if args.device:
    device_filename = args.device
else:
    device_filename = config.get('serial', 'port')

if device_filename == '-':
    device = os.sys.stdin
    device_socket = None
    args.acknowledge = False # Cannot send acknowledgements

elif config.get('daemon', 'connection') == 'ethernet':
    # Connect via ethnernet
    device = None
    local_port = int(config.get('ethernet', 'local_port'))
    local_ip = config.get('ethernet', 'local_ip')
    device_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
    # device_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#    device_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    device_socket.bind((local_ip, local_port))
    device_socket.setblocking(False)
    # device_socket.listen(3)
    control_socket = open_control_socket()

else:
    if args.read_only:
        device = open(device_filename, 'rb', 0)
    else:
        device = open(device_filename, 'a+b', 0)
    device_socket = None

if device_filename == '-':
    control_socket = None
    
elif device:
    if device.isatty():
        if args.verbosity:
            print('Reading from ' + device_filename)
        tty.setraw(device, termios.TCIOFLUSH)
        term_attr = termios.tcgetattr(device)
        term_attr[4] = term_attr[5] = get_termios_baud_rate(config.get('serial', 
                                                              'baudrate'))
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
        args.acknowledge = False

        
control_socket_conn = None
control_buffer = None

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

hmac_key = config.get('magnetometer', 'key').decode('hex')
if len(hmac_key) != 16:
    print('key must be 32 characters long')
    exit(1)

buf = bytearray()



running = True
while running:
    try:
        if control_socket_conn is None:
            inputready,outputready,exceptready = select.select(select_list,[],[])
        else:
            select_list2 = select_list[:]
            select_list2.append(control_socket_conn)
            inputready,outputready,exceptready = select.select(select_list2,[],[])
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
                print(repr(remote_addr))
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
    
            message = AW_Message.validate_packet(buf, hmac_key)
            if message is not None:
                if (device and device.isatty()) or device_socket:
                    message_time = time.time()
                else:
                    message_time = None
                if args.verbosity:
                    # print('=============')
                    # if device.isatty():
                    #     print('Valid message received ' + str(time.time()))
                    AW_Message.print_packet(message, message_time=message_time)
                
                timestamp = AW_Message.get_timestamp(message)
                message_tags = AW_Message.parse_packet(message)
                AW_Message.tidy_pending_tags(pending_tags, message_tags)
                
                # if fd.isatty() and args.acknowledge:
                if args.acknowledge:
                    # Not a file, so send a acknowledgement                     
                    response = bytearray(1024)
                    AW_Message.put_header(response,
                                          site_id=AW_Message.get_site_id(message),
                                          timestamp=timestamp,
                                          flags=(1 << AW_Message.flags_response_bit))
                    AW_Message.put_current_epoch_time(response)
                    
                    # Handle packet requests. These tags live only for the 
                    # duration between receiving the request and sending the
                    # response.
                    requested_tags = {}
                    handle_packet_requests(message_tags)
                    for tag_name in requested_tags:
                        AW_Message.put_data(response, 
                                            AW_Message.tag_data[tag_name]['id'], 
                                            requested_tags[tag_name])
                    

                    for tag_name in pending_tags:
                        AW_Message.put_data(response, 
                                            AW_Message.tag_data[tag_name]['id'],
                                            pending_tags[tag_name])
                        # del pending_tags[tag]
                        
                    # Add padding to round up to a multiple of block size
                    padding_length = (comms_block_size - 
                                     ((AW_Message.get_packet_length(response) +
                                       AW_Message.signature_block_length) %
                                      comms_block_size))
                    AW_Message.put_padding(response, padding_length)
                    AW_Message.put_signature(response, hmac_key, 
                                             AW_Message.get_retries(message), 
                                             AW_Message.get_sequence_id(message))
                    
                    # Trim spare bytes from end of buffer
                    del response[AW_Message.get_packet_length(response):]
                    if fd == device:
                        device.write(response)
                    else:
                        count = device_socket.sendto(response, remote_addr)

                    if args.verbosity:   
                        # print('Response: ------')
                        AW_Message.print_packet(response, message_time=message_time)
                    
                if config.has_option('awpacket', 'filename'):
                    # Save the message and response
                    write_message_to_file(timestamp, message, 
                                        config.get('awpacket', 'filename'))
                    if response is not None:
                        write_message_to_file(timestamp, response, 
                                            config.get('awpacket', 'filename'))

                if (config.has_option('aurorawatchrealtime', 'filename') and
                    not AW_Message.is_response_message(message)):
                    data = { }
                    for tag_name in ['mag_data_x', 'mag_data_y', 'mag_data_z']:
                        if tag_name in message_tags:
                            comp = \
                                struct.unpack(AW_Message.tag_data[tag_name]['format'], 
                                              str(message_tags[tag_name][0]))
                            data[tag_name] = comp[1];
                    write_aurorawatch_realtime_data(timestamp, data)
                
                if (config.has_option('cloud', 'filename') and
                    not AW_Message.is_response_message(message)):
                    data = {}
                    for tag_name in ['cloud_ambient_temperature', 
                                     'cloud_object1_temperature',
                                     'cloud_object2_temperature', 
                                     'ambient_temperature',
                                     'relative_humidity']:
                        if tag_name in message_tags:
                            data[tag_name] = AW_Message.decode_cloud_temp( \
                                tag_name, str(message_tags[tag_name][0]))
                    write_cloud_data(timestamp, data)
                    
                if (not AW_Message.is_response_message(message)):
                    write_aurorawatchnet_text_data(timestamp, message_tags)
                        
            else:
                response = None


                        
        elif fd == control_socket:
            if control_socket_conn is not None:
                try:
                    control_socket_conn.shutdown(socket.SHUT_RDWR)
                except:
                    None
            control_socket_conn = None
            try:
                (control_socket_conn, client_address) = control_socket.accept()
                control_socket_conn.settimeout(10)
                control_buffer = bytearray()
            except Exception as e:
                print('ERROR: ' + str(e))
                control_socket_conn = None


        elif fd == control_socket_conn:
            try:
                s = control_socket_conn.recv(1024)
                if s:
                    control_buffer += s
                    mesg = handle_control_message(control_buffer, pending_tags)
                    fd.send('\n'.join(mesg) + '\n')
                else:
                    # EOF on control socket connection
                    control_socket_conn.shutdown(socket.SHUT_RDWR)
                    control_socket_conn.close()
                    control_socket_conn = None
            except Exception as e:
                print('ERROR: ' + str(e))
                control_socket_conn = None
        else:
            print('Other: ' + str(fd))
