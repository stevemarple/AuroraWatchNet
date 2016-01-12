#include <avr/eeprom.h>
#include <avr/wdt.h>
#include <ctype.h>

#include <Streaming.h>
#include <WIZnet_UDP.h>
#include <AwEeprom.h>

extern Stream& console;

WIZnet_UDP::WIZnet_UDP(void) : ssPin(255), sdSsPin(255)
{
  ;
}

int WIZnet_UDP::available(void)
{
  return udp.available();
}

int WIZnet_UDP::peek(void)
{
  return udp.peek();
}

int WIZnet_UDP::read(void)
{
  return udp.read();
}

void WIZnet_UDP::flush(void)
{
  ; // return udp.flush();
}

size_t WIZnet_UDP::write(uint8_t c)
{
  return udp.write(c);
}

// size_t WIZnet_UDP::write(const char* str)
// {
//   return udp.write((const uint8_t *)str, strlen(str));
// }

// size_t WIZnet_UDP::write(const uint8_t *buffer, size_t size)
// {
//   return udp.write(buffer, size);
// }

bool WIZnet_UDP::powerOn(void)
{
  return true;
}

bool WIZnet_UDP::powerOff(void)
{
  return true;
}

bool WIZnet_UDP::reset(void)
{
  return true;
}


bool WIZnet_UDP::begin(uint8_t *macAddress __attribute__ ((unused)),
		      IPAddress localIP_, uint16_t localPort_, 
		      IPAddress remoteIP_, uint16_t remotePort_,
		      uint8_t ssPin_, uint8_t sdSsPin_)
{
  ssPin = ssPin_;
  sdSsPin = sdSsPin_;
  localIP = localIP_;
  localPort = localPort_;
  remoteIP = remoteIP_;
  remotePort = remotePort_;

  pinMode(ssPin, OUTPUT);
  digitalWrite(ssPin, HIGH);

  if (sdSsPin != 255) {
    pinMode(sdSsPin, OUTPUT);
    digitalWrite(sdSsPin, HIGH); // Keep SD card inactive
  }

  udp.begin(localPort_);
  return true;
}

void WIZnet_UDP::poll(void)
{
  ; // No polling needed
}

void WIZnet_UDP::messageStart(void)
{
  udp.beginPacket(remoteIP, remotePort);
}

void WIZnet_UDP::messageEnd(void)
{
  udp.endPacket();
}

size_t WIZnet_UDP::messageWriteSize(void)
{
  return 0;
}

void WIZnet_UDP::checkForResponse(void)
{
  udp.parsePacket();
}

