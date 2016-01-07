#ifndef COMMSINTERFACE_H
#define COMMSINTERFACE_H

#include "Stream.h"

/*
 * Common interface for communications
 */
class CommsInterface : public Stream {
public:
  // Return true to indicate when done
  virtual bool powerOn(void) = 0;
  virtual bool powerOff(void) = 0;
  virtual bool reset(void) = 0;

  // Some interfaces require regular prodding
  virtual void poll(void) = 0;

  // Some interfaces need to be told start and end of message (eg for
  // UDP packets)
  virtual void messageStart(void) = 0;
  virtual void messageEnd(void) = 0;

  // Indicate how many bytes should be sent to the stream at once. zero
  // means send everything.
  virtual size_t messageWriteSize(void) = 0;
  virtual void checkForResponse(void) = 0;
  
};

#endif
