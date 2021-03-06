#include <limits.h>
#include <avr/eeprom.h>
#include <avr/power.h>

#include <Arduino.h>
#include <AwEeprom.h>
#include <FLC100_shield.h>
#include "median.h"

unsigned long FLC100::powerUpDelay_ms = FLC100::defaultPowerUpDelay_ms;

FLC100::FLC100(void) : state(off), axis(0), numSamples(1), useMedian(false), 
			 trimSamples(false)
{

}


bool FLC100::initialise(uint8_t pp, uint8_t adcAddressList[numAxes],
			uint8_t adcChannelList[numAxes],
			uint8_t adcResolutionList[numAxes],
			uint8_t adcGainList[numAxes])
{
  powerPin = pp;
  pinMode(powerPin, OUTPUT);

  pinMode(FLC100_DUMP_CHARGE_PIN, OUTPUT);
  digitalWrite(FLC100_DUMP_CHARGE_PIN, HIGH);
  
  uint8_t pud_50ms = eeprom_read_byte((uint8_t*)FLC100_POWER_UP_DELAY_50MS);
  if (pud_50ms != 0xFF)
    powerUpDelay_ms = 50 * pud_50ms;
  
  // Turn on 5V supply so that the ADC can be probed. Ensure some
  // delay if set to zero (always on mode)
  digitalWrite(powerPin, HIGH);
  delay.start((powerUpDelay_ms ? powerUpDelay_ms : defaultPowerUpDelay_ms),
	      AsyncDelay::MILLIS);

  // Reset all MCP342x devices
  MCP342x::generalCallReset();

  bool r = true;
  // Autoprobe to check ADCs are actually present
  for (int i = 0; i < numAxes; ++i) {
    adc[i] = MCP342x(adcAddressList[i]);
    adcConfig[i] = MCP342x::Config(adcChannelList[i], false,
				   adcResolutionList[i], adcGainList[i]);
    if (adc[i].autoprobe(&adcAddressList[i], 1)) 
      adcPresent[i] = true;
    else {
      adcPresent[i] = false;
      r = false;
    }
  }

  tempConfig = MCP342x::Config(FLC100_TEMPERATURE_CHANNEL, false, 16, 1);



  
  return r;
}


