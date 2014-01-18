# -*- coding: iso-8859-15 -*-

# import datetime
from datetime import datetime
import hashlib
import hmac
import os
import struct
import time



__all__ = ['validate_packet']

default_magic = 'AW'
default_version = 1

header_length = 14
signature_block_length = 10
magic_offset = 0
magic_size = len(default_magic)
version_offset = 2
version_size = 1
flags_offset = 3
flags_size = 1
packet_length_offset = 4
packet_length_size = 2
site_id_offset = 6
site_id_size = 2
timestamp_offset = 8
timestamp_seconds_offset = timestamp_offset
timestamp_seconds_size = 4
timestamp_fraction_offset = timestamp_seconds_offset + timestamp_seconds_size
timestamp_fraction_size = 2
timestamp_size = timestamp_seconds_size + timestamp_fraction_size
num_axes = 3

# Signature offsets are relative to the start of the signature block,
# which starts at packet_length - signature_block_length
sequence_id_offset = 0
sequence_id_size = 1
retries_offset = 1
retries_size = 1
hmac_offset = 2
hmac_length = 8


flags_signed_message_bit = 0
flags_sample_timing_error_bit = 1
flags_response_bit = 2

size_of_tag = 1
size_of_packet_length = 2
size_of_firmware_page_number = 2
size_of_crc = 2

firmware_version_max_length = 16

# Define the block size used for firmware updates.
firmware_block_size = 128


def format_tag_array_of_longs(tag_name, data_len, payload):
    return repr(list(struct.unpack('!' + str(data_len/4) + 'l', str(payload))))
    
def format_padding(tag_name, data_len, payload):
    return str([0] * data_len)

def format_tag_blank(tag_name, data_len, payload):
    return ''

def format_null_terminated_string(tag_name, data_len, payload):
    return "'" + str(payload.split('\0')[0]) + "'"

def format_unix_epoch_32678(tag_name, data_len, payload):
    '''
    Format a timestamp based on seconds since Unix epoch plus
    32768th second.
    '''
    t = struct.unpack('!ih', str(payload))
    dt = datetime.utcfromtimestamp(t[0] + (t[1]/32768.0))
    return str(t[0]) + ',' + str(t[1]) + ' (' + dt.isoformat() + ')'

# Description of the radio communication protocol tags. The different
# types of data are identified by a tag, sent numerically in the
# protocol but elsewhere referred to by name. In tag_data the keys are
# the tag names. 
#
# Lengths are given including the tag itself (one byte). Some tags
# have variable length are are entered as zero bytes for length; they
# are sent as tag, payload length (16-bit unsigned int), payload.
#
# Format (if specified) is the format specifier for
# struct.pack/struct.unpack.
#
# Formatter (if specified) is a function to convert the data to a
# string representation for display.
#
# All numbers are sent in network byte order (MSB first, LSB last).

