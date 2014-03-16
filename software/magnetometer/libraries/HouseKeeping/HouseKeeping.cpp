#include <avr/power.h>
#include <HouseKeeping.h>

HouseKeeping houseKeeping;

HouseKeeping::HouseKeeping(void) : _state(off),
				   _VinDivider(1),
				   _mcuVoltage_mV(3300),
				   _readVin(true),
				   _systemTemperature(0),
				   _Vin(0)
{
  ;
}

bool HouseKeeping::initialise(uint8_t VinADC, uint8_t temperatureADC,
			      uint8_t temperaturePowerPin,
			      uint16_t mcuVoltage_mV, bool readVin,
			      bool alwaysOn)
{
  _VinADC = VinADC;
  _temperatureADC = temperatureADC;
  _temperaturePowerPin = temperaturePowerPin;
  _alwaysOn = alwaysOn;
  _mcuVoltage_mV = mcuVoltage_mV;
  _readVin = readVin;
  if (_temperaturePowerPin != 255)
    pinMode(_temperaturePowerPin, OUTPUT);
  return true;
}


void HouseKeeping::start(void)
{
  if (_state == off && _temperaturePowerPin != 255) {
    digitalWrite(_temperaturePowerPin, HIGH); // Apply power to the sensor
    _powerUpDelay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
    _state = poweringUp;
  }
  else
    _state = initialiseAdc;
}


void HouseKeeping::process(void)
{
  switch (_state) {
  case off:
    // Stay powered off until told to turn on
    break;

  case poweringUp:
    if (_powerUpDelay.isExpired())
      _state = initialiseAdc;
    break;

  case initialiseAdc:
    power_adc_enable(); // Enable ADC inside the MCU
    _state = getSystemTemp0;
    break;

  case getSystemTemp0:
    analogRead(_temperatureADC); // Thow away first reading
    _state = getSystemTemp1;
    break;
    
  case getSystemTemp1:
    /* Voltage in millivolts is given by (for details see description
     * below for battery voltage)
     * mV = (100 * count) / 31;
     * and from LM61 data sheet
     * hundredthsDegC = 10*mV - 6000
     * Combining gives
     * hundredthsDegC = ((1000*count)/31) - 6000
     * Work as int32_t to avoid overflow
     */

    /* Voltage in millivolts is given by (for details see description
     * below for battery voltage)
     * mV = ((count * MCU_VCC_mV) + 512) / 1023
     * [512 added for rounding to nearest mV value]
     * From LM61 data sheet
     * hundredthsDegC = 10 * mv - 6000
     * hundredthsDegC = (((10 * count * MCU_VCC_mV) + 512) / 1023) - 6000
     */
    _systemTemperature = (((10 * int32_t(analogRead(_temperatureADC))
			    * _mcuVoltage_mV) + 512) / 1023) - 6000;
    if (_readVin)
      _state = getVin0;
    else
      _state = ready;
    break;
    
  case getVin0:
    analogRead(_VinADC); // Thow away first reading
    _state = getVin1;
    break;
    
  case getVin1:
    /* Battery voltage in millivolts is given by
     * mV = (count * 3300 * _VinDivider) / 1023
     * NB: Use 32 bits
     *
     * To round to nearest millivolt add 512 before dividing.
     */
    _Vin = ((uint32_t(analogRead(_VinADC)) *
	     _mcuVoltage_mV * _VinDivider) + 512) 
      / 1023;
    if (_alwaysOn)
      _state = ready;
    else
      _state = off;
    break;
    
 case ready:
    // Do nothing, remain in this state
    break;    
  }

}


void HouseKeeping::powerOff(void)
{
  if (!_alwaysOn && _temperaturePowerPin != 255)
    digitalWrite(_temperaturePowerPin, LOW); // Remove power from the sensor
  _state = off;
}