void FLC100::process(void)
{
  static uint8_t magNum; // sub-state number
  static uint8_t tmp = 0;
  static uint8_t sampleNum = 0;

  switch (state) {
  case off:
    break;
    
  case poweringUp:
    if (delay.isExpired()) {
      timestamp = 0;
      sensorTemperature = INT_MIN; // Clear previous reading
      for (uint8_t i = 0; i < numAxes; ++i) {
	magData[i] = LONG_MIN;
	for (uint8_t j = 0; j < maxSamples; ++j)
	  magDataSamples[i][j] = LONG_MIN;
      }
      digitalWrite(FLC100_DUMP_CHARGE_PIN, LOW);

      // Ensure ADC has latched its address correctly
      MCP342x::generalCallReset();
      state = readingTime;
    }
    break;
    
  case readingTime:
    {
      CounterRTC::Time now;
      cRTC.getTime(now);
      timestamp = now.getSeconds();
    }
    state = convertingTemp;
    break;
    
  case convertingTemp:
    adc[0].convert(tempConfig);
    // Start two timers, after the first has expired try reading the
    // ADC until a result is returned. This reduces power consumption
    // from the I2C pull-up resistors and help keep the noise low
    // around the magnetometers. The second one is the timeout.
    delay.start(tempConfig.getConversionTime(), AsyncDelay::MICROS);
    timeout.start(tempConfig.getConversionTime() +
		  (tempConfig.getConversionTime() / 2), AsyncDelay::MICROS);
    state = readingTemp;
    break;
    
  case readingTemp:
    if (delay.isExpired()) {
      uint8_t err;
      MCP342x::Config status;
      long adcResult;
      err = adc[0].read(adcResult, status);
      if (!err && status.isReady()) {
	/* Have valid data. Convert to hundredths of degrees C using
	 * only integer arithmetic.
	 * From MCP342x data sheet:
	 * Vdiff = outputCount * 2.048V / ((maxCount+1) * gain)
	 * where Vdiff is in volts
	 * maxCount+1 is (1 << resolution)/2 and multiply by gain is a
	 * shift of log2(gain)
	 *
	 * Working in millivolts this can be given as
	 * mVdiff = outputCount * 2048 / (1 << (resolution + log2(gain) - 1))
	 * or
	 * mVdiff = (outputCount << 11) / (1 << (resolution + log2(gain) - 1))
	 * mVdiff = outputCount >> (resolution + log2(gain) - 12)
	 *
	 * From LM61 data sheet degC = (mV - 600)/10
	 * which gives hundredthsDegC = 10*mV - 6000
	 *
	 * Since mVdiff == mV
	 * hundredthsDegC = (outputCount * 10) >> (resolution + log2(gain) - 12)
	 *                  - 6000;
	 */
	sensorTemperature = ((adcResult * 10) >> (int(tempConfig.getResolution()) + tempConfig.getGain().log2() - 12)) - 6000;
	state = configuringMags;
	magNum = 0;
	tmp = 0;
      }
      else if (timeout.isExpired()) {
	state = configuringMags;
	magNum = 0;
	tmp = 0;
      }

    }
    break;
    
  case configuringMags:
    // Write configuration to each ADC. Use tmp as flag to indicate a
    // failed configuration attempt (and therefore to use the timeout
    // delay).
    if (magNum >= numAxes) {
      state = convertingMags;
      magNum = 0;
      tmp = 0;
      sampleNum = 0;
      break;
    }

    if (adcPresent[magNum] && (tmp == 0 || !timeout.isExpired())) {
      // ADC present and, either no attempts made to configure this ADC
      // or still within the timeout period.
      if (adc[magNum].configure(adcConfig[magNum]) ==
	  MCP342x::errorNone) {
	++magNum;
	tmp = 0; // Clear failed flag
      }
      else if (tmp == 0) {
	timeout.start(MCP342x::writeTimeout_us, AsyncDelay::MICROS);
	tmp = 1;
      }
    }
    else
      // May have reached this point because the ADC could not be
      // configured. Don't do anything, it will be checked later.
      ++magNum;
    break;

  case convertingMags:
    // Start conversions
    if (tmp == 0 || !timeout.isExpired()) {
      if (MCP342x::generalCallConversion() == 0) {
	// Conversion command succeeded, start the timers. Delay is
	// used to indicate when to first attempt reading the
	// results. Timeout is when to give up.
	delay.start(adcConfig[0].getConversionTime(), AsyncDelay::MICROS);
	timeout.start(adcConfig[0].getConversionTime() +
		      (adcConfig[0].getConversionTime() / 2),
		      AsyncDelay::MICROS);
	state = readingMags;
	magNum = 0;
	break;
      }
      else if (tmp == 0) {
	// Timeout for issuing the convert command
	timeout.start(MCP342x::writeTimeout_us, AsyncDelay::MICROS);
	tmp = 1;
      }
    }
    else {
      // Couldn't send generalCallConversion(); move on anyway.
      delay.start(adcConfig[0].getConversionTime(), AsyncDelay::MICROS);
      timeout.start(adcConfig[0].getConversionTime() +
		    (adcConfig[0].getConversionTime() / 2),
		    AsyncDelay::MICROS);
      state = readingMags;
      magNum = 0;
    }
    break;
    
  case readingMags:
    if (sampleNum >= numSamples) {
      // Calculate final result
      aggregate();
      
      state = poweringDown;
      break;
    }
    
    if (magNum >= numAxes) {
      ++sampleNum;
      state = convertingMags;
      magNum = 0;
      tmp = 0; 
      break;
    }

    if (!adcPresent[magNum]) {
      ++magNum;
      break;
    }
        
    if (delay.isExpired()) {
      uint8_t err;
      MCP342x::Config status;
      long adcResult;
	
      err = adc[magNum].read(adcResult, status);
      if (!err && status.isReady()) {
	// Have valid data
	MCP342x::normalise(adcResult, status);
	magDataSamples[magNum][sampleNum] = adcResult;
	++magNum;
      }
      else if (timeout.isExpired()) {
	++magNum;
      }
    }
    break;
    
  case poweringDown:
    if (powerUpDelay_ms)
      digitalWrite(powerPin, LOW);
    digitalWrite(FLC100_DUMP_CHARGE_PIN, HIGH);
    state = finished;
    break;

  case finished:
    // Do nothing, remain in this state
    break;
  }
}


void FLC100::finish(void)
{
  state = finished;
  if (powerUpDelay_ms)
    digitalWrite(powerPin, LOW);
  digitalWrite(FLC100_DUMP_CHARGE_PIN, HIGH);
}


void FLC100::aggregate(void)
{
  for (uint8_t i = 0; i < numAxes; ++i) {
    if (!adcPresent[i])
      continue;

    if (useMedian)
      magData[i] = median<long>(magDataSamples[i], numSamples);
    else {
      // Mean. Ignore any values which are LONG_MIN since they
      // represent sampling errors.
      long tmp = 0;
      long smallest, largest; // Initialised when first valid sample found
      uint8_t count = 0;
      for (uint8_t j = 0; j < numSamples; ++j) {
	if (magDataSamples[i][j] != LONG_MIN) {
	  // Sample is valid
	  if (count) {
	    if (magDataSamples[i][j] < smallest)
	      smallest = magDataSamples[i][j];
	    if (magDataSamples[i][j] > largest)
	      largest = magDataSamples[i][j];
	  }
	  else 
	    largest = smallest = magDataSamples[i][j];
	  ++count;
	  tmp += magDataSamples[i][j];
	}
	if (trimSamples && count >= 3) {
	  // Remove largest and smallest values
	  tmp = tmp - largest - smallest;
	  count -= 2;
	}
	magData[i] = tmp / count;
      }
    }
  }
 
}


