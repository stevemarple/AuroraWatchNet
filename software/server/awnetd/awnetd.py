#!/usr/bin/env python

import binascii
from curses import ascii 
import math
import os
import select
import socket
import struct
import sys
from optparse import OptionParser
import termios
import time
import tty

import hmac
# from AWPacket import getTimestamp, getPacketLength, tagNames, tagLengths
import AWPacket

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import AWPacket



def readConfig(configFile):
    global config
    global siteIds
    config = SafeConfigParser()
    
    config.add_section("daemon")
    config.set("daemon", "pidfile", "/tmp/test.pid")
    config.set("daemon", "user", "nobody")
    config.set("daemon", "group", "nogroup")
    
    config.add_section("serial")
    config.set("serial", "port", "/dev/ttyACM0")
    # config.set("serial", "port", "/tmp/data")
    config.set("serial", "baudrate", "9600")
    config.set("serial", "blocksize", "12")
    
#    config.add_section("magnetometer")
#    config.set("magnetometer", "datatransferdelay", "2")

    config.add_section("firmware")
    config.set("firmware", "path", "/tmp/firmware")
    
    # TOD: Handle multiple stations 
    config.add_section("s")
    config.set("s", "path", '/s/aurorawatch/net')
    if configFile:
        configFilesRead = config.read(configFile)
        print("## Config files read: " + ", ".join(configFilesRead))

    if config.has_option("s", "siteids"):
        siteIds = config.get("s", "siteids").split()
    else:
        siteIds = []

    
    print("## Serial port: " + config.get('serial', 'port'))

# AuroraWatch realtime file
realtimeFile = None
def writeAuroraWatchRealTimeData(timestamp, data):
    global realtimeFile
    seconds = long(round(timestamp[0] + (timestamp[1]/32768.0)))
    tmpName = time.strftime(config.get("aurorawatchrealtime", 
                                       "filename"),
                            time.gmtime(seconds))
    if realtimeFile is not None and tmpName != realtimeFile.name:
        # Filename has changed
        realtimeFile.close()
        realtimeFile = None
            
    if realtimeFile is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmpName)
        if not os.path.isdir(p):
            try:
                os.makedirs(p)
            except Exception as e:
                print("Could not make directory " + p + str(e))
                return
        
        try:
            realtimeFile = open(tmpName, "a+", 1)
        except Exception as e:
            print("Exception was " + str(e))
            realtimeFile = None
    
    if realtimeFile is not None:
        realtimeFile.write("{:05d}".format(seconds % 86400))
        for tag in ["magDataX", "magDataY", "magDataZ"]:
            if tag in data:
                realtimeFile.write(" {:.1f}".format(data[tag]))
            else:
                realtimeFile.write(" nan")
        realtimeFile.write("\n")

    
# Process any CR or LF terminated messages which are in the buffer    
def handleControlMessage(buf, pendingTags):
    r = []
    while len(buf):
        cmds = buf.splitlines()
        if cmds[0] == buf:
            # no newlines
            # return None
            break;
        
        cmd = cmds[0]
        # Assign back to the input reference
        buf[:] = "\n".join(cmds[1:])
        
        if cmd == "" or cmd.startswith("#"):
            continue
        
        if cmd.startswith("samplingInterval="):
            val = float(cmd.replace("samplingInterval=", "", 1)) * 16
            # pendingTags["samplingInterval"] = struct.pack('!L', val)
            pendingTags["samplingInterval"] = \
                struct.pack(AWPacket.tagFormat["samplingInterval"], val)
            r.append("samplingInterval:" + str(val / 16))
        
        elif cmd.startswith("upgradeFirmware="):
            version = str(cmd.replace("upgradeFirmware=", "", 1))
            try:
                handleCmdUpgradeFirmware(version)
                r.append("upgradeFirmware:" + version)
            except Exception as e:
                r.append("ERROR: " + str(e))
                    
        elif cmd == "reboot=TRUE":
            pendingTags["reboot"] = [];
            r.append("reboot:TRUE")
            
    print("\n".join(r))
    #print(repr(pendingTags))
    
    return r


