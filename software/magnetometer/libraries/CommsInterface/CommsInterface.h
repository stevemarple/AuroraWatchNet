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
};

#endif
