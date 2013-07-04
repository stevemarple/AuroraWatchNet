#include <limits.h>
#include <avr/eeprom.h>
#include <avr/power.h>

#include <Arduino.h>
#include <MLX90614.h>
#include <mysofti2cmaster.h>

unsigned long MLX90614::powerUpDelay_ms = MLX90614::defaultPowerUpDelay_ms;

uint16_t MLX90614::convertToCentiK(const uint16_t &data)
{
  uint16_t r = data;
  // Remove MSB (error bit, ignored for temperatures)
  r &= 0x7FFF;
  r <<= 1; // Convert from units of 0.02K to 0.01K
  --r;
  return r;
}

MLX90614::MLX90614(void)
{
  ;
}

//bool MLX90614::initialise(uint8_t scl, uint8_t sda, uint8_t power)
bool MLX90614::initialise(void)
{
  // For Calunium
  sclPin = 19;
  sdaPin = 16;
  powerPin = 18;
  dualSensor = false;
  
  pinMode(powerPin, OUTPUT);
  digitalWrite(powerPin, LOW); // Off
  pinMode(sclPin, INPUT); // Inactive for I2C
  pinMode(sdaPin, INPUT); // Inactive for I2C
  if (!dualSensor)
    object2 = 0;
  
  return true;
}
  
void MLX90614::start(void)
{
  if (state == off) {
      state = poweringUp;
      pinMode(sdaPin, INPUT);
      pinMode(sclPin, INPUT);
      digitalWrite(powerPin, HIGH);
      delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
  }
  else
    state = readingAmbient;
}

void MLX90614::process(void)
{
  switch (state) {
  case off:
    // Stay powered off until told to turn on
    break;

  case poweringUp:
    if (delay.isExpired()) {
      state = readingAmbient;
    }
    break;
    
  case readingAmbient:
    ambient = read(addressAmbient);
    convertToCentiK(ambient);
    state = readingObject1;
    break;

  case readingObject1:
    object1 = read(addressObject1);
    convertToCentiK(object1);
    if (dualSensor)
      state = readingObject2;
    else
      state = ready;
    break;

  case readingObject2:
    object2 = read(addressObject2);
    convertToCentiK(object2);
    state = ready;
    break;

  case ready:
    break; // Stay powered on until told to turn off
  }
}


void MLX90614::powerOff(void)
{
  pinMode(sdaPin, INPUT);
  pinMode(sclPin, INPUT);
  // pinMode(powerPin, OUTPUT);
  digitalWrite(powerPin, LOW);
  state = off;
}

uint16_t MLX90614::read(uint8_t command) const
{
  int dev = 0x5A << 1;
  int dataLow = 0;
  int dataHigh = 0;
  int pec = 0;
  
  // digitalWrite(LED_BUILTIN, HIGH); delayMicroseconds(50);

  i2c_start_wait(dev + I2C_WRITE);
  i2c_write(command);
    
  // read
  i2c_rep_start(dev + I2C_READ);
  dataLow = i2c_readAck();  // Read 1 byte and then send ack
  dataHigh = i2c_readAck(); // Read 1 byte and then send ack
  pec = i2c_readNak();
  i2c_stop();
  //digitalWrite(LED_BUILTIN, LOW);

  return (uint16_t(dataHigh) << 8) | dataLow;
}

   
