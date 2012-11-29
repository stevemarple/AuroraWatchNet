#include <avr/eeprom.h>
#include <stdint.h>
#include <string.h>

extern "C" {
#include "hmac-md5.h"
}


#include <Streaming.h>
#include <AWPacket.h>
#include <AwEeprom.h>
#include "CommsHandler.h"

extern Stream& console;
static const char* strNoError = "no error";
static const char* strBufferTooSmall = "buffer too small";
static const char* strResponseTimeout = "reponse timeout";
//static const char* strNotReady = "not ready";
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

bool CommsHandler::xrfPowerOn(void)
{
  // if (xrfPoweringUp && powerUpTimer.isExpired())
  if (xrfPoweringUp && digitalRead(xrfOnPin))
    return true;

  if (xrfPoweringUp == false) {
    digitalWrite(xrfSleepPin, LOW);
    // powerUpTimer.start(powerUpDelay_ms, AsyncDelay::MILLIS);
    xrfPoweringUp = true;
  }
  return false;
}

bool CommsHandler::xrfPowerOff(void)
{
  digitalWrite(xrfSleepPin, HIGH);
  xrfPoweringUp = false;
  return true;
}

bool CommsHandler::xrfReset(void)
{
  if (xrfResetPin == 255)
    return true; // Reset pin not set, report reset done
  
  if (xrfResetting && resetTimer.isExpired()) {
    // Timer expired, make reset pin inactive and check that XRF
    // indicates it is ready.
    digitalWrite(xrfResetPin, HIGH);
    if (digitalRead(xrfOnPin) == HIGH) {
      xrfResetting = false;
      return true;
    }
  }
  
  if (xrfResetting == false) {
    // Begin reset cycle. Make reset pin active for a short while.
    digitalWrite(xrfResetPin, LOW);
    resetTimer.start(resetDelay_us, AsyncDelay::MICROS);
    xrfResetting = true;
    xrfPoweringUp = false;
  }
  return false;
}

void CommsHandler::setup(uint8_t sleepPin, uint8_t onPin, uint8_t resetPin)
{
  AsyncDelay timeout;
  xrfSleepPin = sleepPin;
  xrfOnPin = onPin;
  xrfResetPin = resetPin;
  
  if (xrfSleepPin != 255) {
    pinMode(xrfSleepPin, OUTPUT);
    //digitalWrite(xrfSleepPin, HIGH); // active low, in sleep mode 2
    digitalWrite(xrfSleepPin, LOW); // low = on, in sleep mode 2
  }

  if (xrfResetPin != 255) {
    pinMode(xrfResetPin, OUTPUT);
    digitalWrite(xrfResetPin, HIGH); // active low

    timeout.start(3000, AsyncDelay::MILLIS);
    while (1) {
      if (xrfReset())
	break;
      if (timeout.isExpired()) {
	console << "Timeout waiting for XRF to reset\n";
	break;
      }
    }
    // do {
    //   ;
    // } while (xrfReset() != true);
  }

  if (xrfOnPin != 255) { 
    pinMode(xrfOnPin, INPUT);
    timeout.start(3000, AsyncDelay::MILLIS);
    while (1) {
      if (xrfPowerOn() == true)
	break;
      if (timeout.isExpired()) {
	console << "Timeout waiting for XRF to power on\n";
	break;
      }
    }
    // do {
    //   ;
    // } while (xrfPowerOn() != true);
  }
  
  while (xrf.available())
    xrf.read();
  
  delay(1050);
  xrf.print("+++");
  //xrf.flush();
  delay(1050);
  // xrf << "ATRE\r";
  xrf << "ATSM 2\r"; // Sleep mode
  uint8_t channelNum = eeprom_read_byte((const uint8_t*)EEPROM_RADIO_CHANNEL);
  if (channelNum != 0xFF) {
    xrf << "ATCN " << int(channelNum) << '\r';
    console << "Channel number: " << channelNum << endl;
  }
  xrf << "ATAC\r"    // Apply changes
      << "ATDN\r";   // Done
  delay(300);
  while (xrf.available()) {
    xrf.read(); //Serial.print(xrf.read());
  }
  
}

void CommsHandler::addMessage(void *ptr, uint16_t len)
{
  stack.write(ptr, len);
  errno = errorNoError;

  // No point in waiting in the timed out state when a new message has
  // arrived; attempt delivery
  if (state == stateTimedOut)
    state = stateWaitingForMessages;
}

int CommsHandler::process(uint8_t *responseBuffer, uint16_t responseBufferLen)
{
  bool validResponse = false;
  errno = errorNoError;
  switch (state) {
  case stateWaitingForMessages:
    if (!stack.isEmpty()) {
      messageLen = stack.read(messageBuffer, messageBufferLen);
      if (messageLen) {
	bytesSent = 0;
	state = statePowerUp;

	// Append null characters to fill a complete block
	const uint8_t xrfBlockSize = 12;
	uint8_t remainder = messageLen % xrfBlockSize;
	if (remainder) {
	  uint16_t newLen = messageLen + (xrfBlockSize - remainder);
	  if (newLen <= messageBufferLen) {
	    memset(messageBuffer + messageLen, 0, xrfBlockSize - remainder);
	    messageLen = newLen;
	  }
	}
      }
    }
    break;

  case statePowerUp:
    if (xrfPowerOn())
      state = sendingData;
    break;

  case sendingData:
    // Send each byte individually. At present
    // HardwareSerial.write() waits until the buffer has room but
    // in future it might return immediately with a return value of
    // zero.
    if (xrf.write(messageBuffer[bytesSent])) {
      // Serial.print(messageBuffer[bytesSent], HEX);
      ++bytesSent;
    }
    if (bytesSent == messageLen) {
      responseLen = 0;
      responseTimeout.start(responseTimeout_ms, AsyncDelay::MILLIS);
      responsePacketLen = 65535; // Use maximum value until we know
      state = stateWaitingForResponse;
    }
    break;

  case stateWaitingForResponse:
    if (responseTimeout.isExpired()) {
      Serial.println("Message timeout");
      
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
	Serial.print("Too many retries: ");
	AWPacket::printPacket(messageBuffer, messageBufferLen, Serial);
      }
      state = stateTimedOut;
      break;
    }

    if (xrf.available()) {
      if (responseLen >= responseBufferLen) {
	errno = errorBufferTooSmall;
	messageLen = 0;
	state = stateWaitingForMessages;
	break;
      }

      uint8_t b = xrf.read();
      responseBuffer[responseLen++] = b;

      if (validateResponse(responseBuffer, responseLen)) {
	// The response in the buffer is valid, but is it a response
	// to our last message?
	uint32_t messageSeconds, responseSeconds;
	uint16_t messageFraction, responseFraction;
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
	  Serial.println("######################");
	  Serial.println("Packet valid but incorrect response");
	  AWPacket::printPacket(responseBuffer, responseLen, Serial);
	  Serial.println("######################");
	  
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
	  valid = ((*calcHmacPtr++ == *respHmacPtr++) && valid);
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
