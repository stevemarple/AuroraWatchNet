#include <avr/eeprom.h>
#include "AWPacket.h"
#include "Arduino.h"

#include <AwEeprom.h>

extern "C" {
#include "hmac-md5.h"
}

const char AWPacket::magic[AWPacket::magicLength] = {'A', 'W'};

/* Array of total lengths for each tag. A zero length indicates that
 * the length is variable, the first two bytes (in network byte order)
 * following the tag indicate the payload size.
 */
const uint16_t AWPacket::tagLengths[27] = {
  6, // 0 = X
  6, // 1 = Y
  6, // 2 = Z
  3, // 3 = sensorTemperature
  3, // 4 = mcuTemperature
  3, // 5 = batteryVoltage
  7, // 6 = timeAdjustment
  2, // 7 = rebootFlags
  3, // 8 = samplingInterval
  1, // 9 = paddingByte
  0, // 10 = padding (variable length)
  7, // 11 = currentUnixTime
  1, // 12 = reboot (command)
  (sizeOfTag + firmwareNameLength), // 13 = current firmware
  (sizeOfTag + firmwareNameLength +
   sizeOfFirmwarePageNumber + sizeOfCrc), // 14 = upgrade firmware
  (sizeOfTag + firmwareNameLength +
   sizeOfFirmwarePageNumber), // 15 = get firmware page
  (sizeOfTag + firmwareNameLength +
   sizeOfFirmwarePageNumber + firmwareBlockSize), // 16 = firmware page
  5, // 17 = readEeprom
  0, // 18 = eepromContents (variable length)
  3, // 19 = numSamples (numSamples, bit field)
  2, // 20 = allSamples (bool)
  0, // 21 = magDataAllX
  0, // 22 = magDataAllY
  0, // 23 = magDataAllZ
  3, // 24 = cloudTempAmbient
  3, // 25 = cloudTempObject1
  3, // 26 = cloudTempObject2
};

uint8_t AWPacket::defaultSequenceId = 0;
uint16_t AWPacket::defaultSiteId = 0;

// AVR-libc doesn't have htobe32 etc
void AWPacket::avrToNetwork(void* dest, const void* src, uint8_t len)
{
  uint8_t *dptr = (uint8_t*)dest;
  const uint8_t *sptr = (uint8_t*)src;
  sptr += len - 1;
  for (uint8_t i = 0; i < len; ++i) {
    *dptr++ = *sptr--;
  }
}

bool AWPacket::getCurrentUnixTime(const uint8_t* buffer, int32_t &t)
{
  const uint8_t *ptr = findTag(buffer, tagCurrentUnixTime);
  if (ptr == NULL)
    return false;

  networkToAvr(&t, ptr, sizeof(t));
  return true;
}

const uint8_t* AWPacket::findTag(const uint8_t *buffer, uint8_t tag)
{
  const uint8_t *ptr = buffer + headerLength;
  const uint8_t *ep = buffer + getUnsignedPacketLength(buffer);
  while (ptr < ep) {
    uint8_t currentTag = *ptr;
    if (currentTag == tag) {
      return ++ptr; // Skip past tag to the interesting stuff
    }
    else {
      uint16_t len = tagLengths[currentTag];
      if (len)
	ptr += len;
      else {
	++ptr;
	uint16_t payloadLen;
	networkToAvr(&payloadLen, ptr, sizeof(payloadLen));
	ptr += sizeof(payloadLen) + payloadLen;
      }
    }
  }
  return NULL;
}


bool AWPacket::parsePacket(const uint8_t* buffer, size_t bufferLength,
			   void *context,
			   bool (*callback)(uint8_t tag, const uint8_t *data,
					    uint16_t dataLen, void *context),
			   void (*errorCb)(uint8_t tag, void *context))
{
  if (bufferLength < headerLength)
    return false;
  
  if (getPacketLength(buffer) > bufferLength)
    return false;
  
  const uint8_t *p = buffer + headerLength;
  const uint8_t *ep = buffer + getUnsignedPacketLength(buffer);
  while (p < ep) {
    uint8_t tag = *p++;
    if (tag >= sizeof(tagLengths)) {
      // Unknown/bad tag
      if (errorCb != NULL)
	(*errorCb)(tag, context);
      return false;
    }

    uint16_t dataLen;
    if (tagLengths[tag] == 0) {
      // Read the total tag size
      networkToAvr(&dataLen, p, sizeof(dataLen));
      p += sizeof(dataLen);
    }
    else
      dataLen = tagLengths[tag] - 1;

    // Make callback, stop if it returns true
    if (callback != NULL && (*callback)(tag, p, dataLen, context))
      return false;
    p += dataLen;
  }
  return true;
}

