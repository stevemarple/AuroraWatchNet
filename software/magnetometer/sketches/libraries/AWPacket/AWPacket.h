#ifndef AWPACKET_H
#define AWPACKET_H

#include <stdint.h>
#include <stddef.h>

#include <Stream.h>

/* Class to handle AuroraWatch packets
 */

// Meaning of the epoch flag bit
#define AWPACKET_EPOCH_FLAG_0 1970
#define AWPACKET_EPOCH_FLAG_1 1998

class AWPacket {
public:
	// magic (2), version, flags, packetLength(2), siteId(2) and timestamp(4)
	static const uint8_t headerLength = 14;
	static const uint8_t hmacLength = 8;
	// sequenceId, retries, truncated HMAC-MSD signature (8)
	static const uint8_t signatureBlockLength = 10;
	static const uint8_t versionOffset = 2;
	static const uint8_t flagsOffset = 3;
	static const uint8_t packetLengthOffset = 4;
	static const uint8_t siteIdOffset = 6;
	static const uint8_t timestampOffset = 8;
	static const uint8_t numAxes = 3;
	static const uint8_t magicLength = 2;
	static const char magic[magicLength];
	static const uint16_t tagLengths[31];

	static const uint8_t sizeOfTag = 1;
	static const uint8_t sizeOfPacketLength = 2;
	static const uint8_t sizeOfFirmwarePageNumber = 2;
	static const uint8_t sizeOfCrc = 2;
	static const uint16_t firmwareNameLength = 16;
	// SPM_PAGESIZE must be a multiple of firmwareBlockSize
	static const uint16_t firmwareBlockSize = 128;
	enum flags_t {
		flagsSignedMessageBit = 0,     // Signed message
		flagsSampleTimingErrorBit = 1, // Sampled late
		flagsResponseBit = 2,          // An acknowledgement message
		flagsDataQualityWarningBit = 3,

		// See AWPACKET_EPOCH_FLAG_0 and AWPACKET_EPOCH_FLAG_1 #defines
		flagsEpochBit = 4,
	};

	enum tags_t {
		tagMagDataX = 0,
		tagMagDataY = 1,
		tagMagDataZ = 2,
		tagSensorTemperature = 3,
		tagMCUTemperature = 4,
		tagSupplyVoltage = 5,
		tagTimeAdjustment = 6,
		tagRebootFlags = 7,
		tagSamplingInterval = 8,
		tagPaddingByte = 9,
		tagPadding = 10,
		tagCurrentUnixTime = 11,
		tagReboot =	12,
		tagCurrentFirmware = 13,
		tagUpgradeFirmware = 14,
		tagGetFirmwarePage = 15,
		tagFirmwarePage = 16,
		tagReadEeprom = 17,
		tagEepromContents = 18,
		tagNumSamples = 19,
		tagAllSamples = 20,
		tagMagDataAllX = 21,
		tagMagDataAllY = 22,
		tagMagDataAllZ = 23,
		tagCloudTempAmbient = 24,
		tagCloudTempObject1 = 25,
		tagCloudTempObject2 = 26,
		tagAmbientTemp = 27,
		tagRelHumidity = 28,
		tagGnssStatus = 29,
		tagGnssLocation = 30,
		tagGenData = 31,
	};

	static const uint8_t numSamplesMethodMedian = 0x01; // otherwise mean
	static const uint8_t numSamplesTrimmed = 0x02; // min and max discarded

	static void avrToNetwork(void* dest, const void* src, uint8_t len);
	static inline void networkToAvr(void* dest, const void* src, uint8_t len);
	static inline uint8_t getDefaultSequenceId(void);
	static inline void incrementDefaultSequenceId(void);
	static inline uint16_t getDefaultSiteId(void);
	static inline void setDefaultSiteId(uint16_t s);
	static inline uint8_t getFlags(const uint8_t* buffer);
	static inline bool isSignedPacket(const uint8_t* buffer);
	static inline uint16_t getPacketLength(const uint8_t* buffer);
	static inline uint16_t getUnsignedPacketLength(const uint8_t* buffer);
	static inline void setPacketLength(uint8_t* buffer, uint16_t length);
	static inline uint16_t getSiteId(const uint8_t* buffer);
	static inline void setSiteId(uint8_t* buffer, uint16_t siteId);
	//static inline uint32_t getTimestamp(const uint8_t* buffer);
	static inline void getTimestamp(const uint8_t* buffer,
									uint32_t& t_s, uint16_t& t_32768th);
	//static inline void setTimestamp(uint8_t* buffer, uint32_t timestamp);
	static inline void setTimestamp(uint8_t* buffer, uint32_t seconds,
									uint16_t fraction);
	static inline uint8_t getSequenceId(const uint8_t* buffer);
	static inline uint8_t getRetries(const uint8_t* buffer);

