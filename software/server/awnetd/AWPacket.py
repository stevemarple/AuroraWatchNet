# import datetime
from datetime import datetime
import hashlib
import hmac
import os
import struct
import time



__all__ = ["validatePacket"]

defaultMagic = "AW"
defaultVersion = 1

headerLength = 12
signatureBlockLength = 10
magicOffset = 0
magicSize = len(defaultMagic)
versionOffset = 2
versionSize = 1
flagsOffset = 3
flagsSize = 1
packetLengthOffset = 4
packetLengthSize = 2
siteIdOffset = 6
siteIdSize = 2
timestampOffset = 8
timestampSize = 4
numAxes = 3

# Signature offsets are relative to the start of the signature block,
# which starts at packetLength - signatureBlockLength
sequenceIdOffset = 0
sequenceIdSize = 1
retriesOffset = 1
retriesSize = 1
hmacOffset = 2
hmacLength = 8


flagsSignedMessageBit = 0
sizeOfTag = 1
sizeOfPacketLength = 2
sizeOfFirmwarePageNumber = 2
sizeOfCrc = 2

firmwareVersionMaxLength = 16

# Defines the block size used for firmware updates.
firmwareBlockSize = 128

tags = {"magDataX": 1,
        "magDataY": 1,
        "magDataZ": 2,
        "sensorTemperature": 3,
        "MCUTemperature": 4,
        "batteryVoltage": 5,
        "timeAdjustment": 6,
        "rebootFlags": 7,
        "samplingInterval": 8,
        "paddingByte": 9,
        "padding": 10,
        "currentUnixTime": 11,
        "reboot": 12,
        "currentFirmware": 13,
        "upgradeFirmware": 14,
        "getFirmwarePage": 15,
        "firmwarePage": 16,
        }

tagNames = ["magDataX", 
            "magDataY",
            "magDataZ",
            "sensorTemperature",
            "MCUTemperature",
            "batteryVoltage",
            "timeAdjustment",
            "rebootFlags",
            "samplingInterval",
            "paddingByte",
            "padding",
            "currentUnixTime",
            "reboot",
            "currentFirmware",
            "upgradeFirmware",
            "getFirmwarePage",
            "firmwarePage",
        ]

# Zero means variable length
tagLengths = {"magDataX": 6,
              "magDataY": 6,
              "magDataZ": 6,
              "sensorTemperature": 3,
              "MCUTemperature": 3,
              "batteryVoltage": 3,
              "timeAdjustment": 5,
              "rebootFlags": 2,
              "samplingInterval": 5, # ???
              "paddingByte": 1,
              "padding": 0,
              "currentUnixTime": 5,
              "reboot": 1, 
              "currentFirmware": (sizeOfTag + firmwareVersionMaxLength),
              "upgradeFirmware": (sizeOfTag + firmwareVersionMaxLength +
                                  sizeOfFirmwarePageNumber + sizeOfCrc),
              "getFirmwarePage": (sizeOfTag + firmwareVersionMaxLength + 
                                  sizeOfFirmwarePageNumber),
              "firmwarePage": (sizeOfTag + firmwareVersionMaxLength + 
                               sizeOfFirmwarePageNumber + firmwareBlockSize),
              } 

