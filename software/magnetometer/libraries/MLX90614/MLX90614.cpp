#include <MLX90614.h>

unsigned long MLX90614::powerUpDelay_ms = MLX90614::defaultPowerUpDelay_ms;

int16_t MLX90614::convertToCentiC(uint16_t data)
{
  if (data & 0x8000)
    // MSB does seem to be set for some devices when error exists
    return 32767;
  
  data <<= 1; // Convert from units of 0.02K to 0.01K
  --data;
  return int16_t(data) - 27315;
}


uint16_t MLX90614::convertToCentiK(uint16_t data)
{
  uint16_t r = data;
  // Remove MSB (error bit, ignored for temperatures)
  r &= 0x7FFF;
  r <<= 1; // Convert from units of 0.02K to 0.01K
  --r;
  return r;
}

MLX90614::MLX90614(void) : state(off),
	i2c(sdaPin, sclPin)
{
  ;
}

//bool MLX90614::initialise(uint8_t sda, uint8_t scl, uint8_t power)
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
    if (!delay.isExpired())
      break;
    
    ambient = convertToCentiC(read(addressAmbient));
    state = readingObject1;
    break;

  case readingObject1:
    object1 = convertToCentiC(read(addressObject1));
    if (dualSensor)
      state = readingObject2;
    else
      state = poweringDown;
    break;

  case readingObject2:
    object2 = convertToCentiC(read(addressObject2));
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
  //pinMode(sdaPin, INPUT);
  //pinMode(sclPin, INPUT);
  i2c.setSdaHigh();
  i2c.setSclHigh();
  if (powerPin != 255)
    digitalWrite(powerPin, LOW);
  state = finished;
}

uint16_t MLX90614::read(uint8_t command) const
{
  uint8_t address = 0x5A;
  uint8_t dataLow = 0;
  uint8_t dataHigh = 0;
  uint8_t pec = 0;

  uint8_t errors = 0;
  // Send command
  errors += i2c.startWait(address, SoftWire::writeMode);
  errors += i2c.rawWrite(command);
  
  // Read results
  errors += i2c.repeatedStart(address, SoftWire::readMode);
  errors += i2c.readThenAck(dataLow);  // Read 1 byte and then send ack
  errors += i2c.readThenAck(dataHigh); // Read 1 byte and then send ack
  errors += i2c.readThenNack(pec);
  i2c.stop();

  if (errors)
    return 0xFFFF;
  
  uint8_t crc = 0;
  crc = SoftWire::crc8_update(crc, address << 1); // Write address
  crc = SoftWire::crc8_update(crc, command);
  crc = SoftWire::crc8_update(crc, (address << 1) + 1); // Read address
  crc = SoftWire::crc8_update(crc, dataLow);
  crc = SoftWire::crc8_update(crc, dataHigh);
  crc = SoftWire::crc8_update(pec, pec);

  if (crc)
    return 0xFFFF;
  return (uint16_t(dataHigh) << 8) | dataLow;
}

// uint16_t MLX90614::read(uint8_t command) const
// {
//   int address = 0x5A << 1;
//   int dataLow = 0;
//   int dataHigh = 0;
//   int pec = 0;
  
//   // digitalWrite(LED_BUILTIN, HIGH); delayMicroseconds(50);

//   i2c.startWait(address, SoftWire::writeMode);
//   i2c.rawWrite(command);
    
//   // read
//   i2c.repeatedStart(address, SoftWire::readMode);
//   dataLow = i2c_readAck();  // Read 1 byte and then send ack
//   dataHigh = i2c_readAck(); // Read 1 byte and then send ack
//   pec = i2c_readNak();
//   i2c_stop();
//   //digitalWrite(LED_BUILTIN, LOW);

//   return (uint16_t(dataHigh) << 8) | dataLow;
// }

   