def getFirmwareDetails(version):
    filename = os.path.join(config.get("firmware", "path"),
                            version + ".bin")
    crcFilename = os.path.join(config.get("firmware", "path"),
                            version + ".crc")

    if not os.path.exists(filename):
        raise Exception("firmware file " + filename + " does not exist")
    if not os.path.exists(crcFilename):
        raise Exception("CRC file " + crcFilename + " does not exist")
    firmwareFile = open(filename)
    firmware = firmwareFile.read();
    firmwareFile.close()
    
    if len(firmware) % AWPacket.firmwareBlockSize != 0:
        raise Exception("firmware file " + filename + " not a multiple  of "
                        + str(AWPacket.firmwareBlockSize) + " bytes")

    # Be paranoid about the CRC file
    crcFile = open(crcFilename)
    crcContents = crcFile.read()
    crcFile.close()
    crcLines = crcContents.splitlines()
    if len(crcLines) != 1:
        raise Exception("Bad file format for " + crcFilename)
    crcCols = crcLines[0].split()
    statedCrcHex = crcCols[0]
    statedVersion = crcCols[1]
    statedCrc = int(struct.unpack(">H", binascii.unhexlify(statedCrcHex))[0])
    
    # The CRC check must be computed over the entire temporary 
    # application section; extend as necessary
    tempAppSize = (131072 - 4096) / 2;
    if len(firmware) < tempAppSize:
        padding = chr(0xFF) * (tempAppSize - len(firmware))
        paddedFirmware = firmware + padding
    elif len(firmware) > tempAppSize:
        raise Exception("Firmware image too large (" + str(len(firmware)) + " bytes)")
    else:
        paddedFirmware = firmware
    
    actualCrc = AWPacket.crc16(paddedFirmware)
    if actualCrc != statedCrc:
        raise Exception("Firmware CRC does not match with " + crcFilename + " " + str(actualCrc) + " " + str(statedCrc))
    if version != statedVersion:
        raise Exception("Version does not match with " + crcFilename)
    return statedCrc, len(firmware) / AWPacket.firmwareBlockSize

def handleCmdUpgradeFirmware(version):
    if len(version) > AWPacket.firmwareVersionMaxLength:
        raise Exception("Bad version")
    
    versionStr = str(version)
    # crc, numPages = getFirmwareDetails(version.decode("ascii"))
    crc, numPages = getFirmwareDetails(versionStr)
    paddedVersion = version + ("\0" * (AWPacket.firmwareVersionMaxLength
                                      - len(version)))
    args = list(paddedVersion)
    args.append(numPages)
    args.append(crc)
    pendingTags["upgradeFirmware"] = \
        struct.pack(AWPacket.tagFormat["upgradeFirmware"], *args)
    
    
# Deal with any item requested in the incoming packet
def handlePacketRequests(messageTags):
    try:
        if "getFirmwarePage" in messageTags:
            # Write the page to requested tags
            packetReqGetFirmwarePage(messageTags["getFirmwarePage"][0])
    except Exception as e:
        None 
    
def packetReqGetFirmwarePage(data):
    global requestedTags
    unpackedData = struct.unpack(AWPacket.tagFormat["getFirmwarePage"],
                                 buffer(data)) 
    version = "".join(unpackedData[0:AWPacket.firmwareVersionMaxLength])
    versionStr = version.split('\0', 1)[0]
                                                         
    pageNumber, = unpackedData[AWPacket.firmwareVersionMaxLength:]
    imageFilename = AWPacket.getImageFilename(versionStr)
    imageFile = open(imageFilename)
    
    # Ensure file is closed in the case of any error
    try:   
        imageFile.seek(AWPacket.firmwareBlockSize * pageNumber)
        fwPage = imageFile.read(AWPacket.firmwareBlockSize)
    except:
        print("SOME ERROR")
        # Some error, so don't try adding to requestedTags
        return
    finally:
        # Ensure file is closed in all circumstances
        imageFile.close()

    args = list(version)
    args.append(pageNumber)
    args.extend(list(fwPage))
    requestedTags["firmwarePage"] = struct.pack(AWPacket.tagFormat["firmwarePage"], *args) 
    
# ==========================================================================

# Parse command line options
optParser = OptionParser()
optParser.add_option("-c", "--config-file", dest="configFile", 
                     help="Configuration file")

(options, args) = optParser.parse_args()


readConfig(options.configFile)
if siteIds:
    print("Site IDs: " + ", ".join(siteIds))
else:
    print("Site IDs: none")
    
print("Done")
commsBlockSize = int(config.get("serial", "blocksize"))

device = open(config.get("serial", "port"), "a+b", 0)
tty.setraw(device, termios.TCIOFLUSH)

termAttr = termios.tcgetattr(device)
termAttr[4] = termAttr[5] = termios.B57600
termios.tcsetattr(device, termios.TCSANOW, termAttr)

# tty.CBAUD = tty.B57600
# tty.CBAUD = tty.B115200