tag_data = {
    # Magnetometer data, raw sample units.
    'mag_data_x': {
        'id': 0,
        'length': 6,
        'format': '!Bl',
        },
    'mag_data_y': {
        'id': 1,
        'length': 6,
        'format': '!Bl',
        },
    'mag_data_z': {
        'id': 2,
        'length': 6,
        'format': '!Bl',
        },
    # Temperatures, hundredths of Celsius (signed).
    'magnetometer_temperature': {
        'id': 3,
        'length': 3,
        'format': '!h',
        },
    'system_temperature': {
        'id': 4,
        'length': 3,
        'format': '!h',
        },
    # Voltage, millivolts.
    'battery_voltage': {
        'id': 5,
        'length': 3,
        'format': '!H',
        },
    'time_adjustment': {
        'id': 6,
        'length': 7,
        'format': '!ih',
        },
    'reboot_flags': {
        'id': 7,
        'length': 2,
        # 'format': '!B',
        },
    'sampling_interval': {
        'id': 8,
        'length': 3,
        'format': '!H',
        },
    'padding_byte': {
        'id': 9,
        'length': 1,
        'formatter': format_padding,
        },
    'padding': {
        'id': 10,
        'length': 0,
        'formatter': format_padding,
        },
    'current_epoch_time': {
        'id': 11,
        'length': 7,
        #'format': '!LH',
        'format': '!ih',
        'formatter' : format_unix_epoch_32678,
        },
    'reboot': {
        'id': 12,
        'length': 1,
        # 'format': '',
        },
    'current_firmware': {
        'id': 13,
        'length': (size_of_tag + firmware_version_max_length),
        'format': ('!' + str(firmware_version_max_length) + 'c'),
        'formatter': format_null_terminated_string,
        },
    'upgrade_firmware': {
        'id': 14,
        'length': (size_of_tag + firmware_version_max_length +
                   size_of_firmware_page_number + size_of_crc),
        'format': ('!' + str(firmware_version_max_length) + 'cHH'),
        },
    'get_firmware_page': {
        'id': 15,
        'length': (size_of_tag + firmware_version_max_length + 
                   size_of_firmware_page_number),
        'format': ('!' + str(firmware_version_max_length) + 'cH'),
        },
    'firmware_page': {
        'id': 16,
        'length': (size_of_tag + firmware_version_max_length + 
                   size_of_firmware_page_number + firmware_block_size),
        'format': ('!' + str(firmware_version_max_length) + 'cH' + 
                   str(firmware_block_size) + 'c'),
        'formatter': 'format_tag_blank',
        },
    'read_eeprom': {
        'id': 17,
        'length': 5,
        'format': '!HH',
        },
    'eeprom_contents': {
        'id': 18,
        'length': 0,
        # 'format': None,
        },
    'num_samples': {
        'id': 19,
        'length': 3,
        'format': '!BB',
        },
    'all_samples': {
        'id': 20,
        'length': 2,
        # 'format': '!?',
        },
    'mag_data_all_x': {
        'id': 21,
        'length': 0,
        'formatter': format_tag_array_of_longs,
        },
    'mag_data_all_y': {
        'id': 22,
        'length': 0,
        'formatter': format_tag_array_of_longs,
        },
    'mag_data_all_z': {
        'id': 23,
        'length': 0,
        'formatter': format_tag_array_of_longs,
        },
    # Temperatures, hundredths of Celsius (signed).
    'cloud_ambient_temperature': {
        'id': 24,
        'length': 3,
        'format': '!h',
        },
    'cloud_object1_temperature': {
        'id': 25,
        'length': 3,
        'format': '!h',
        },
    'cloud_object2_temperature': {
        'id': 26,
        'length': 3,
        'format': '!h',
        },
    'ambient_temperature': {
        'id': 27,
        'length': 3,
        'format': '!h',
        },
    # Relative humidity, hundredths of percent.
    'relative_humidity': {
        'id': 28,
        'length': 3,
        'format': '!H',
        },
    }

tag_id_to_name = {}
for tag_name in tag_data.keys():
    tag_id = tag_data[tag_name]['id']
    if tag_id_to_name.has_key(tag_id):
        raise Exception('Duplicate tag ID')
    tag_id_to_name[tag_id] = tag_name


# Horrid hack because cloud data was originally sent as absolute
# temperatures, unlike other tags.
def decode_cloud_temp(tag_name, payload):
    tmp = (float(struct.unpack(tag_data[tag_name]['format'],
                               str(payload))[0]) / 100)
    if tmp > 173.15:
        tmp -= 273.15
    return tmp

def format_tag_cloud_temp(tag_name, dataLen, payload):
    return str(decode_cloud_temp(tag_name, payload)) + '°C'
    
    
def get_header_field(buf, offset, size):
    if len(buf) < offset + size:
        return None
    r = 0
    for i in range(size):
        r *= 256
        r += buf[offset + i]
    return r

def get_magic(buf):
    if len(buf) > magic_offset + magic_size:
        return bytearray(buf[magic_offset:magic_offset+magic_size])
    else:
        return None
    
def get_version(buf):
    return get_header_field(buf, version_offset, version_size)

def get_flags(buf):
    return get_header_field(buf, flags_offset, flags_size)

def get_packet_length(buf):
    return get_header_field(buf, packet_length_offset, packet_length_size)

def get_site_id(buf):
    return get_header_field(buf, site_id_offset, site_id_size)

def get_timestamp(buf):
    seconds = get_header_field(buf, timestamp_seconds_offset, 
                             timestamp_seconds_size)
    fraction = get_header_field(buf, timestamp_fraction_offset, 
                              timestamp_fraction_size)
    return [seconds, fraction]

def is_signed_message(buf):
    global flags_signed_message_bit
    if len(buf) <= flags_offset:
        return None
    return buf[flags_offset] & (1 << flags_signed_message_bit)
    
def is_response_message(buf):
    global flags_response_bit
    if len(buf) <= flags_offset:
        return None
    return buf[flags_offset] & (1 << flags_response_bit)

def get_sequence_id(buf):
    if not is_signed_message(buf):
        return None
    else:
        return buf[get_packet_length(buf) - signature_block_length + sequence_id_offset]

