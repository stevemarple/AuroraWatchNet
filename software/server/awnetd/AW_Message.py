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

tag_data = {
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
    'battery_voltage': {
        'id': 5,
        'length': 3,
        'format': '!H',
        },
    'time_adjustment': {
        'id': 6,
        'length': 7,
        # 'format': 'LH',
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
        'format': '!LH',
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
    'relative_humidity': {
        'id': 28,
        'length': 3,
        'format': '!H',
        },
    }


tags = {'mag_data_x': 1,
        'mag_data_y': 1,
        'mag_data_z': 2,
        'magnetometer_temperature': 3,
        'system_temperature': 4,
        'battery_voltage': 5,
        'time_adjustment': 6,
        'reboot_flags': 7,
        'sampling_interval': 8,
        'paddingByte': 9,
        'padding': 10,
        'current_epoch_time': 11,
        'reboot': 12,
        'current_firmware': 13,
        'upgrade_firmware': 14,
        'get_firmware_page': 15,
        'firmware_page': 16,
        'read_eeprom': 17,
        'eeprom_contents': 18,
        'num_samples': 19,
        'all_samples': 20,
        'mag_data_AllX': 21,
        'mag_data__all_y': 22,
        'mag_data__all_z': 23,
	'cloud_ambient_temperature': 24,
	'cloud_object1_temperature': 25,
	'cloud_object2_temperature': 26,
        'ambientTemp': 27,
        'relative_humidity': 28,
        }

tagNames = ['mag_data_x', 
            'mag_data_y',
            'mag_data_z',
            'magnetometer_temperature',
            'system_temperature',
            'battery_voltage',
            'time_adjustment',
            'reboot_flags',
            'sampling_interval',
            'paddingByte',
            'padding',
            'current_epoch_time',
            'reboot',
            'current_firmware',
            'upgrade_firmware',
            'get_firmware_page',
            'firmware_page',
            'read_eeprom',
            'eeprom_contents',
            'num_samples',
            'all_samples',
            'mag_data_AllX',
            'mag_data__all_y',
            'mag_data__all_z',
            'cloud_ambient_temperature',
            'cloud_object1_temperature',
            'cloud_object2_temperature',
            'ambientTemp', 
            'relative_humidity',
        ]

# Zero means variable length
tag_lengths = {'mag_data_x': 6,
              'mag_data_y': 6,
              'mag_data_z': 6,
              'magnetometer_temperature': 3,
              'system_temperature': 3,
              'battery_voltage': 3,
              'time_adjustment': 7,
              'reboot_flags': 2,
              'sampling_interval': 3,
              'paddingByte': 1,
              'padding': 0,
              'current_epoch_time': 7,
              'reboot': 1, 
              'current_firmware': (size_of_tag + firmware_version_max_length),
              'upgrade_firmware': (size_of_tag + firmware_version_max_length +
                                  size_of_firmware_page_number + size_of_crc),
              'get_firmware_page': (size_of_tag + firmware_version_max_length + 
                                  size_of_firmware_page_number),
              'firmware_page': (size_of_tag + firmware_version_max_length + 
                               size_of_firmware_page_number + firmware_block_size),
              'read_eeprom': 5,
              'eeprom_contents': 0,
              'num_samples': 3,
              'all_samples': 2,
              'mag_data_AllX': 0,
              'mag_data__all_y': 0,
              'mag_data__all_z': 0,
              'cloud_ambient_temperature': 3,
              'cloud_object1_temperature': 3,
              'cloud_object2_temperature': 3,
              'ambientTemp': 3, 
              'relative_humidity': 3,
               } 

tagFormat = {'mag_data_x': '!Bl',
             'mag_data_y': '!Bl',
             'mag_data_z': '!Bl',
             'magnetometer_temperature': '!h',
             'system_temperature': '!h',
             'battery_voltage': '!H',
             'sampling_interval': '!H',
             'current_epoch_time': '!LH',
             'current_firmware': ('!' + str(firmware_version_max_length) + 'c'),
             'upgrade_firmware': ('!' + str(firmware_version_max_length) + 'cHH'),
             'get_firmware_page': ('!' + str(firmware_version_max_length) + 'cH'),
             'firmware_page': ('!' + str(firmware_version_max_length) + 'cH' + 
                              str(firmware_block_size) + 'c'), 
             'read_eeprom': '!HH',
             'num_samples': '!BB',
             'all_samples': '!?',
             'cloud_ambient_temperature': '!h',
             'cloud_object1_temperature': '!h',
             'cloud_object2_temperature': '!h',
             'ambientTemp': '!h', 
             'relative_humidity': '!H',
             }

def format_tag_array_of_longs(tag, dataLen, payload):
    # return ' '.join(map(str, list(struct.unpack('!' + str(dataLen/4) + 'l', str(payload)))))
    return repr(list(struct.unpack('!' + str(dataLen/4) + 'l', str(payload))))
    
def format_padding(tag, dataLen, payload):
    return str([0] * dataLen)

# Horrid hack because cloud data was originally sent as absolute
# temperatures, unlike other tags.
def decodeCloudTemp(tag, payload):
    tmp = (float(struct.unpack('!h', str(payload))[0]) / 100)
    if tmp > 173.15:
        tmp -= 273.15
    return tmp

def formatTagCloudTemp(tag, dataLen, payload):
    return str(decodeCloudTemp(tag, payload)) + '°C'
    # return str((float(struct.unpack('!H', str(payload))[0]-) / 100) - 273.15) + 'Â°C'
    
    
tagFormatFunc = {'padding_byte': format_padding,
                 'padding': format_padding,
                 'mag_data_all_x': format_tag_array_of_longs,
                 'mag_data_all_y': format_tag_array_of_longs,
                 'mag_data_all_z': format_tag_array_of_longs,
                 #'cloud_ambient_temperature': formatTagCloudTemp,
                 #'cloud_object1_temperature': formatTagCloudTemp,
                 #'cloud_object2_temperature': formatTagCloudTemp,
                 }


    
def getHeaderField(buf, offset, size):
    if len(buf) < offset + size:
        return None
    r = 0
    for i in range(size):
        r *= 256
        r += buf[offset + i]
    return r

def getMagic(buf):
    if len(buf) > magic_offset + magic_size:
        return bytearray(buf[magic_offset:magic_offset+magic_size])
        # for i in range(magic_size):
        #    r[i] = buf[magic_offset + i]
        # return r
    else:
        return None
    
def getVersion(buf):
    return getHeaderField(buf, version_offset, version_size)

def getFlags(buf):
    return getHeaderField(buf, flags_offset, flags_size)

def getPacket_length(buf):
    return getHeaderField(buf, packet_length_offset, packet_length_size)

def get_site_id(buf):
    return getHeaderField(buf, site_id_offset, site_id_size)

def getTimestamp(buf):
    seconds = getHeaderField(buf, timestamp_seconds_offset, 
                             timestamp_seconds_size)
    fraction = getHeaderField(buf, timestamp_fraction_offset, 
                              timestamp_fraction_size)
    return [seconds, fraction]

def isSignedMessage(buf):
    global flags_signed_message_bit
    if len(buf) <= flags_offset:
        return None
    return buf[flags_offset] & (1 << flags_signed_message_bit)
    
def is_response_message(buf):
    global flags_response_bit
    if len(buf) <= flags_offset:
        return None
    return buf[flags_offset] & (1 << flags_response_bit)

def getSequence_id(buf):
    if not isSignedMessage(buf):
        return None
    else:
        return buf[getPacket_length(buf) - signature_block_length + sequence_id_offset]

def getRetries(buf):
    if not isSignedMessage(buf):
        return None
    else:
        return buf[getPacket_length(buf) - signature_block_length + retries_offset]
    
def setHeaderField(buf, val, offset, size):
    tmp = val
    for i in range(size-1, -1, -1):
        buf[offset + i] = (tmp & 0xff)
        tmp >>= 8

def setMagic(buf, magic=default_magic):
    for i in range(magic_size):
        buf[i] = magic[i]

def setVersion(buf, version=default_version):
    setHeaderField(buf, version, version_offset, version_size)

def setPacket_length(buf, packet_length):
    setHeaderField(buf, packet_length, packet_length_offset, packet_length_size)

def setFlags(buf, flags):
    setHeaderField(buf, flags, flags_offset, flags_size)
    
def setSite_id(buf, site_id):
    setHeaderField(buf, site_id, site_id_offset, site_id_size)
        
def setTimestamp(buf, seconds, fraction):
    setHeaderField(buf, seconds, timestamp_seconds_offset, 
                   timestamp_seconds_size)
    setHeaderField(buf, fraction, timestamp_fraction_offset, 
                   timestamp_fraction_size)

def putHeader(buf, site_id, timestamp, magic=default_magic, version=default_version, flags=0):
    buf[header_length-1] = 0 # Set size
    setMagic(buf, magic)
    setVersion(buf, version)
    setFlags(buf, flags)
    setPacket_length(buf, header_length)
    setSite_id(buf, site_id)
    setTimestamp(buf, *timestamp)

def putData(buf, tag, data):
    packet_length = getPacket_length(buf) 
    i = packet_length
    buf[i] = tag
    i += 1
    tagName = tagNames[tag]
    tagLen = tag_lengths[tagName]
    if tagLen == 0:
        dataLen = len(data)
        buf[i+1] = dataLen & 0xff
        buf[i] = (dataLen >> 8) & 0xff
        i += 2
        packet_length += 3 + dataLen
    else:
        dataLen = tagLen - 1
        packet_length += tagLen
        
    # TODO: optimise? Use buffer?
    for n in range(dataLen):
        buf[i + n] = data[n]
    setPacket_length(buf, packet_length)
    
def putCurrentUnixTime(buf):
    packet_length = getPacket_length(buf)
    tagLen = tag_lengths['current_epoch_time']
    i = packet_length 
    now = time.time()
    seconds = long(now);
    frac = int(round((now % 1) * 32768.0))

    buf[i] = tags['current_epoch_time']
    i += 1
    for n in range(tagLen-2, -1, -1):
        # buf[i + n] = timestamp & 0xff
        # timestamp >>= 8
        buf[i + n] = 0
    data = bytearray(struct.pack(tagFormat['current_epoch_time'], seconds, frac))
    buf[packet_length + 1 : packet_length + tagLen] = data
    
    setPacket_length(buf, packet_length + tagLen)

def putPadding(buf, padding_length):
    if padding_length == 0:
        return

    if padding_length == 1:
        putData(buf, tags['paddingByte'], [])
    elif padding_length == 2:
        putData(buf, tags['paddingByte'], [])
        putData(buf, tags['paddingByte'], [])
    else:
        putData(buf, tags['padding'], bytearray(padding_length - 3))

def putSignature(buf, hmacKey, retries, sequence_id):
    if isSignedMessage(buf):
        signedLen = getPacket_length(buf)
    else:
        signedLen = getPacket_length(buf) + signature_block_length
        setPacket_length(buf, signedLen)

    buf[flags_offset] |= (1 << flags_signed_message_bit)
    
  
    i = signedLen - signature_block_length
    buf[i] = sequence_id;
    i += 1
    buf[i] = retries
    i += 1
    # Now add HMAC-MD5
    hmacMD5 = hmac.new(hmacKey)# , digestmod=hashlib.md5)
    hmacMD5.update(buf[0:(signedLen - hmac_length)])
    
    # Take least significant bytes
    hmacBytes = hmacMD5.digest()
    buf[(signedLen - hmac_length):signedLen] = hmacBytes[(len(hmacBytes)-hmac_length):]
    # buf[signedLen - 1] = 0xff    
    # buf[signedLen-2] = 99

def makeHeader(site_id, timestamp, magic=default_magic, 
               version=default_version, flags=0):
    buf = bytearray()
    putHeader(buf, site_id, timestamp, magic, version, flags)
    return buf

def parsePacket(buf):
    r = { };
    i = header_length;
    endOfData = getPacket_length(buf)
    if isSignedMessage(buf):
        endOfData -= signature_block_length
    while i < endOfData:
        tag = buf[i]
        i += 1
        if tag >= len(tagNames):
            raise Exception('Unknown tag: ' + str(tag))
        tagName = tagNames[tag]
        tagLen = tag_lengths[tagName]
        if tagLen == 0:
            dataLen = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            dataLen = tagLen - 1
        data = buf[i:(i+dataLen)]
        
        
#        if tagName in tagFormat:
#            data = struct.unpack(tagFormat[tagName], str(data))
#            print(tagName)
#            print(tagFormat[tagName])
#            print(repr(data))
#            print(repr(list(data)))
            
        
        if tagName not in r:
            r[tagName] = []
        r[tagName].append(data)
        i += dataLen
        
    return r

def tidyPendingTags(pendingTags, messageTags):
    delList = []
    for tag in pendingTags:  
        if tag == 'reboot' and 'reboot_flags' in messageTags:
            delList.append(tag)
            
        elif tag == 'upgrade_firmware' and 'current_firmware' in messageTags:
            current_firmware = str(messageTags['current_firmware'][0]).split('\0', 1)[0]
            upgrade_firmware = '' + str(pendingTags[tag]).split('\0', 1)[0]
            if current_firmware == upgrade_firmware:
                # Current firmware version matches so cancel
                print('Firmware already at version ' + upgrade_firmware)
                delList.append(tag)
        
        elif tag == 'all_samples' and bool(ord(pendingTags[tag][0])) == \
            any(t in messageTags for t in ['mag_data__all_x', 
                                           'mag_data__all_y', 'mag_data__all_z']):
            # pendingTags[all_samples][0] must match whether mag_data_All{X,Y,Z}
            # exists in messageTags
            delList.append(tag)
            
        elif tag in ['read_eeprom', 'eeprom_contents'] and \
                'eeprom_contents' in messageTags:
            # TODO: check correct data has been received. NB: if key was sent 
            # it won't be confirmed!
            delList.append(tag)
            
            
        elif tag in messageTags and pendingTags[tag] in messageTags[tag]:
            # This tag appears in messageTags, and one of the values matches
            # pendingTags[tag]
            delList.append(tag)

    for d in delList:
        del pendingTags[d]
    
def myHex(a):
    return hex(a)[2:].zfill(2)
    
def printBuffer(buf, length=None):
    if length is None:
        length = len(buf)
    print(' '.join(map(hex, buf[:length])))
    
def header_to_str_array(buf):
    t = getTimestamp(buf)
    dt = datetime.utcfromtimestamp(t[0] + (t[1]/32768.0))
    return ['Magic: ' + ''.join(map(chr, getMagic(buf))),
            'Version: ' + str(getVersion(buf)),
            'Flags: ' + hex(getFlags(buf)),
            'Packet length: ' + str(getPacket_length(buf)),
            'Site ID: ' + str(get_site_id(buf)),
            ('Timestamp: ' + str(t[0]) + ',' + str(t[1]) 
             + ' (' + dt.isoformat() + ')')]

def printHeader(buf):
    print('Magic: ' + ''.join(map(chr, getMagic(buf))))
    print('Version: ' + str(getVersion(buf)))
    print('Flags: ' + hex(getFlags(buf)))
    print('Packet length: ' + str(getPacket_length(buf)))
    print('Site ID: ' + str(get_site_id(buf)))
    t = getTimestamp(buf)
    dt = datetime.utcfromtimestamp(t[0] + (t[1]/32768.0))
    print('Timestamp: ' + str(t[0]) + ',' + str(t[1]) \
              + ' (' + dt.isoformat() + ')')
    
def printTags(buf):
    i = header_length
    endOfData = getPacket_length(buf)
    if isSignedMessage(buf):
        endOfData -= signature_block_length
    while i < endOfData:
        tag = buf[i]
        i += 1
        if tag >= len(tagNames):
            print('BAD TAG: ' + str(tag))
            return
        tagName = tagNames[tag]
        tagLen = tag_lengths[tagName]
        if tagLen == 0:
            dataLen = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            dataLen = tagLen - 1    
          
        ### TODO: Replace by empty format function
        if tagName == 'firmware_page':
            dataRepr = ''
        elif tagName in tagFormatFunc:
            dataRepr = tagFormatFunc[tagName](tagName, dataLen, buf[i:(i+dataLen)])
        elif tagName in tagFormat:
            dataRepr = repr(list(struct.unpack(tagFormat[tagName],
                                               str(buf[i:(i+dataLen)]))))
        else:
            dataRepr = '0x  ' + ' '.join(map(myHex, buf[i:(i+dataLen)]))
            
        #print(tagName + ' (#' + str(tag) + '): 0x  ' 
        #      + ' '.join(map(myHex, buf[i:(i+dataLen)])) 
        #      + '   ' + dataRepr)
        print(tagName + ' (#' + str(tag) + '):  ' + dataRepr)
        i += dataLen
        
def printSignature(buf):
    if isSignedMessage(buf):
        print('Sequence ID: ' + str(getSequence_id(buf)))
        print('Retries: ' + str(getRetries(buf)))
        packet_length = getPacket_length(buf)
        print('HMAC-MD5: 0x  ' + ' '.join(map(myHex, buf[packet_length-hmac_length:packet_length])))
    else:
        print('Signature: none')
        
def printPacket(buf, message_time=None):
    
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
        # printHeader(buf)
        s.extend(header_to_str_array(buf))
    except Exception as e:
        # print('Error in header: ' + str(e))
        s.append('Error in header: ' + str(e))

    print('\n'.join(s))

    try:
        printTags(buf)
    except Exception as e:
        print('Error in tags: ' + str(e))
    try:
        printSignature(buf)
    except Exception as e:
        print('Error in header: ' + str(e))
    
def validatePacket(buf, hmacKey):
    global default_magic
    completeMessage = False

    valid = True    
    while (len(buf)):
        # print('buf: ' + ' '.join(map(hex, buf)))
    
        valid = True
        
        # Check magic
        for i in range(min(len(default_magic), len(buf))):
            if buf[i] != ord(default_magic[i]):
                valid = False
                break
        
        if len(buf) < len(default_magic):
            break
        
        # Check message is signed
        if isSignedMessage(buf) == None:
            break;

        if isSignedMessage(buf) == False:
            # All transmitted messages must be signed
            valid = False
        
        if valid:
            packet_length = getPacket_length(buf)
            if packet_length is None:
                # Insufficient characters
                break
            elif packet_length < header_length:
                valid = False
            
        if valid and len(buf) >= packet_length:
            completeMessage = True
            # Compute HMAC-MD5
            hmacMD5 = hmac.new(hmacKey)# , digestmod=hashlib.md5)
            hmacMD5.update(buf[0:(packet_length - hmac_length)])
            
            
            # Take least significant bytes
            hmacBytes = hmacMD5.digest()
            hmacBytes = hmacBytes[(len(hmacBytes)-hmac_length):]
            
            # Compare. To prevent timing attacks don't stop the 
            # comparison early and aim to have all outcomes take the
            # same time.
            receivedHmacBytes = buf[(packet_length - hmac_length):]

            for i in range(hmac_length):
                valid = (ord(hmacBytes[i]) == receivedHmacBytes[i]) and valid
            if not valid:
                print('#########################')
                print('Packet failed HMAC-MD5, computed as ' +
                      ' '.join(map(myHex, map(ord, hmacBytes))))
                try:
                    # Be wary of printing invalid packets!
                    printPacket(buf)
                except:
                    None
                print('#########################')
            
        # All tests done
        if valid:
            if completeMessage:
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

def getImageFilename(version, crcFile=False):
    # TODO: use config file
    filename = os.path.join('/var/aurorawatchnet/firmware', version);
    if crcFile:
        filename += '.crc'
    else:
        filename += '.bin'
    return filename
    
def adcCountsToTesla(val, magTeslaPerVolt=50e-6):
    # Data is normalised too allow for maximum resolution of 18 bits and
    # 8x gain. Thus largest possible normalised magnitude is 2^17 * 8.
    # Largest magnitude of ADC output is from +/- 2.048V   

    scaleFactor = 2.048 * magTeslaPerVolt / (pow(2,17) * 8)
    return val * scaleFactor
