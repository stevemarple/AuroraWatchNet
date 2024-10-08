#!/usr/bin/env python

from __future__ import print_function

import argparse
import binascii
import os
import struct
import subprocess

import aurorawatchnet as awn
import aurorawatchnet.message


# Parse command line options

parser = argparse.ArgumentParser(description='Make firmware image files')
parser.add_argument('-e', '--elf-file',
                    required=True,
                    dest='elf_filename',
                    help='ELF file',
                    metavar='file.elf')
parser.add_argument('-f', '--firmware-version',
                    required=True,
                    help='firmware version',
                    metavar='version')

options = parser.parse_args()

if not os.path.exists(options.elf_filename):
    print(options.elf_filename + ' does not exist')
    os.sys.exit(1)

fw_path = os.path.dirname(options.elf_filename)
bin_filename = os.path.join(fw_path, options.firmware_version + '.bin')
crc_filename = os.path.join(fw_path, options.firmware_version + '.crc')
if os.path.exists(bin_filename) or os.path.exists(crc_filename):
    bin_filename
try:
    cmd = ['avr-objcopy', '-O', 'binary', options.elf_filename, bin_filename]
    subprocess.check_call(cmd)
except subprocess.CalledProcessError as e:
    print('Could not convert firmware file: ' + str(e))
    os.sys.exit(1)

# Windows support doubtful but use binary mode anyway
bin_file = open(bin_filename, 'r+b')
bin_contents = bin_file.read()

block_size = awn.message.firmware_block_size
print(f'mkfwimage.py: bin file: {len(bin_contents)}')
if len(bin_contents) % block_size:
    # Pad the file to the block size used for transmission
    padding = b'\xff' * (block_size - (len(bin_contents) % block_size))
    print(f'Adding {len(padding)} padding byte(s)')
    bin_contents += padding
    bin_file.write(padding)
bin_file.close()

# The CRC check must be computed over the entire temporary
# application section; extend as necessary
temp_app_size = (131072 - 4096) // 2
if len(bin_contents) < temp_app_size:
    padding = b'\xff' * (temp_app_size - len(bin_contents))
    bin_contents += padding
elif len(bin_contents) > temp_app_size:
    print('Firmware image too large (' + str(len(bin_contents)) + ' bytes)')
    os.sys.exit(1)

crc = awn.message.crc16(bin_contents)
crc_file = open(crc_filename, 'w')
crc_str = struct.pack('>H', crc)
# Output in similar way to md5sum
print(binascii.hexlify(crc_str).decode('ascii') + '  ' + options.firmware_version,
      file=crc_file)
crc_file.close()

print('mkfwimage.py done')