if config.has_option("controlsocket", "filename"):
    if os.path.exists(config.get("controlsocket", "filename")):
        os.remove(config.get("controlsocket", "filename"))
    controlSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # controlSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    controlSocket.bind(config.get("controlsocket", "filename"))
    # controlSocket.setblocking(False)
    controlSocket.listen(1)
else:
    controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    controlSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # ord('A'_ = 65, ord('W') = 87 
    controlSocket.bind(("", 6587))
    controlSocket.setblocking(False)
    controlSocket.listen(0)
    
controlSocketConn = None
controlBuffer = None

# Pending tags are persistent and are removed when acknowledged
pendingTags = {}

selectList = [device, controlSocket]
hmacKey = "".join(map(chr, [255, 255, 255, 255, 255, 255, 255, 255, 
                            255, 255, 255, 255, 255, 255, 255, 255]))

buf = bytearray()


# Discard any characters already present in the device
termios.tcflush(device, termios.TCIOFLUSH)

running = True
while running:
    try:
        if controlSocketConn is None:
            inputready,outputready,exceptready = select.select(selectList,[],[])
        else:
            selectList2 = selectList[:]
            selectList2.append(controlSocketConn)
            inputready,outputready,exceptready = select.select(selectList2,[],[])
    except select.error as e:
        print("select error: " + str(e))
        break
    except socket.error as e:
        print("socket error: " + str(e))
        break
    
    for fd in inputready:
        # print("FD: " + str(fd)) 

        if fd == device:
            s = fd.read(1)
            if len(s) == 0:
                # end of file
                running = False
                break
    
#            if ascii.isprint(s):
#                print(s)   
#            else:
#                print(hex(ord(s)))
    
            buf.append(s)
            message = AWPacket.validatePacket(buf, hmacKey)
            if message is not None:
                print("=============")
                print("Valid message: ")
                # AWPacket.printBuffer(message)
                AWPacket.printPacket(message)
                
                if fd.isatty():
                    # Not a file, so send a acknowledgement
                    messageTags = AWPacket.parsePacket(message)
                    AWPacket.tidyPendingTags(pendingTags, messageTags)
                        
                    print("Response: ------")
                    response = bytearray(1024)
                    timestamp = AWPacket.getTimestamp(message)
                    AWPacket.putHeader(response, 
                                       siteId=AWPacket.getSiteId(message),
                                       timestamp=timestamp)
                    AWPacket.putCurrentUnixTime(response)
                    
                    # Handle packet requests. These tags live only for the 
                    # duration between receiving the request and sending the
                    # response.
                    requestedTags = {}
                    handlePacketRequests(messageTags)
                    for tag in requestedTags:
                        AWPacket.putData(response, AWPacket.tags[tag], requestedTags[tag])
                    

                    for tag in pendingTags:
                        AWPacket.putData(response, AWPacket.tags[tag], pendingTags[tag])
                        # del pendingTags[tag]
                        
                    # Add padding to round up to a multiple of block size
                    paddingLength = (commsBlockSize - 
                                     ((AWPacket.getPacketLength(response) +
                                       AWPacket.signatureBlockLength) %
                                      commsBlockSize))
                    AWPacket.putPadding(response, paddingLength)
                    AWPacket.putSignature(response, hmacKey, 
                                          AWPacket.getRetries(message), 
                                          AWPacket.getSequenceId(message))
                    
                    # Trim spare bytes from end of buffer
                    del response[AWPacket.getPacketLength(response):]
                    AWPacket.printPacket(response)
                    fd.write(response)
                    
                    if config.has_option("aurorawatchrealtime", "filename"):
                        data = { }
                        for tag in ["magDataX", "magDataY", "magDataZ"]:
                            if tag in messageTags:
                                comp = struct.unpack(AWPacket.tagFormat[tag], 
                                                     str(messageTags[tag][0]))
                                data[tag] = comp[1];
                                writeAuroraWatchRealTimeData(timestamp, data)

                        
        elif fd == controlSocket:
            if controlSocketConn is not None:
                try:
                    controlSocketConn.shutdown(socket.SHUT_RDWR)
                except:
                    None
            controlSocketConn = None
            try:
                (controlSocketConn, client_address) = controlSocket.accept()
                controlSocketConn.settimeout(10)
                controlBuffer = bytearray()
            except Exception as e:
                print("ERROR: " + str(e))
                controlSocketConn = None


        elif fd == controlSocketConn:
            try:
                s = controlSocketConn.recv(1024)
                if s:
                    controlBuffer += s
                    handleControlMessage(controlBuffer, pendingTags)
            except Exception as e:
                print("ERROR: " + str(e))
                controlSocketConn = None
        else:
            print("Other: " + str(fd))
