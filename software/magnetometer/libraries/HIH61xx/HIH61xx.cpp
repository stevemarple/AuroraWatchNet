#include <HIH61xx.h>

HIH61xx::HIH61xx(void) : _address(defaultAddress),
  _powerPin(255),
  _state(off),
  _i2c(255, 255),
  _ambientTemp(32767),
  _relHumidity(65535),
  _status(statusUninitialised)
{
  ;
}

bool HIH61xx::initialise(uint8_t sdaPin, uint8_t sclPin, uint8_t powerPin)
{
  _i2c.setSda(sdaPin);
  _i2c.setScl(sclPin);
  _i2c.begin();  // Sets up pin mode for SDA and SCL
  _powerPin = powerPin;
  if (_powerPin != 255) {
    pinMode(_powerPin, OUTPUT);
    digitalWrite(_powerPin, LOW);
  }
  // TODO: check presence of HIH61xx

  // Use the delay so that even when always on the power-up delay is
  // observered from initialisation
  _delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
  
  return true;
}

void HIH61xx::start(void)
{
  if (_powerPin != 255) {
    digitalWrite(_powerPin, HIGH);
    _delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
  }
  _state = poweringUp;
}

void HIH61xx::process(void)
{
  switch (_state) {
  case off:
    // Stay powered off until told to turn on
    break;

  case poweringUp:
    if (_delay.isExpired()) {
      uint8_t s = _i2c.start(defaultAddress, SoftWire::writeMode);
      _i2c.stop();
      if (s == SoftWire::timedOut) 
	timeoutDetected();
      else {
	_delay.start(conversionDelay_ms, AsyncDelay::MILLIS);
	_state = converting;
      }
    }
    break;
    
  case converting:
    if (_delay.isExpired()) {
      _state = reading;
    }
    break;

  case reading:
    {
      uint8_t data[4];
      if (_i2c.start(_address, SoftWire::readMode) || 
	  _i2c.readThenAck(data[0]) || 
	  _i2c.readThenAck(data[1]) ||
	  _i2c.readThenAck(data[2]) ||
	  _i2c.readThenNack(data[3])) {
	timeoutDetected();
	break;
      }
      _i2c.stop();
      _status = data[0] >> 6;
      uint16_t rawHumidity = ((((uint16_t)data[0] & 0x3F) << 8) |
			      (uint16_t)data[1]);
      uint16_t rawTemp = ((uint16_t)data[2] << 6) | ((uint16_t)data[3] >> 2);
      
      _relHumidity = (long(rawHumidity) * 10000L) / 16382;
      _ambientTemp = ((long(rawTemp) * 16500L) / 16382) - 4000;
    }
    _state = poweringDown;
    break;

  case poweringDown:
    finish(); // Sets state to finished
    break;

  case finished:
    // Do nothing, remain in this state
    break;
  }
}

void HIH61xx::finish(void)
{
  _i2c.stop(); // Release SDA and SCL
  if (_powerPin != 255) 
    digitalWrite(_powerPin, LOW);
  _state = finished;
}


void HIH61xx::timeoutDetected(void)
{
  finish();
  _ambientTemp = 32767;
  _relHumidity = 65535;
  _status = statusTimeout;
}