	static bool getCurrentUnixTime(const uint8_t* buffer, int32_t &t);
	static const uint8_t* findTag(const uint8_t *buffer, uint8_t tag);
	static Stream& printPacket(const uint8_t* buffer, uint16_t bufferLength,
							   Stream &s);

	// Parse a packet, calling a function for each tag found, callback is
	// callback(uint8_t tag, uint8_t *data, uint16_t dataLen);
	static bool parsePacket(const uint8_t* buffer, size_t bufferLength,
							void *context,
							bool (*callback)(uint8_t tag, const uint8_t *data,
											 uint16_t dataLen, void *context),
							void (*errorCb)(uint8_t tag, void *context) = NULL);

	static bool printTag(uint8_t tag, const uint8_t *data, uint16_t dataLen,
						 void *context);
	static void printUnknownTag(uint8_t tag, void *context);

	AWPacket(void);
	AWPacket(const uint8_t *buffer, uint8_t bufferLength);

	inline uint16_t getSiteId(void) const;

	inline void setSiteId(uint16_t s);
	//inline void setTimestamp(uint32_t t);
	inline void setTimestamp(uint32_t seconds, uint16_t fraction);
	inline uint8_t getRetries(void);
	inline void incrementRetries(void);
	inline void clearRetries(void);
	inline void setKey(uint8_t *k, uint8_t len);
	inline void setFlagBit(uint8_t flagBit, bool val);

	bool putHeader(uint8_t* buffer, size_t bufferLength) const;
	bool putMagData(uint8_t* buffer, size_t bufferLength,
					uint8_t tag, uint8_t resGain, uint32_t data) const;
	inline bool putDataInt8(uint8_t* buffer, size_t bufferLength,
							uint8_t tag, int8_t data) const;
	inline bool putDataUint8(uint8_t* buffer, size_t bufferLength,
							 uint8_t tag, uint8_t data) const;
	inline bool putDataInt16(uint8_t* buffer, size_t bufferLength,
							 uint8_t tag, int16_t data) const;
	inline bool putDataUint16(uint8_t* buffer, size_t bufferLength,
							  uint8_t tag, uint16_t data) const;
	inline bool putDataInt32(uint8_t* buffer, size_t bufferLength,
							 uint8_t tag, int32_t data) const;
	inline bool putDataUint32(uint8_t* buffer, size_t bufferLength,
							  uint8_t tag, uint32_t data) const;
	bool putData(uint8_t* buffer, size_t bufferLength,
				 uint8_t tag, const void* data) const;
	bool putString(uint8_t* buffer, size_t bufferLength,
				   uint8_t tag, const void* str) const;

	bool putGetFirmwarePage(uint8_t* buffer, size_t bufferLength,
							const char* version, uint16_t pageNumber) const;
	bool putTimeData(uint8_t* buffer, size_t bufferLength, uint8_t tag,
					 int32_t seconds, int16_t fraction) const;
	bool putTimeAdjustment(uint8_t* buffer, size_t bufferLength,
						   int32_t seconds, int16_t fraction) const;
	bool putEepromContents(uint8_t* buffer, size_t bufferLength,
						   uint16_t address, uint16_t length) const;

	bool putGnssStatus(uint8_t* buffer, size_t bufferLength,
					   int32_t timestamp, bool isValid, char navSystem,
					   uint8_t numSat, uint8_t hdop) const;
	bool putDataArray(uint8_t* buffer, size_t bufferLength,
					  uint8_t tag, uint8_t elemSize, uint8_t numElems,
					  const void* data) const;
	bool putAdcData(uint8_t* buffer, size_t bufferLength,
					uint8_t tag, uint8_t resGain, uint8_t numElems,
					const int32_t* data) const;
	bool putPadding(uint8_t* buffer, size_t bufferLength,
					uint16_t paddingLength) const;
	bool putSignature(uint8_t* buffer, size_t bufferLength,
					  uint16_t blockSize = 0);

	bool padToBlockSize(uint8_t* buffer, size_t bufferLength, uint16_t blockSize);

private:
	// In normal operation the timestamp should be sufficient to prevent
	// replay attacks. However, if the time has been adjusted backwards
	// there is a possibility that an attacker could shortly afterwards
	// replay the same acknowledgement which led to the time being
	// adjusted. A change in the sequenceId prevents the acknowledgement
	// from being replayed.
	static uint8_t defaultSequenceId;
	static uint16_t defaultSiteId;
	uint8_t version;
	uint8_t flags;
	uint16_t siteId;
	uint32_t timestamp_s;
	uint16_t timestamp_32768th;
	uint8_t sequenceId;
	uint8_t retries;

	uint8_t keyLen; // In bytes
	uint8_t *key;

};

void AWPacket::networkToAvr(void* dest, const void* src, uint8_t len)
{
	avrToNetwork(dest, src, len);
}

uint8_t AWPacket::getDefaultSequenceId(void)
{
	return defaultSequenceId;
}

