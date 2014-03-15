#ifndef HOUSEKEEPING_H
#define HOUSEKEEPING_H

#include <AsyncDelay.h>

// #define MCU_VCC_mV 3300
#define VIN_ADC 2
#define VIN_DIVIDER 1
#define SYSTEM_TEMPERATURE_ADC 7
#define SYSTEM_TEMPERATURE_PWR A6

// State machine for reading SYSTEM temperature and battery voltage
class HouseKeeping {
public:

  static const uint8_t powerUpDelay_ms = 5; // Delay for temp sensor to power up
  
  HouseKeeping(void);
    
  bool initialise(uint16_t mcuVoltage_mV, bool readVin);
  inline bool isFinished(void) const;
  inline bool isSampling(void) const; // start called, results not ready
  inline bool isPowerOff(void) const;

  inline bool getReadVin(void) const;
  
  void start(void);
  void process(void);
  void powerOff(void);

  inline int16_t getSystemTemperature(void) const {
    return _systemTemperature;
  }
  inline uint16_t getVin(void) const {
    return _Vin;
  }

private:
  enum state_t {
    off,
    poweringUp,
    initialiseAdc,
    getSystemTemp0,
    getSystemTemp1,
    getVin0,
    getVin1,
    ready,
  };
  
  state_t _state;

  // Configuration
  uint16_t _mcuVoltage_mV;
  bool _readVin;
  
  // Data fields
  int16_t _systemTemperature; // hundredths of degrees Celsius
  uint16_t _Vin; // millivolts
  AsyncDelay _powerUpDelay;
};

extern HouseKeeping houseKeeping;

bool HouseKeeping::isFinished(void) const
{
  return _state == off || _state == ready;
}

bool HouseKeeping::isSampling(void) const
{
  return !isFinished();
}

bool HouseKeeping::isPowerOff(void) const
{
  return _state == off;
}

bool HouseKeeping::getReadVin(void) const
{
  return _readVin;
}

#endif
