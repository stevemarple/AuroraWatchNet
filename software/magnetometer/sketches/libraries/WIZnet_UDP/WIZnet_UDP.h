#ifndef WIZNET_UDP_H
#define WIZNET_UDP_H

#if defined (COMMS_W5100) && defined (COMMS_W5500)
#error Cannot build for both WIZnet W5100 and W5500 simultaneously
#endif

#ifdef COMMS_W5100
#include <EthernetUdp.h>
#endif

#ifdef COMMS_W5500
#include <EthernetUdp2.h>
#endif

#include <CommsInterface.h>

class WIZnet_UDP : public CommsInterface
{
public:
  WIZnet_UDP(void);
  bool begin(uint8_t *macAddress,
	     IPAddress localIP, uint16_t localPort_,
	     IPAddress remoteIP_, uint16_t remotePort_,
	     uint8_t ssPin, uint8_t sdSsPin = 255);

  inline const IPAddress& getRemoteIP(void) const;
  
  // Overload the pure virtual functions
  virtual int available(void);
  virtual int peek(void);
  virtual int read(void);
  virtual void flush(void);
  virtual size_t write(uint8_t);
  using Print::write; // Pull in write(str) and write(buf, size) from Print
  
  virtual bool powerOn(void);
  virtual bool powerOff(void);
  virtual bool reset(void);
  virtual void poll(void);

  virtual void messageStart(void);
  virtual void messageEnd(void);
  virtual size_t messageWriteSize(void);
  virtual void checkForResponse(void);

private:
  uint8_t ssPin;
  uint8_t sdSsPin;
  EthernetUDP udp;
  uint16_t localPort;
  uint16_t remotePort;
  IPAddress localIP;
  IPAddress remoteIP;
};

const IPAddress& WIZnet_UDP::getRemoteIP(void) const {
  return remoteIP;
}


#endif
