#!/usr/bin/env python

import binascii
from optparse import OptionParser
import struct
import AWPacket

# Parse command line options
usage = "usage: %prog [options] files ..."
optParser = OptionParser(usage)

(options, args) = optParser.parse_args()

if len(args) == 0:
    optParser.error("filename required")

for filename in args:
    binfile = open(filename)
    # crcfile = open(filename + ".crc")
    crc = AWPacket.crc16(binfile.read())
    binfile.close()
    crcStr = struct.pack(">H", crc)
    # Output in similar way to md5sum
    print(binascii.hexlify(crcStr) + "  " + filename)
