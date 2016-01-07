#include <MLX90614.h>

unsigned long MLX90614::powerUpDelay_ms = MLX90614::defaultPowerUpDelay_ms;

int16_t MLX90614::convertToCentiC(uint16_t data)
{
  // Check for error bit set
  if (data & 0x8000U)
    return 0x7FFF;
  
  // Convert from units of 0.02K to 0.01K then subtract 273.15 degC
  return int16_t(data << 1U) - 27315;
}


uint16_t MLX90614::convertToCentiK(uint16_t data)
{
  // Check for error bit set
  if (data & 0x8000U)
    return 0xFFFFU;

  return data << 1U;
}

MLX90614::MLX90614(void) : state(off),
	i2c(sdaPin, sclPin)
{
  ;
}

bool MLX90614::initialise(void)
{
  // For Calunium
  sdaPin = 16;
  sclPin = 19;
  powerPin = 18;
  dualSensor = false;

  i2c.setSda(sdaPin);
  i2c.setScl(sclPin);
  i2c.enablePullups(false); // Do not enable with a power pin
  
  if (powerPin != 255) {
    pinMode(powerPin, OUTPUT);
    digitalWrite(powerPin, LOW); // Off
  }

  if (!dualSensor)
    object2 = 0;
  
  return true;
}
  
void MLX90614::start(void)
{
  if (powerPin != 255) {
    // Let SDA and SCL float
    i2c.setSdaHigh();
    i2c.setSclHigh();
    digitalWrite(powerPin, HIGH);
    delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
  }
  state = poweringUp;
}

void MLX90614::process(void)
{
  switch (state) {
  case off:
    // Stay powered off until told to turn on
    break;

  case poweringUp:
    if (delay.isExpired()) {
      i2c.setSclLow();
      delay.start(3, AsyncDelay::MILLIS); // SCL must be low for > 1.44ms
      state = exitingPwm;
    }
    break;

  case exitingPwm:
    if (delay.isExpired()) {
      i2c.setSclHigh();
      delay.start(2, AsyncDelay::MILLIS);
      state = readingAmbient;
    }
    break;

  case readingAmbient:
    if (delay.isExpired()) {
      uint16_t value;
      if (read(addressAmbient, value))
	ambient = convertToCentiC(value);
      else
	ambient = 0x7FFF;
      state = readingObject1;
    }
    break;

  case readingObject1:
    {
      uint16_t value;
      if (read(addressObject1, value))
	object1 = convertToCentiC(value);
      else
	object1 = 0x7FFF;
    }
    if (dualSensor)
      state = readingObject2;
    else
      state = poweringDown;
    break;

  case readingObject2:
    {
      uint16_t value;
      if (read(addressObject2, value))
	object2 = convertToCentiC(value);
      else
	object2 = 0x7FFF;
    }
    state = poweringDown;
    break;

  case poweringDown:
    finish(); // Sets state to finished
    break;

  case finished:
    // Do nothing, remain in this state
    break;
  }
}


void MLX90614::finish(void)
{
  i2c.setSdaHigh();
  i2c.setSclHigh();
  if (powerPin != 255)
    digitalWrite(powerPin, LOW);
  state = finished;
}


bool MLX90614::read(uint8_t command, uint16_t &value) const
{
  uint8_t address = 0x5A;
  uint8_t dataLow = 0;
  uint8_t dataHigh = 0;
  uint8_t pec = 0;

  bool r = !(i2c.startWait(address, SoftWire::writeMode) ||
	     i2c.write(command) || // Command sent
	     i2c.repeatedStart(address, SoftWire::readMode) || // Read results
	     i2c.readThenAck(dataLow) ||  // Read 1 byte and then send ack
	     i2c.readThenAck(dataHigh) || // Read 1 byte and then send ack
	     i2c.readThenNack(pec));
  i2c.stop();
  if (r) {
    uint8_t crc = 0;
    crc = SoftWire::crc8_update(crc, address << 1U); // Write address
    crc = SoftWire::crc8_update(crc, command);
    crc = SoftWire::crc8_update(crc, (address << 1U) + 1U); // Read address
    crc = SoftWire::crc8_update(crc, dataLow);
    crc = SoftWire::crc8_update(crc, dataHigh);
    crc = SoftWire::crc8_update(pec, pec);

    if (crc)
      return false;
    value = (uint16_t(dataHigh) << 8U) | dataLow;
    return true;
  }
  return false;
}
