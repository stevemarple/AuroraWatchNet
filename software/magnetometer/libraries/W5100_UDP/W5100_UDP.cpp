#include <avr/eeprom.h>
#include <avr/wdt.h>
#include <ctype.h>

#include <Streaming.h>
#include <W5100_UDP.h>
#include <AwEeprom.h>

extern Stream& console;

W5100_UDP::W5100_UDP(void) : ssPin(255), sdSsPin(255)
{
  ;
}

int W5100_UDP::available(void)
{
  return udp.available();
}

int W5100_UDP::peek(void)
{
  return udp.peek();
}

int W5100_UDP::read(void)
{
  return udp.read();
}

void W5100_UDP::flush(void)
{
  ; // return udp.flush();
}

size_t W5100_UDP::write(uint8_t c)
{
  return udp.write(c);
}

// size_t W5100_UDP::write(const char* str)
// {
//   return udp.write((const uint8_t *)str, strlen(str));
// }

// size_t W5100_UDP::write(const uint8_t *buffer, size_t size)
// {
//   return udp.write(buffer, size);
// }

bool W5100_UDP::powerOn(void)
{
  return true;
}

bool W5100_UDP::powerOff(void)
{
  return true;
}

bool W5100_UDP::reset(void)
{
  return true;
}


bool W5100_UDP::begin(uint8_t *macAddress,
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

void W5100_UDP::poll(void)
{
  ; // No polling needed
}

void W5100_UDP::messageStart(void)
{
  udp.beginPacket(remoteIP, remotePort);
}

void W5100_UDP::messageEnd(void)
{
  udp.endPacket();
}

size_t W5100_UDP::messageWriteSize(void)
{
  return 0;
}

void W5100_UDP::checkForResponse(void)
{
  udp.parsePacket();
}