tagFormat = {"samplingInterval": "!L",
             "currentUnixTime": "!L",
             "currentFirmware": ("!" + str(firmwareVersionMaxLength) + "c"),
             "upgradeFirmware": ("!" + str(firmwareVersionMaxLength) + "cHH"),
             "getFirmwarePage": ("!" + str(firmwareVersionMaxLength) + "cH"),
             "firmwarePage": ("!" + str(firmwareVersionMaxLength) + "cH" + 
                              str(firmwareBlockSize) + "c"), 
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
    if len(buf) > magicOffset + magicSize:
        return bytearray(buf[magicOffset:magicOffset+magicSize])
        # for i in range(magicSize):
        #    r[i] = buf[magicOffset + i]
        # return r
    else:
        return None
    
def getVersion(buf):
    return getHeaderField(buf, versionOffset, versionSize)

def getFlags(buf):
    return getHeaderField(buf, flagsOffset, flagsSize)

def getPacketLength(buf):
    return getHeaderField(buf, packetLengthOffset, packetLengthSize)

def getSiteId(buf):
    return getHeaderField(buf, siteIdOffset, siteIdSize)

def getTimestamp(buf):
    return getHeaderField(buf, timestampOffset, timestampSize)

def isSignedMessage(buf):
    global flagsSignedMessageBit
    if len(buf) <= flagsOffset:
        return None
    return buf[flagsOffset] & (1 << flagsSignedMessageBit)
    
def getSequenceId(buf):
    if not isSignedMessage(buf):
        return None
    else:
        return buf[getPacketLength(buf) - signatureBlockLength + sequenceIdOffset]

def getRetries(buf):
    if not isSignedMessage(buf):
        return None
    else:
        return buf[getPacketLength(buf) - signatureBlockLength + retriesOffset]
    
def setHeaderField(buf, val, offset, size):
    tmp = val
    for i in range(size-1, -1, -1):
        buf[offset + i] = (tmp & 0xff)
        tmp >>= 8

def setMagic(buf, magic=defaultMagic):
    for i in range(magicSize):
        buf[i] = magic[i]

def setVersion(buf, version=defaultVersion):
    setHeaderField(buf, version, versionOffset, versionSize)

def setPacketLength(buf, packetLength):
    setHeaderField(buf, packetLength, packetLengthOffset, packetLengthSize)

def setFlags(buf, flags):
    setHeaderField(buf, flags, flagsOffset, flagsSize)
    
def setSiteId(buf, siteId):
    setHeaderField(buf, siteId, siteIdOffset, siteIdSize)
        
def setTimestamp(buf, timestamp):
    setHeaderField(buf, timestamp, timestampOffset, timestampSize)

def putHeader(buf, siteId, timestamp, magic="AW", version=defaultVersion, flags=0):
    buf[headerLength-1] = 0 # Set size
    setMagic(buf, magic)
    setVersion(buf, version)
    setFlags(buf, flags)
    setPacketLength(buf, headerLength)
    setSiteId(buf, siteId)
    setTimestamp(buf, timestamp)

def putData(buf, tag, data):
    packetLength = getPacketLength(buf) 
    i = packetLength
    buf[i] = tag
    i += 1
    tagName = tagNames[tag]
    tagLen = tagLengths[tagName]
    if tagLen == 0:
        dataLen = len(data)
        buf[i+1] = dataLen & 0xff
        buf[i] = (dataLen >> 8) & 0xff
        i += 2
        packetLength += 3 + dataLen
    else:
        dataLen = tagLen - 1
        packetLength += tagLen
        
    # TODO: optimise? Use buffer?
    for n in range(dataLen):
        buf[i + n] = data[n]
    setPacketLength(buf, packetLength)
    
def putCurrentUnixTime(buf):
    packetLength = getPacketLength(buf)
    tagLen = tagLengths["currentUnixTime"]
    i = packetLength 
    timestamp = long(round(time.time()))
    buf[i] = tags["currentUnixTime"]
    i += 1
    for n in range(tagLen-2, -1, -1):
        buf[i + n] = timestamp & 0xff
        timestamp >>= 8
    setPacketLength(buf, packetLength + tagLen)

def putPadding(buf, paddingLength):
    if paddingLength == 0:
        return

    if paddingLength == 1:
        putData(buf, tags["paddingByte"], [])
    elif paddingLength == 2:
        putData(buf, tags["paddingByte"], [])
        putData(buf, tags["paddingByte"], [])
    else:
        putData(buf, tags["padding"], bytearray(paddingLength - 3))

def putSignature(buf, hmacKey, retries, sequenceId):
    if isSignedMessage(buf):
        signedLen = getPacketLength(buf)
    else:
        signedLen = getPacketLength(buf) + signatureBlockLength
        setPacketLength(buf, signedLen)

    buf[flagsOffset] |= (1 << flagsSignedMessageBit)
    
  
    i = signedLen - signatureBlockLength
    buf[i] = sequenceId;
    i += 1
    buf[i] = retries
    i += 1
    # Now add HMAC-MD5
    hmacMD5 = hmac.new(hmacKey)# , digestmod=hashlib.md5)
    hmacMD5.update(buf[0:(signedLen - hmacLength)])
    
    # Take least significant bytes
    hmacBytes = hmacMD5.digest()
    buf[(signedLen - hmacLength):signedLen] = hmacBytes[(len(hmacBytes)-hmacLength):]
    # buf[signedLen - 1] = 0xff    
    # buf[signedLen-2] = 99

def makeHeader(siteId, timestamp, magic="AW", 
               version=defaultVersion, flags=0):
    buf = bytearray()
    putHeader(buf, siteId, timestamp, magic, version, flags)
    return buf

def parsePacket(buf):
    r = { };
    i = headerLength;
    endOfData = getPacketLength(buf)
    if isSignedMessage(buf):
        endOfData -= signatureBlockLength
    while i < endOfData:
        tag = buf[i]
        i += 1
        if tag >= len(tagNames):
            raise Exception("Unknown tag: " + str(tag))
        tagName = tagNames[tag]
        tagLen = tagLengths[tagName]
        if tagLen == 0:
            dataLen = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            dataLen = tagLen - 1
        data = buf[i:(i+dataLen)]
#        if tagName in tagFormat:
#            print(tagName)
#            print(repr(data))
#            print(tagFormat[tagName])
#            data = struct.unpack(tagFormat[tagName], str(data))
        if tagName not in r:
            r[tagName] = []
        r[tagName].append(data)
        i += dataLen
        
    return r

def tidyPendingTags(pendingTags, messageTags):
    delList = []
    for tag in pendingTags:  
        if tag == "reboot" and "rebootFlags" in messageTags:
            delList.append(tag)
            
        elif tag == "upgradeFirmware" and "currentFirmware" in messageTags:
            currentFirmware = str(messageTags["currentFirmware"][0]).split('\0', 1)[0]
            upgradeFirmware = "" + str(pendingTags[tag]).split('\0', 1)[0]
            if currentFirmware == upgradeFirmware:
                # Current firmware version matches so cancel
                print("Firmware already at version " + upgradeFirmware)
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
    print(" ".join(map(hex, buf[:length])))
    
def printHeader(buf):
    print("Magic: " + "".join(map(chr, getMagic(buf))))
    print("Version: " + str(getVersion(buf)))
    print("Flags: " + hex(getFlags(buf)))
    print("Packet length: " + str(getPacketLength(buf)))
    print("Site ID: " + str(getSiteId(buf)))
    t = getTimestamp(buf)
    dt = datetime.utcfromtimestamp(t)
    print("Timestamp: " + str(t) + " (" + dt.isoformat() + ")")
    
def printTags(buf):
    i = headerLength
    endOfData = getPacketLength(buf)
    if isSignedMessage(buf):
        endOfData -= signatureBlockLength
    while i < endOfData:
        tag = buf[i]
        i += 1
        if tag >= len(tagNames):
            print("BAD TAG: " + str(tag))
            return
        tagName = tagNames[tag]
        tagLen = tagLengths[tagName]
        if tagLen == 0:
            dataLen = (buf[i] << 8) + buf[i+1]
            i += 2
        else:
            dataLen = tagLen - 1    
        print(tagName + " (#" + str(tag) + "): 0x  " 
              + " ".join(map(myHex ,buf[i:(i+dataLen)])))
        i += dataLen
        
def printSignature(buf):
    if isSignedMessage(buf):
        print("Sequence ID: " + str(getSequenceId(buf)))
        print("Retries: " + str(getRetries(buf)))
        packetLength = getPacketLength(buf)
        print("HMAC-MD5: 0x  " + " ".join(map(myHex, buf[packetLength-hmacLength:packetLength])))
    else:
        print("Signature: none")
        
def printPacket(buf):
    printHeader(buf)
    printTags(buf)
    printSignature(buf)
    
def validatePacket(buf, hmacKey):
    global defaultMagic
    completeMessage = False

    valid = True    
    while (len(buf)):
        # print("buf: " + " ".join(map(hex, buf)))
    
        valid = True
        
        # Check magic
        for i in range(min(len(defaultMagic), len(buf))):
            if buf[i] != ord(defaultMagic[i]):
                valid = False
                break
        
        if len(buf) < len(defaultMagic):
            break
        
        # Check message is signed
        if isSignedMessage(buf) == None:
            break;

        if isSignedMessage(buf) == False:
            # All transmitted messages must be signed
            valid = False
        
        if valid:
            packetLength = getPacketLength(buf)
            if packetLength is None:
                # Insufficient characters
                break
            elif packetLength < headerLength:
                valid = False
            
        if valid and len(buf) >= packetLength:
            completeMessage = True
            # Compute HMAC-MD5
            hmacMD5 = hmac.new(hmacKey)# , digestmod=hashlib.md5)
            hmacMD5.update(buf[0:(packetLength - hmacLength)])
            
            
            # Take least significant bytes
            hmacBytes = hmacMD5.digest()
            hmacBytes = hmacBytes[(len(hmacBytes)-hmacLength):]
            
            # Compare. To prevent timing attacks don't stop the 
            # comparison early and aim to have all outcomes take the
            # same time.
            receivedHmacBytes = buf[(packetLength - hmacLength):]

            for i in range(hmacLength):
                valid = (ord(hmacBytes[i]) == receivedHmacBytes[i]) and valid
            if not valid:
                print("#########################")
                print("Packet failed HMAC-MD5, computed as " +
                      " ".join(map(myHex, map(ord, hmacBytes))))
                printPacket(buf)
                print("#########################")
            
        # All tests done
        if valid:
            if completeMessage:
                r = bytearray(buf[0:packetLength])
                del buf[0:packetLength]
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
    filename = os.path.join("/var/aurorawatchnet/firmware", version);
    if crcFile:
        filename += ".crc"
    else:
        filename += ".bin"
    return filename
    
    
