#include <RF12.h>
#include <RFM12B_Radio.h>

RFM12B_Radio::RFM12B_Radio(RF12_Stream &s) :
  stream(s)
{
  ;
}

bool RFM12B_Radio::begin(uint8_t cs, uint8_t irqPin, uint8_t irqNum,
			 uint8_t id, uint8_t band, uint8_t group)
{
  return stream.begin(cs, irqPin, irqNum, id, band, group);
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
  rf12_sleep(RF12_WAKEUP);
  return true;
}

bool RFM12B_Radio::powerOff(void)
{
  rf12_sleep(RF12_SLEEP);
  return true;
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

