#include <stdint.h>
#include <string.h>
#include <avr/eeprom.h>
//#include <avr/wdt.h>

#include "xbootapi.h"

extern "C" {
#include "hmac-md5.h"
}


#include <Streaming.h>
#include <AwEeprom.h>
#include <AWPacket.h>
#include "CommsHandler.h"

extern Stream& console;
extern uint8_t verbosity;
extern uint16_t commsBlockSize;

static const char* strNoError = "no error";
static const char* strBufferTooSmall = "buffer too small";
static const char* strResponseTimeout = "reponse timeout";


const char* CommsHandler::errorMessages[4] = {
	strNoError,
	strBufferTooSmall,
	strResponseTimeout,
	//strNotReady,
	// PSTR("no error"),
	// PSTR("buffer too small"),
	// PSTR("reponse timeout"),
	// PSTR("not ready"),
};


CommsHandler::CommsHandler(void* msgBuffer, uint16_t msgBufferLen,
						   void* stackBuffer, uint16_t stackBufferLen) :
	errno(errorNoError),
	messageBufferLen(msgBufferLen),
	messageBuffer((uint8_t*)msgBuffer),
	messageLen(0),
	bytesSent(0),
	responseLen(0),
	responsePacketLen(0),
	state(stateWaitingForMessages),
	commsPtr(NULL),
	stack(stackBuffer, stackBufferLen),
	keyLen(0),
	key(NULL)
{
	;
}


void CommsHandler::addMessage(void *msg, uint16_t len)
{
	if (len > messageBufferLen) {
		console.println(strBufferTooSmall);
		errno = errorBufferTooSmall;
	}

	stack.write(msg, len);
	errno = errorNoError;

	// No point in waiting in the timed out state when a new message has
	// arrived; attempt delivery
	if (state == stateTimedOut)
		state = stateWaitingForMessages;
}

int CommsHandler::process(uint8_t *responseBuffer, uint16_t responseBufferLen)
{
	if (commsPtr == NULL) {
		errno = errorCommsNotSet;
		return false;
	}

	bool validResponse = false;
	errno = errorNoError;

	commsPtr->poll();

	switch (state) {
	case stateWaitingForMessages:
		if (!stack.isEmpty()) {
			messageLen = stack.read(messageBuffer, messageBufferLen);
			if (messageLen) {
				bytesSent = 0;
				state = statePowerUp;

				if (commsBlockSize) {
					// Append null characters to fill a complete block
					uint8_t remainder = messageLen % commsBlockSize;
					if (remainder) {
						uint16_t newLen = messageLen + (commsBlockSize - remainder);
						if (newLen <= messageBufferLen) {
							memset(messageBuffer + messageLen, 0, commsBlockSize - remainder);
							messageLen = newLen;
						}
					}
				}
			}
		}
		break;

	case statePowerUp:
		if (commsPtr->powerOn())
			state = sendingData;
		break;

	case sendingData:
		// Send each byte individually. At present
		// HardwareSerial.write() waits until the buffer has room but
		// in future it might return immediately with a return value of
		// zero.
		if (bytesSent == 0 && verbosity == 10)
			AWPacket::printPacket(messageBuffer, messageLen, console);

		if (bytesSent == 0)
			commsPtr->messageStart();

		{
			size_t bytesToSend = commsPtr->messageWriteSize();
			if (bytesToSend == 0)
				bytesToSend = messageLen;
			bytesSent += commsPtr->write(messageBuffer + bytesSent, bytesToSend);
		}

		if (bytesSent == messageLen) {
			commsPtr->messageEnd();
			responseLen = 0;
			responseTimeout.start(responseTimeout_ms, AsyncDelay::MILLIS);
			responsePacketLen = 65535; // Use maximum value until we know
			state = stateWaitingForResponse;
		}
		break;

	case stateWaitingForResponse:
		if (responseTimeout.isExpired()) {
			console.println(strResponseTimeout);
			errno = errorResponseTimeout;

			// Put message back into queue if retries not exceeded
			AWPacket failedPacket(messageBuffer, messageLen);
			if (failedPacket.getRetries() < maxRetries) {
				failedPacket.incrementRetries();
				// Update the signature for new retries
				failedPacket.setKey(key, keyLen);
				failedPacket.putSignature(messageBuffer, messageBufferLen);

				messageLen = 0;
				stack.write(messageBuffer, AWPacket::getPacketLength(messageBuffer));
			}
			else {
				console.print(F("Too many retries: "));
				AWPacket::printPacket(messageBuffer, messageBufferLen, console);
			}
			state = stateTimedOut;
			break;
		}

		commsPtr->checkForResponse();
		if (int avail = commsPtr->available()) {
			if (responseLen >= responseBufferLen) {
				errno = errorBufferTooSmall;
				messageLen = 0;
				state = stateWaitingForMessages;
				break;
			}

			for (int i = avail; i; --i) {
				uint8_t b = commsPtr->read();
				responseBuffer[responseLen++] = b;
			}

			if (validateResponse(responseBuffer, responseLen)) {
				// The response in the buffer is valid, but is it a response
				// to our last message?
				int32_t messageSeconds, responseSeconds;
				int16_t messageFraction, responseFraction;
				AWPacket::getTimestamp(messageBuffer, messageSeconds,
									   messageFraction);
				AWPacket::getTimestamp(responseBuffer, responseSeconds,
									   responseFraction);
				if ((AWPacket::getSiteId(responseBuffer)
					 == AWPacket::getSiteId(messageBuffer)) &&
					(messageSeconds == responseSeconds) &&
					(messageFraction == responseFraction) &&
					(AWPacket::getSequenceId(responseBuffer)
					 == AWPacket::getSequenceId(messageBuffer)) &&
					(AWPacket::getRetries(responseBuffer)
					 == AWPacket::getRetries(messageBuffer))) {
					// Valid response found
					validResponse = true;
					messageLen = 0;
					state = stateWaitingForMessages;
				}
				else {
					// Need another response
					__FlashStringHelper* hashes =
						(__FlashStringHelper*)PSTR("######################");
					console.println(hashes);
					console.println(F("Packet valid but incorrect response"));
					AWPacket::printPacket(responseBuffer, responseLen, console);
					console.println(hashes);

					responseLen = 0;
					responsePacketLen = 65535; // Use maximum value until we know
				}
			}
		}
		break;

	case stateTimedOut:
		// Stuck here until a new message is added
		break;
	}

	return validResponse;
}


