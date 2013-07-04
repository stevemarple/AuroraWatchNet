#ifndef COMMSHANDLER_H
#define COMMSHANDLER_H

#include <AsyncDelay.h>
#include <CircularStack.h>
#include <CommsInterface.h>

class CommsHandler {
public:
  enum error_t {
    errorNoError = 0,
    errorBufferTooSmall,
    errorResponseTimeout,
    errorNotReady,
    errorCommsNotSet,
  };

  static const uint8_t maxRetries = 2;
  static const char* errorMessages[4];
  
  inline CommsHandler(void* stackBuffer, uint16_t stackBufferLen);

  // Returns true when ready to use. 
  // bool xrfPowerOn(void);

  // Returns true when powered off
  // bool xrfPowerOff(void);

  // Returns true when reset completed
  // bool xrfReset(void);

  void setup(uint8_t sleepPin, uint8_t onPin, uint8_t resetPin); 

  inline void setKey(uint8_t *k, uint8_t len);
  void addMessage(void *buffer, uint16_t len);

  // Returns number of bytes written to buffer. Powers up XRF when
  // needed, does not power off.
  int process(uint8_t *responseBuffer, uint16_t responseBufferLen);
  
  bool validateResponse(uint8_t *responseBuffer, uint16_t &responseLen) const;

  
  inline bool isFinished(void) const;
  inline bool isWaitingForMessages(void) const;
  // inline bool isXrfPowered(void) const;
  inline error_t getError(void) const;

  inline uint16_t getBytesSent(void) const;
  inline uint8_t getState(void) const;
  inline CommsInterface* getCommsInterface(void) const;
  inline void setCommsInterface(CommsInterface* cip);
  
private:
  enum state_t {
    stateWaitingForMessages = 0,
    statePowerUp = 1,
    sendingData = 2,
    stateWaitingForResponse = 3,
    // Used when a message didn't get a response
    stateTimedOut = 4,
  };

  static const uint16_t messageBufferLen = 260;
  // static const int powerUpDelay_ms = 250;
  // static const int resetDelay_us = 250;
  static const int responseTimeout_ms = 2000;
  
  uint8_t xrfSleepPin;
  uint8_t xrfOnPin;
  uint8_t xrfResetPin;
  bool xrfPoweringUp;
  bool xrfResetting;

  error_t errno;
  uint8_t messageBuffer[messageBufferLen];
  uint16_t messageLen;
  uint16_t bytesSent;
  uint16_t responseLen; // Length of the response so far
  uint16_t responsePacketLen; // Length of the packet, read from incoming data
  state_t state;
  CommsInterface* commsPtr;
  AsyncDelay responseTimeout;
  AsyncDelay resetTimer;
  CircularStackBlock stack;
  uint8_t keyLen; // In bytes
  uint8_t *key;

};


CommsHandler::CommsHandler(void* stackBuffer, uint16_t stackBufferLen) :
  xrfPoweringUp(false),
  xrfResetting(false),
  messageLen(0),
  state(stateWaitingForMessages),
  commsPtr(NULL),
  stack(stackBuffer, stackBufferLen)
{
  ;
}

void CommsHandler::setKey(uint8_t *k, uint8_t len)
{
  key = k;
  keyLen = len;
}

bool CommsHandler::isFinished(void) const
{
  return ((stack.isEmpty() && state == stateWaitingForMessages) ||
	  state == stateTimedOut);
}

bool CommsHandler::isWaitingForMessages(void) const
{
  return (stack.isEmpty() && state == stateWaitingForMessages);
}

// bool CommsHandler::isXrfPowered(void) const
// {
//   return xrfPoweringUp;
// }

CommsHandler::error_t CommsHandler::getError(void) const
{
  return errno;
}

uint16_t CommsHandler::getBytesSent(void) const
{
  return bytesSent;
}

uint8_t CommsHandler::getState(void) const
{
  return state;
}

CommsInterface* CommsHandler::getCommsInterface(void) const
{
  return commsPtr;
}

void CommsHandler::setCommsInterface(CommsInterface* cip)
{
  commsPtr = cip;
}
  

#endif
