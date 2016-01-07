#include <RF12.h>
#include <RFM12B_Radio.h>

RFM12B_Radio::RFM12B_Radio(RF12_Stream &s) :
  stream(s)
{
  ;
}

bool RFM12B_Radio::begin(uint8_t cs, uint8_t irqPin, uint8_t irqNum,
			 uint8_t id, uint8_t band, uint16_t channel,
			 uint8_t group)
{
  return stream.begin(cs, irqPin, irqNum, id, band, channel, group);
}

int RFM12B_Radio::available(void)
{
  return stream.available();
}

int RFM12B_Radio::peek(void)
{
  return stream.peek();
}

int RFM12B_Radio::read(void)
{
  return stream.read();
}

void RFM12B_Radio::flush(void)
{
  return stream.flush();
}

size_t RFM12B_Radio::write(uint8_t c)
{
  return stream.write(c);
}

bool RFM12B_Radio::powerOn(void)
{
  return stream.powerOff();
}

bool RFM12B_Radio::powerOff(void)
{
  return stream.powerOff();
}

bool RFM12B_Radio::reset(void)
{
  // TODO
  return true;
}

void RFM12B_Radio::poll(void)
{
  stream.poll();
}

void RFM12B_Radio::messageStart(void)
{
  ;
}

void RFM12B_Radio::messageEnd(void)
{
  ;
}

size_t RFM12B_Radio::messageWriteSize(void)
{
  return 1;
}

void RFM12B_Radio::checkForResponse(void)
{
  ;
}

