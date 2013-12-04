#ifndef W5100_UDP_H
#define W5100_UDP_H

#include <SPI.h>
#include <Ethernet.h>
//#include <EthernetUDP.h>
#include <CommsInterface.h>
// #include <AsyncDelay.h>

class W5100_UDP : public CommsInterface
{
public:

  W5100_UDP(void);
  bool begin(uint8_t *macAddress,
	     IPAddress localIP, uint16_t localPort_,
	     IPAddress remoteIP_, uint16_t remotePort_,
	     uint8_t ssPin, uint8_t sdSsPin = 255);
  
  // Overload the pure virtual functions
  virtual int available(void);
  virtual int peek(void);
  virtual int read(void);
  virtual void flush(void);
  virtual size_t write(uint8_t);
  using Print::write; // Apull in write(str) and write(buf, size) from Print
  // size_t write(const char *str) { return write((const uint8_t *)str, strlen(str)); }
  //size_t write(const char *str);
  //virtual size_t write(const uint8_t *buffer, size_t size);
    
  
  virtual bool powerOn(void);
  virtual bool powerOff(void);
  virtual bool reset(void);
  virtual void poll(void);

  virtual void messageStart(void);
  virtual void messageEnd(void);
  virtual size_t messageWriteSize(void);
  virtual void checkForResponse(void);

private:
  // Stream &stream;
  uint8_t ssPin;
  uint8_t sdSsPin;
  EthernetUDP udp;
  uint16_t localPort;
  uint16_t remotePort;
  IPAddress localIP;
  IPAddress remoteIP;
};


#endif
