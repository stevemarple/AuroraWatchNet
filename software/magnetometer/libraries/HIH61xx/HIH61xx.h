#ifndef HIH61XX_H
#define HIH61XX_H

#include <SoftWire.h>
#include <AsyncDelay.h>

class HIH61xx {
public:
  static const uint8_t defaultAddress = 0x27;
  static const uint8_t powerUpDelay_ms = 75; // Data sheet indicates 60ms
  static const uint8_t conversionDelay_ms = 45; // "Typically 36.65ms"

  HIH61xx(void);
  
  inline int16_t getAmbientTemp(void) const;
  inline uint16_t getRelHumidity(void) const;
  inline uint8_t getStatus(void) const;

  inline bool isFinished(void) const;
  inline bool isSampling(void) const; // start called, results not ready
  inline bool isPowerOff(void) const;
  
  bool initialise(uint8_t sda, uint8_t scl, uint8_t power = 255);
  
  void start(void); // To include power-up (later), start sampling
  void process(void); // Call often to process state machine
  void finish(void); // Force completion and power-down
  void timeoutDetected(void);
  
private:
  enum state_t {
    off,
    poweringUp, // power applied, waiting for timeout
    converting, // Conversion started, waiting for completion
    reading, // Ready to read results
    poweringDown,
    finished, // Results read
  };

  enum status_t {
    statusNormal = 0,    // Defined by HIH61xx device
    statusStaleData = 1, // Defined by HIH61xx device
    statusCmdMode = 2,   // Defined by HIH61xx device
    statusNotUsed = 3,   // Defined by HIH61xx device
    statusUninitialised = 4,
    statusTimeout = 5,
  };

  uint8_t _address;
  uint8_t _powerPin;
  state_t _state;
  SoftWire _i2c;

  int16_t _ambientTemp;
  uint16_t _relHumidity;
  uint8_t _status;
  AsyncDelay _delay;
};


int16_t HIH61xx::getAmbientTemp(void) const
{
  return _ambientTemp;
}


uint16_t HIH61xx::getRelHumidity(void) const
{
  return _relHumidity;
}

uint8_t HIH61xx::getStatus(void) const
{
  return _status;
}

bool HIH61xx::isFinished(void) const
{
  return _state == finished;
}


bool HIH61xx::isSampling(void) const
{
  return !(_state == off || _state == finished);
}


bool HIH61xx::isPowerOff(void) const
{
  return (_state == off || _state == finished);
}


#endif
