#!/usr/bin/env python

from __future__ import print_function

import binascii
from optparse import OptionParser
import os
import struct
import subprocess

import AW_Message


# Parse command line options

usage = "usage: %prog [options] firmware.elf"
optParser = OptionParser(usage)
optParser.add_option("-e", "--elf-file", dest="elfFilename",
                     metavar="file.elf", help="ELF file")
optParser.add_option("-f", "--firmware-version", dest="firmwareVersion", 
                     metavar="version", help="firmware version")

(options, args) = optParser.parse_args()

if len(args) != 0:
    optParser.error("incorrect arguments")

if not os.path.exists(options.elfFilename):
    print(options.elfFilename + " does not exist")
    os.sys.exit(1)

# TODO: Use config file
fwPath = "/var/aurorawatchnet/firmware"
binFilename = os.path.join(fwPath, options.firmwareVersion + ".bin")
crcFilename = os.path.join(fwPath, options.firmwareVersion + ".crc")

if os.path.exists(binFilename):
    print("Error: " + binFilename + " already exists")
    os.sys.exit(1)
if os.path.exists(crcFilename):
    print("Error: " + crcFilename + " already exists")
    os.sys.exit(1)

try:
    cmd = ["avr-objcopy", "-O", "binary", options.elfFilename, binFilename]
    subprocess.check_call(cmd)
except subprocess.CalledProcessError as e:
    print("Could not convert firmware file: " + str(e))
    os.sys.exit(1)
        
# Windows support doubtful but use binary mode anyway
binFile = open(binFilename, "a+b") 
binContents = binFile.read()

blockSize = AW_Message.firmware_block_size
# blockSize = 256;
if len(binContents) % blockSize:
    # Pad the file to the block size used for transmission
    padding = chr(0xFF) * (blockSize - (len(binContents) % blockSize))
    binContents += padding
    binFile.write(padding)
binFile.close()

# The CRC check must be computed over the entire temporary 
# application section; extend as necessary
tempAppSize = (131072 - 4096) / 2;
if len(binContents) < tempAppSize:
    padding = chr(0xFF) * (tempAppSize - len(binContents))
    binContents += padding
elif len(binContents) > tempAppSize:
    print("Firmware image too large (" + str(len(binContents)) + " bytes)")
    os.sys.exit(1)
    
crc = AW_Message.crc16(binContents)
crcFile = open(crcFilename, "w")
crcStr = struct.pack(">H", crc)
# Output in similar way to md5sum
print(binascii.hexlify(crcStr) + "  " + options.firmwareVersion, file=crcFile)
crcFile.close()