bool AWPacket::printTag(uint8_t tag, const uint8_t *data, uint16_t dataLen,
			void *context)
{
  Stream *s = (Stream*)context;
  s->print("Tag ");
  s->print(tag, DEC);
  s->print(":");

  for (uint16_t i = 0; i < dataLen; ++i) {
    s->print(' ');
    if (i >= 16) {
      s->print(" ...");
      break;
    }
    else
      s->print(*data++, HEX);
  }
  s->println();
  return false;
}


void AWPacket::printUnknownTag(uint8_t tag, void *context)
{
  Stream *s = (Stream*)context;
  s->print("Unknown tag: ");
  s->println(tag, DEC);
}

Stream& AWPacket::printPacket(const uint8_t* buffer, uint16_t bufferLength,
			      Stream &s)
{
  // Print header
  s.println();
  if (memcmp(buffer, magic, magicLength) != 0) {
    s.println("Bad magic");
    return s;
  }
  s.print("Version: "); s.println(buffer[versionOffset], DEC);
  s.print("Flags: "); s.println(buffer[flagsOffset], DEC);
  s.print("Packet length: "); s.println(getPacketLength(buffer));
  s.print("Site ID: "); s.println(getSiteId(buffer));
  uint32_t t_s;
  uint16_t t_32768th;
  getTimestamp(buffer, t_s, t_32768th);
  s.print("Timestamp: "); s.print(t_s); s.print(',');s.println(t_32768th);

  
  if (parsePacket(buffer, bufferLength, &s, printTag, printUnknownTag) == false)
    return s; // Failed to parse properly, don't attempt signature
  
  if (isSignedPacket(buffer)) {
    const uint8_t *p = buffer + getUnsignedPacketLength(buffer);
    s.print("Sequence ID: ");
    s.println(*p++, HEX);
    s.print("Retries: ");
    s.println(*p++, HEX);
    s.print("HMAC-MD5:");
    for (uint8_t i = hmacLength; i; --i) {
      s.print(' ');
      s.print(*p++, HEX);
    }
    s.println();
  }
  
  return s;
}


AWPacket::AWPacket(void) : version(1), flags(0),
			   siteId(defaultSiteId),
			   timestamp_s(0),
			   timestamp_32768th(0), 
			   sequenceId(defaultSequenceId),
			   retries(0), keyLen(0), key(NULL)
{
  ;
}

// Construct the packet header and footer information from the binary
// packet
AWPacket::AWPacket(const uint8_t *buffer, uint8_t bufferLength)
  : version(1), flags(0),
    siteId(defaultSiteId),
    timestamp_s(0),
    timestamp_32768th(0),
    sequenceId(defaultSequenceId),
    retries(0), keyLen(0), key(NULL)
{
  if (bufferLength < headerLength) {
    // Serial.println("BUFFER TOO SHORT!");
    return;
  }

  if (memcmp(magic, buffer, magicLength) != 0) {
    // Serial.println("BAD MAGIC!");
    return;
  }

  version = buffer[versionOffset];
  siteId = getSiteId(buffer);
  getTimestamp(buffer, timestamp_s, timestamp_32768th);

  flags = 0;
  if (isSignedPacket(buffer)) {
    flags |= (1 << flagsSignedMessageBit);
    uint16_t ulen = getUnsignedPacketLength(buffer);
    sequenceId = buffer[ulen];
    retries = buffer[ulen + 1];
  }
}
 