def get_retries(buf):
    if not is_signed_message(buf):
        return None
    else:
        return buf[get_packet_length(buf) - signature_block_length + retries_offset]
    
def set_header_field(buf, val, offset, size):
    tmp = val
    for i in range(size-1, -1, -1):
        buf[offset + i] = (tmp & 0xff)
        tmp >>= 8

def set_magic(buf, magic=default_magic):
    for i in range(magic_size):
        buf[i] = magic[i]

def setVersion(buf, version=default_version):
    set_header_field(buf, version, version_offset, version_size)

def set_packet_length(buf, packet_length):
    set_header_field(buf, packet_length, packet_length_offset, packet_length_size)

def set_flags(buf, flags):
    set_header_field(buf, flags, flags_offset, flags_size)
    
def set_site_id(buf, site_id):
    set_header_field(buf, site_id, site_id_offset, site_id_size)
        
def set_timestamp(buf, seconds, fraction):
    set_header_field(buf, seconds, timestamp_seconds_offset, 
                   timestamp_seconds_size)
    set_header_field(buf, fraction, timestamp_fraction_offset, 
                   timestamp_fraction_size)

def put_header(buf, site_id, timestamp, magic=default_magic, version=default_version, flags=0):
    buf[header_length-1] = 0 # Set size
    set_magic(buf, magic)
    setVersion(buf, version)
    set_flags(buf, flags)
    set_packet_length(buf, header_length)
    set_site_id(buf, site_id)
    set_timestamp(buf, *timestamp)

def put_data(buf, tag_id, data):
    packet_length = get_packet_length(buf) 
    i = packet_length
    buf[i] = tag_id
    i += 1
    tag_name = tag_id_to_name[tag_id]
    tag_len = tag_data[tag_name]['length']
    if tag_len == 0:
        data_len = len(data)
        buf[i+1] = data_len & 0xff
        buf[i] = (data_len >> 8) & 0xff
        i += 2
        packet_length += 3 + data_len
    else:
        data_len = tag_len - 1
        packet_length += tag_len
        
    # TODO: optimise? Use buffer?
    for n in range(data_len):
        buf[i + n] = data[n]
    set_packet_length(buf, packet_length)
    
def put_current_epoch_time(buf):
    packet_length = get_packet_length(buf)
    tag_len = tag_data['current_epoch_time']['length']
    i = packet_length 
    now = time.time()
    seconds = long(now);
    frac = int(round((now % 1) * 32768.0))

    buf[i] = tag_data['current_epoch_time']['id']
    i += 1
    for n in range(tag_len-2, -1, -1):
        # buf[i + n] = timestamp & 0xff
        # timestamp >>= 8
        buf[i + n] = 0
    data = bytearray(struct.pack(tag_data['current_epoch_time']['format'], 
                                 seconds, frac))
    buf[packet_length + 1 : packet_length + tag_len] = data
    
    set_packet_length(buf, packet_length + tag_len)

def put_padding(buf, padding_length):
    if padding_length == 0:
        return

    if padding_length == 1:
        put_data(buf, tag_data['paddingByte']['id'], [])
    elif padding_length == 2:
        put_data(buf, tag_data['paddingByte']['id'], [])
        put_data(buf, tag_data['paddingByte']['id'], [])
    else:
        put_data(buf, tag_data['padding']['id'], bytearray(padding_length - 3))

def put_signature(buf, hmac_key, retries, sequence_id):
    if is_signed_message(buf):
        signedLen = get_packet_length(buf)
    else:
        signedLen = get_packet_length(buf) + signature_block_length
        set_packet_length(buf, signedLen)

    buf[flags_offset] |= (1 << flags_signed_message_bit)
    
  
    i = signedLen - signature_block_length
    buf[i] = sequence_id;
    i += 1
    buf[i] = retries
    i += 1
    # Now add HMAC-MD5
    hmac_md5 = hmac.new(hmac_key)# , digestmod=hashlib.md5)
    hmac_md5.update(buf[0:(signedLen - hmac_length)])
    
    # Take least significant bytes
    hmac_bytes = hmac_md5.digest()
    buf[(signedLen - hmac_length):signedLen] = \
        hmac_bytes[(len(hmac_bytes)-hmac_length):]

def make_header(site_id, timestamp, magic=default_magic, 
               version=default_version, flags=0):
    buf = bytearray()
    put_header(buf, site_id, timestamp, magic, version, flags)
    return buf