void AWPacket::incrementDefaultSequenceId(void)
{
	++defaultSequenceId;
}

uint16_t AWPacket::getDefaultSiteId(void)
{
	return defaultSiteId;
}

void AWPacket::setDefaultSiteId(uint16_t s)
{
	defaultSiteId = s;
}

uint8_t AWPacket::getFlags(const uint8_t* buffer)
{
	return buffer[flagsOffset];
}

bool AWPacket::isSignedPacket(const uint8_t* buffer)
{
	return getFlags(buffer) & (1 << flagsSignedMessageBit);
}

uint16_t AWPacket::getPacketLength(const uint8_t* buffer)
{
	return (((uint16_t)buffer[packetLengthOffset]) << 8) + buffer[packetLengthOffset+1];
}

uint16_t AWPacket::getUnsignedPacketLength(const uint8_t* buffer)
{
	uint16_t p = getPacketLength(buffer);
	if (isSignedPacket(buffer))
		p -= signatureBlockLength;
	return p;
}

void AWPacket::setPacketLength(uint8_t* buffer, uint16_t length)
{
	buffer[packetLengthOffset] = length >> 8;
	buffer[packetLengthOffset+1] = (uint8_t)(length & (uint8_t)0xff);
}

uint16_t AWPacket::getSiteId(const uint8_t* buffer)
{
	return (((uint16_t)buffer[siteIdOffset]) << 8) + buffer[siteIdOffset+1];
}

void AWPacket::setSiteId(uint8_t* buffer, uint16_t siteId)
{
	buffer[siteIdOffset] = siteId >> 8;
	buffer[siteIdOffset+1] = (uint8_t)(siteId & (uint8_t)0xff);
}

// uint32_t AWPacket::getTimestamp(const uint8_t* buffer)
// {
//   uint32_t t = 0;
//   networkToAvr(&t, buffer + timestampOffset, sizeof(t));
//   return t;
// }

void AWPacket::getTimestamp(const uint8_t* buffer,
							uint32_t& t_s, uint16_t& t_32768th)
{
	networkToAvr(&t_s, buffer + timestampOffset, sizeof(t_s));
	networkToAvr(&t_32768th, buffer + timestampOffset + sizeof(t_s),
				 sizeof(t_32768th));
}

void AWPacket::setTimestamp(uint8_t* buffer, uint32_t t_s, uint16_t t_32768th)
{
	avrToNetwork(buffer + timestampOffset, &t_s, sizeof(t_s));
	avrToNetwork(buffer + timestampOffset + sizeof(t_s),
				 &t_32768th, sizeof(t_32768th));
}


uint8_t AWPacket::getSequenceId(const uint8_t* buffer)
{
	return buffer[getPacketLength(buffer) - signatureBlockLength];
}

uint8_t AWPacket::getRetries(const uint8_t* buffer)
{
	return buffer[getPacketLength(buffer) - signatureBlockLength + 1];
}

uint16_t AWPacket::getSiteId(void) const
{
	return siteId;
}

void AWPacket::setSiteId(uint16_t s)
{
	siteId = s;
}

// void AWPacket::setTimestamp(uint32_t t)
// {
//   timestamp_s = t;
//   timestamp_32768th = 0;
// }

void AWPacket::setTimestamp(uint32_t seconds, uint16_t fraction)
{
	timestamp_s = seconds;
	timestamp_32768th = fraction;
}

uint8_t AWPacket::getRetries(void)
{
	return retries;
}

void AWPacket::incrementRetries(void)
{
	++retries;
}

void AWPacket::clearRetries(void)
{
	retries = 0;
}

void AWPacket::setKey(uint8_t *k, uint8_t len)
{
	key = k;
	keyLen = len;
}

void AWPacket::setFlagBit(uint8_t flagBit, bool val)
{
	if (flagBit != flagsSignedMessageBit) {
		if (val)
			flags |= (1 << flagBit);
		else
			flags &= ~(1<< flagBit);
	}
}

bool AWPacket::putDataInt8(uint8_t* buffer, size_t bufferLength,
						   uint8_t tag, int8_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}

bool AWPacket::putDataUint8(uint8_t* buffer, size_t bufferLength,
							uint8_t tag, uint8_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}

bool AWPacket::putDataInt16(uint8_t* buffer, size_t bufferLength,
							uint8_t tag, int16_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}

bool AWPacket::putDataUint16(uint8_t* buffer, size_t bufferLength,
							 uint8_t tag, uint16_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}

bool AWPacket::putDataInt32(uint8_t* buffer, size_t bufferLength,
							uint8_t tag, int32_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}

bool AWPacket::putDataUint32(uint8_t* buffer, size_t bufferLength,
							 uint8_t tag, uint32_t data) const
{
	return putData(buffer, bufferLength, tag, &data);
}


#endif
