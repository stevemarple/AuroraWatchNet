#ifndef XRF_RADIO_H
#define XRF_RADIO_H

#include <CommsInterface.h>
#include <AsyncDelay.h>

class XRF_Radio : public CommsInterface
{
public:
  static const int resetDelay_us = 250;

  XRF_Radio(Stream &s);
  bool begin(uint8_t xrfSleepPin, uint8_t xrfOnPin, uint8_t xrfResetPin);
  
  // Overload the pure virtual functions
  virtual int available(void);
  virtual int peek(void);
  virtual int read(void);
  virtual void flush(void);
  virtual size_t write(uint8_t);
  using Print::write; // pull in write(str) and write(buf, size) from Print
  
  virtual bool powerOn(void);
  virtual bool powerOff(void);
  virtual bool reset(void);
  virtual void poll(void);

  virtual void messageStart(void);
  virtual void messageEnd(void);
  virtual size_t messageWriteSize(void);
  virtual void checkForResponse(void);
  
private:
  Stream &stream;
  uint8_t sleepPin;
  uint8_t onPin;
  uint8_t resetPin;

  bool poweringUp;
  bool resetting;
  AsyncDelay resetTimer;

};

#endif
