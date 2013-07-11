#ifndef MLX90614_H
#define MLX90614_H

#include <stdint.h>
#include <AsyncDelay.h>
#include <SoftWire.h>

class MLX90614 {
public:
  static const unsigned long defaultPowerUpDelay_ms = 1000;
  static unsigned long powerUpDelay_ms;

  static const uint8_t addressAmbient = 6;
  static const uint8_t addressObject1 = 7;
  static const uint8_t addressObject2 = 8;
  static const uint8_t addressFlags = 0xf0;
  static const uint8_t addressSleep = 0xff;

  static uint16_t convertToCentiK(uint16_t data);
  static int16_t convertToCentiC(uint16_t data);
  MLX90614(void);

  // Read
  inline int16_t getAmbient(void) const;
  inline int16_t getObject1(void) const;
  inline int16_t getObject2(void) const;
  inline SoftWire& getSoftWire(void);
  
  // TODO: take pin details
  // bool initialise(uint8_t scl, uint8_t sda, uint8_t power = 255);
  bool initialise(void);

  inline bool isDualSensor(void) const;
  inline bool isFinished(void) const;
  inline bool isSampling(void) const; // start called, results not ready
  inline bool isPowerOff(void) const;
  
  void start(void); // Power up if needed, start sampling
  void process(void); // Call often to process state machine
  void finish(void); // Force completion and power-down

  uint16_t read(uint8_t address) const;

  
  
private:
  enum state_t {
    off,
    poweringUp,
    exitingPwm,
    readingAmbient,
    readingObject1,
    readingObject2,
    poweringDown,
    finished,
  };
    
  state_t state;
  uint8_t sdaPin;
  uint8_t sclPin;
  uint8_t powerPin;

  int16_t ambient;
  int16_t object1;
  int16_t object2;
  bool dualSensor;

  AsyncDelay delay;
  SoftWire i2c;
};

int16_t MLX90614::getAmbient(void) const
{
  return ambient;
}
  
int16_t MLX90614::getObject1(void) const
{
  return object1;
}

int16_t MLX90614::getObject2(void) const
{
  return object2;
}

SoftWire& MLX90614::getSoftWire(void)
{
  return i2c;
}

bool MLX90614::isDualSensor(void) const
{
  return dualSensor;
}

bool MLX90614::isFinished(void) const
{
  return state == finished;
}

bool MLX90614::isSampling(void) const
{
  return !(state == off || state == finished);
}

bool MLX90614::isPowerOff(void) const
{
  return (state == off || state == finished);
}


#endif
