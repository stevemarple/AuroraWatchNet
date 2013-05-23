#ifndef RFM12B_RADIO_H
#define RFM12B_RADIO_H

#include <CommsInterface.h>
#include <RF12_Stream.h>

class RFM12B_Radio : public CommsInterface {
public:
  RFM12B_Radio(RF12_Stream &s);
  bool begin(uint8_t cs, uint8_t irqPin, uint8_t irqNum,
	     uint8_t id, uint8_t band, uint16_t channel, uint8_t group=0xD4);
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

private:
  RF12_Stream &stream;

};

#endif