def parse_packet(buf):
    r = { };
    i = header_length;
    end_of_data = get_packet_length(buf)
    if is_signed_message(buf):
        end_of_data -= signature_block_length
    while i < end_of_data:
        tag_id = buf[i]
        i += 1
        if not tag_id_to_name.has_key(tag_id):
            raise Exception('Unknown tag: ' + str(tag_id))
        tag_name = tag_id_to_name[tag_id]
        tag = tag_data[tag_name]
        tag_len = tag['length']
        if tag_len == 0:
            data_len = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            data_len = tag_len - 1
        data = buf[i:(i+data_len)]
        
              
        if tag_name not in r:
            r[tag_name] = []
        r[tag_name].append(data)
        i += data_len
        
    return r

def tidy_pending_tags(pending_tags, message_tags):
    del_list = []
    for tag_name in pending_tags:  
        if tag_name == 'reboot' and 'reboot_flags' in message_tags:
            del_list.append(tag_name)
            
        elif tag_name == 'upgrade_firmware' and 'current_firmware' in message_tags:
            current_firmware = str(message_tags['current_firmware'][0]).split('\0', 1)[0]
            upgrade_firmware = '' + str(pending_tags[tag_name]).split('\0', 1)[0]
            if current_firmware == upgrade_firmware:
                # Current firmware version matches so cancel
                print('Firmware already at version ' + upgrade_firmware)
                del_list.append(tag_name)
        
        elif tag_name == 'all_samples' and bool(ord(pending_tags[tag][0])) == \
            any(t in message_tags for t in ['mag_data_all_x', 'mag_data_all_y',
                                            'mag_data_all_z']):
            # pending_tags[all_samples][0] must match whether
            # mag_data_all_{x,y,z} exists in message_tags
            del_list.append(tag_name)
            
        elif tag_name in ['read_eeprom', 'eeprom_contents'] and \
                'eeprom_contents' in message_tags:
            # TODO: check correct data has been received. NB: if key was sent 
            # it won't be confirmed!
            del_list.append(tag_name)
            
            
        elif tag_name in message_tags and \
                pending_tags[tag_name] in message_tags[tag_name]:
            # This tag appears in message_tags, and one of the values matches
            # pending_tags[tag_name]
            del_list.append(tag_name)

    for d in del_list:
        del pending_tags[d]
    
# Print in hex, 00 - FF
def byte_hex(a):
    return hex(a)[2:].zfill(2)
    
def print_buffer(buf, length=None):
    if length is None:
        length = len(buf)
    print(' '.join(map(hex, buf[:length])))
    
def header_to_str_array(buf):
    t = get_timestamp(buf)
    dt = datetime.utcfromtimestamp(t[0] + (t[1]/32768.0))
    return ['Magic: ' + ''.join(map(chr, get_magic(buf))),
            'Version: ' + str(get_version(buf)),
            'Flags: ' + hex(get_flags(buf)),
            'Packet length: ' + str(get_packet_length(buf)),
            'Site ID: ' + str(get_site_id(buf)),
            ('Timestamp: ' + str(t[0]) + ',' + str(t[1]) 
             + ' (' + dt.isoformat() + ')')]

  
def print_header(buf):
    print('\n'.header_to_str_array(buf))

def print_tags(buf):
    i = header_length
    end_of_data = get_packet_length(buf)
    if is_signed_message(buf):
        end_of_data -= signature_block_length
    while i < end_of_data:
        tag_id = buf[i]
        i += 1
        if not tag_id_to_name.has_key(tag_id):
            # Cannot continue since the length is not known
            print('Unknown tag: ' + str(tag_id))
            return
        tag_name = tag_id_to_name[tag_id]
        tag = tag_data[tag_name]
        # tag_len = tag_data[tag_name]['length']
        tag_len = tag['length']
        if tag_len == 0:
            data_len = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            data_len = tag_len - 1    
          
        if tag.has_key('formatter'):
            data_repr = tag['formatter'](tag_name, data_len, 
                                         buf[i:(i+data_len)])
        elif tag.has_key('format'):
            data_repr = repr(list(struct.unpack(tag['format'],
                                                str(buf[i:(i+data_len)]))))
        else:
            data_repr = '0x  ' + ' '.join(map(byte_hex, buf[i:(i+data_len)]))
            
        print(tag_name + ' (#' + str(tag_id) + '):  ' + data_repr)
        i += data_len
        