bool AWPacket::putHeader(uint8_t* buffer, size_t bufferLength) const
{
  uint8_t *p = buffer; 
  if (headerLength > bufferLength)
    return false;
  for (uint8_t i = 0; i < magicLength; ++i)
    *p++ = magic[i];
  *p++ = version;
  // Write the flags, clear the signed message bit
  *p++ = flags & (uint8_t)(~(1 << flagsSignedMessageBit)); 
  setPacketLength(buffer, headerLength);
  //avrToNetwork(p, &headerLength, sizeof(headerLength));
  // p += 2;
  //avrToNetwork(p, &siteId, sizeof(siteId));
  setSiteId(buffer, siteId);
  //p += sizeof(siteId);
  //avrToNetwork(p, &timestamp, sizeof(timestamp));
  //p += sizeof(timestamp);
  setTimestamp(buffer, timestamp_s, timestamp_32768th);
  return true;
}

bool AWPacket::putMagData(uint8_t* buffer, size_t bufferLength,
			  uint8_t tag, uint8_t resGain, uint32_t data) const
{
  uint16_t len = getPacketLength(buffer);
  if (len + tagLengths[tag] > bufferLength)
    return false;
  uint8_t *p = buffer + len;
  *p++ = tag;
  *p++ = resGain;
  avrToNetwork(p, &data, sizeof(data));
  setPacketLength(buffer,len + tagLengths[tag]);
  return true;
}

bool AWPacket::putData(uint8_t* buffer, size_t bufferLength,
		       uint8_t tag, const void* data) const
{
  uint16_t len = getPacketLength(buffer);
  if (len + tagLengths[tag] > bufferLength)
    return false;
  uint8_t *p = buffer + len;
  *p++ = tag;
  avrToNetwork(p, data, tagLengths[tag]-1);
  setPacketLength(buffer, len + tagLengths[tag]);
  return true;
}

bool AWPacket::putString(uint8_t* buffer, size_t bufferLength,
			 uint8_t tag, const void* str) const
{
  uint16_t packetLen = getPacketLength(buffer);
  uint16_t tagLen = tagLengths[tag];
  uint16_t payloadLen;
  if (tagLen == 0) {
    payloadLen = strlen((const char*)str);
    if (packetLen + payloadLen + 3 > bufferLength)
      return false;
    else
      setPacketLength(buffer, packetLen + payloadLen + 3);
  }
  else {
    payloadLen = tagLen - 1;
    if (packetLen + tagLen > bufferLength)
      return false;
    else
      setPacketLength(buffer, packetLen + tagLen);
  }
  
  uint8_t *p = buffer + packetLen;
  *p++ = tag;
  
  if (tagLen == 0) {
    avrToNetwork(p, &payloadLen, sizeof(payloadLen)); // Write data size
    p += sizeof(payloadLen);
  }
  memcpy(p, str, payloadLen);
  return true;
}

bool AWPacket::putGetFirmwarePage(uint8_t* buffer, size_t bufferLength,
				  const char* version,
				  uint16_t pageNumber) const
{
  uint16_t len = getPacketLength(buffer);
  if (len + tagLengths[tagGetFirmwarePage] > bufferLength)
    return false;
  uint8_t *p = buffer + len;
  *p++ = tagGetFirmwarePage;
  memcpy(p, version, AWPacket::firmwareNameLength);
  p += AWPacket::firmwareNameLength;
  avrToNetwork(p, &pageNumber, sizeof(pageNumber));
  setPacketLength(buffer, len + tagLengths[tagGetFirmwarePage]);
  return true;
}


bool AWPacket::putTimeAdjustment(uint8_t* buffer, size_t bufferLength,
				 int32_t seconds, int16_t fraction) const
{
  uint16_t len = getPacketLength(buffer);
  if (len + tagLengths[tagTimeAdjustment] > bufferLength)
    return false;
  uint8_t *p = buffer + len;
  *p++ = tagTimeAdjustment;
  avrToNetwork(p, &seconds, sizeof(seconds));
  p += sizeof(seconds);
  avrToNetwork(p, &fraction, sizeof(fraction));
  setPacketLength(buffer, len + tagLengths[tagTimeAdjustment]);
  return true;
}