//TODO: validate the response against the last transmitted message
// Validate the contents of the buffer
// responseLen: current length of buffer
// b: newly received byte
bool CommsHandler::validateResponse(uint8_t *responseBuffer,
									uint16_t &responseLen) const
{
	// Don't shift the characters in the buffer unless the current
	// packet is not valid and a potentially valid has been be
	// found. ('Potentially' valid because the message may be
	// incomplete, but at present passes all tests for a valid message).
	uint8_t *tmpBuf = responseBuffer;
	uint16_t len = responseLen;
	bool completeMessage = false;

	while (len) {
		bool valid = true;

		// Check magic
		for (uint8_t i = 0; i < (len >= AWPacket::magicLength ? AWPacket::magicLength : len); ++i) {
			if (tmpBuf[i] != AWPacket::magic[i]) {
				valid = false;
				break;
			}
		}

		if (len < AWPacket::magicLength)
			break;

		if (valid && len > AWPacket::flagsOffset &&
			!(AWPacket::isSignedPacket(tmpBuf)))
			// tmpBuf[AWPacket::flagsOffset] & (1 << AWPacket::flagsSignedMessageBit)))
			valid = false; // Must be signed

		uint16_t packetLength = 0;
		if (valid && len >= (AWPacket::packetLengthOffset + sizeof(packetLength))) {
			packetLength = AWPacket::getPacketLength(tmpBuf);
			if (len >= packetLength) {
				completeMessage = true;
				// Compute HMAC-MD5
				uint32_t mesgLenBits = (packetLength - AWPacket::hmacLength) * 8;
				uint8_t hmac[HMAC_MD5_BYTES];
				hmac_md5(hmac, key, ((uint16_t)keyLen) * 8, tmpBuf, mesgLenBits);
				uint8_t *calcHmacPtr = hmac; // Calculated HMAC
				uint8_t *respHmacPtr = tmpBuf + (len - AWPacket::hmacLength);

				// Take least significant bytes
				calcHmacPtr += HMAC_MD5_BYTES - AWPacket::hmacLength;

				// Compare. To prevent timing attacks don't stop the
				// comparison early and aim to have all outcomes take the
				// same time.
				for (uint8_t i = 0; i < AWPacket::hmacLength; ++i)
					valid = ((*calcHmacPtr++ == *respHmacPtr++) & valid);
			}
		}


		// All tests done
		if (valid) {
			if (len != responseLen) {
				// Start point is not the first character in the buffer
				memmove(responseBuffer, tmpBuf, len);
			}
			return (completeMessage && valid);
		}
		else {
			// Try next byte in the buffer but without shifting the data
			// each time
			++tmpBuf;
			--len;
		}
	}
	// No valid message found
	return false;
}