def decode_tag_payload(tag_name, tag_payload):
    if tag_data[tag_name]['length'] == 0:
        data_len = (tag_payload[0] << 8) + tag_payload[1]
        i = 2
    else:
        data_len = tag_data[tag_name]['length'] - 1
        i = 0

    if tag_data[tag_name].has_key('formatter'):
        data_repr = tag_data[tag_name]['formatter'](tag_name, data_len, 
                                                    tag_payload[i:(i+data_len)])
    elif tag_data[tag_name].has_key('format'):
        data_repr = repr(list(struct.unpack(tag_data[tag_name]['format'],
                                            str(tag_payload[i:(i+data_len)]))))
    else:
        data_repr = '0x  ' + ' '.join(map(byte_hex, tag_payload[i:(i+data_len)]))
    
    return tag_name + (' (#%d): ' % tag_data[tag_name]['id']) + data_repr, \
        data_repr, data_len


def print_signature(buf):
    if is_signed_message(buf):
        print('Sequence ID: ' + str(get_sequence_id(buf)))
        print('Retries: ' + str(get_retries(buf)))
        packet_length = get_packet_length(buf)
        print('HMAC-MD5: 0x  ' + ' '.join(map(byte_hex, buf[packet_length-hmac_length:packet_length])))
    else:
        print('Signature: none')
        
def print_packet(buf, message_time=None):
    
    try:
        if is_response_message(buf):
            separator = '------------- Response'
        else:
            separator = '============= Message'
    except:
        separator = '============= Invalid Message' 

    if message_time is not None:
        separator += ' received ' + str(time.time())

    s = [separator]
    try:
        # print_header(buf)
        s.extend(header_to_str_array(buf))
    except Exception as e:
        s.append('Error in header: ' + str(e))

    print('\n'.join(s))

    try:
        print_tags(buf)
    except Exception as e:
        print('Error in tags: ' + str(e))
    try:
        print_signature(buf)
    except Exception as e:
        print('Error in header: ' + str(e))
    
def validate_packet(buf, hmac_key, ignore_digest=False):
    global default_magic
    complete_message = False

    valid = True    
    while (len(buf)):
        valid = True
        
        # Check magic
        for i in range(min(len(default_magic), len(buf))):
            if buf[i] != ord(default_magic[i]):
                valid = False
                break
        
        if len(buf) < len(default_magic):
            break
        
        # Check message is signed
        if is_signed_message(buf) == None:
            break;

        if is_signed_message(buf) == False:
            # All transmitted messages must be signed
            valid = False
        
        if valid:
            packet_length = get_packet_length(buf)
            if packet_length is None:
                # Insufficient characters
                break
            elif packet_length < header_length:
                valid = False
            
        if valid and len(buf) >= packet_length:
            complete_message = True

            if not ignore_digest:
                # Compute HMAC-MD5
                hmac_md5 = hmac.new(hmac_key)# , digestmod=hashlib.md5)
                hmac_md5.update(buf[0:(packet_length - hmac_length)])


                # Take least significant bytes
                hmac_bytes = hmac_md5.digest()
                hmac_bytes = hmac_bytes[(len(hmac_bytes)-hmac_length):]

                # Compare. To prevent timing attacks don't stop the 
                # comparison early and aim to have all outcomes take the
                # same time.
                received_hmac_bytes = buf[(packet_length - hmac_length):]

                for i in range(hmac_length):
                    valid = (ord(hmac_bytes[i]) == received_hmac_bytes[i]) and valid
                if not valid:
                    print('#########################')
                    print('Packet failed HMAC-MD5, computed as ' +
                          ' '.join(map(byte_hex, map(ord, hmac_bytes))))

                    # Be paranoid when printing invalid packets!
                    try:
                        print_packet(buf)
                    except:
                        None
                    print('#########################')
            
        # All tests done
        if valid:
            if complete_message:
                r = bytearray(buf[0:packet_length])
                del buf[0:packet_length]
                return r
            else:
                return None
        else:
            # Remove the first character and try the next
            del buf[0]
            return None
    
    return None  

def crc16(data, crc=0):
    for a in data:
        crc ^= ord(a)
        for i in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = (crc >> 1)
    return crc & 0xffff

def get_image_filename(version, crc_file=False):
    # TODO: use config file
    filename = os.path.join('/var/aurorawatchnet/firmware', version);
    if crc_file:
        filename += '.crc'
    else:
        filename += '.bin'
    return filename
    
def adc_counts_to_tesla(val, tesla_per_volt=50e-6):
    # Data is normalised too allow for maximum resolution of 18 bits and
    # 8x gain. Thus largest possible normalised magnitude is 2^17 * 8.
    # Largest magnitude of ADC output is from +/- 2.048V   

    scale_factor = 2.048 * tesla_per_volt / (pow(2,17) * 8)
    return val * scale_factor