bool AWPacket::putEepromContents(uint8_t* buffer, size_t bufferLength,
				 uint16_t address, uint16_t length) const
{
  uint16_t packetLen = getPacketLength(buffer);
  uint16_t payloadLen = sizeof(address) + length;
  uint16_t newPacketLen = packetLen + sizeOfTag + sizeOfPacketLength
    + payloadLen;
  
  if (newPacketLen > bufferLength)
    return false;
  setPacketLength(buffer, newPacketLen);

  uint8_t *p = buffer + packetLen;
  *p++ = tagEepromContents;
  avrToNetwork(p, &payloadLen, sizeof(payloadLen));
  p += sizeof(payloadLen);
  avrToNetwork(p, &address, sizeof(address));
  p += sizeof(address);
  for (uint16_t i = length; i; --i)
    if (address < EEPROM_HMAC_KEY ||
	address >= (EEPROM_HMAC_KEY + EEPROM_HMAC_KEY_SIZE))
      *p++ = eeprom_read_byte((const uint8_t*)address++);
    else {
      // Do NOT send the key. Send unprogrammed EEPROM values instead.
      *p++ = 0xFF;
      ++address;
    }
  return true;
}


bool AWPacket::putDataArray(uint8_t* buffer, size_t bufferLength,
			    uint8_t tag, uint8_t elemSize, uint8_t numElems,
			    const void* data) const
{
  uint16_t payloadLength = elemSize * numElems;
  uint16_t tagLen = payloadLength + sizeOfTag + sizeOfPacketLength; 
  uint16_t len = getPacketLength(buffer);
  if (len + tagLen > bufferLength)
    return false;
  
  setPacketLength(buffer, len + tagLen);
  uint8_t *p = buffer + len;
  *p++ = tag;
  avrToNetwork(p, &payloadLength, sizeof(payloadLength));
  p += sizeof(payloadLength);

  const uint8_t *dp = (const uint8_t*)data;
  for (uint8_t i = 0; i < numElems; ++i) {
    avrToNetwork(p, dp, elemSize);
    p += elemSize;
    dp += elemSize;
  }
  return true;
}

bool AWPacket::putPadding(uint8_t* buffer, size_t bufferLength,
			  uint16_t paddingLength) const
{
  if (paddingLength == 0)
    return true;
  uint16_t len = getPacketLength(buffer);
  if (len + paddingLength > bufferLength)
    return false;

  setPacketLength(buffer, len + paddingLength);
  uint8_t *p = buffer + len;
  if (paddingLength == 1) {
    *p = tagPaddingByte;
    return true;
  }
  if (paddingLength == 2) {
    *p++ = tagPaddingByte;
    *p++ = tagPaddingByte;
    return true;
  }
  
  *p++ = tagPadding;
  uint16_t payloadLength = paddingLength - 3;
  avrToNetwork(p, &payloadLength, sizeof(payloadLength));
  p += sizeof(payloadLength);
  for (uint16_t i = 0; i < payloadLength; ++i)
    *p++ = 0;
  return true;
}


bool AWPacket::putSignature(uint8_t* buffer, size_t bufferLength,
			    uint16_t blockSize) 
{
  uint16_t unsignedLen = getUnsignedPacketLength(buffer);
  if (blockSize) {
    uint16_t remainder = (unsignedLen + signatureBlockLength) % blockSize;
    if (remainder) {
      // Must add padding
      uint16_t paddingLen = blockSize - remainder;

      // Ensure unsigned
      buffer[flagsOffset] &= ~(1 << flagsSignedMessageBit);
      flags &= ~(1 << flagsSignedMessageBit);
      setPacketLength(buffer, unsignedLen);

      // Add the padding
      if (putPadding(buffer, bufferLength, paddingLen) == false)
	return false;
      unsignedLen += paddingLen;
    }
  }
  
  uint16_t signedLen = unsignedLen + signatureBlockLength;
  setPacketLength(buffer, signedLen);
  
  buffer[flagsOffset] |= (1 << flagsSignedMessageBit);
  flags |= (1 << flagsSignedMessageBit);
  
  
  uint8_t *p = buffer + unsignedLen;

  // sequenceId = getDefaultSequenceId();
  *p++ = sequenceId;
  *p++ = retries;

  // Now add HMAC-MD5
  uint32_t mesgLenBits = (signedLen - hmacLength) * 8;
  uint8_t hmac[HMAC_MD5_BYTES];
  hmac_md5(hmac, key, ((uint16_t)keyLen) * 8, buffer, mesgLenBits);
  uint8_t *hmacPtr = hmac;
  // Take least significant bytes
  hmacPtr += HMAC_MD5_BYTES - hmacLength;
  
  for (uint8_t i = 0; i < hmacLength; ++i)
    *p++ = *hmacPtr++;
  return true;
}


