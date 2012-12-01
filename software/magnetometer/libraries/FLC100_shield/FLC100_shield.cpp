#include <limits.h>
#include <avr/power.h>

#include <Arduino.h>
#include <FLC100_shield.h>


FLC100::FLC100(void)
{
  ;
}

FLC100::I2C::I2C(void) : state(off), axis(0), numSamples(1), median(false), 
			 trimmed(false)
{

}


bool FLC100::I2C::initialise(uint8_t pp, uint8_t adcAddressList[numAxes],
			     uint8_t adcChannelList[numAxes])
{
  powerPin = pp;
  pinMode(powerPin, OUTPUT);

  // Turn on 5V supply so that the ADC can be probed.
  digitalWrite(powerPin, HIGH);
  delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
  
  for (uint8_t i = 0; i < numAxes; ++i) {
    addresses[i] = adcAddressList[i];
    channels[i] = adcChannelList[i];
  }
  
  

    // Reset all MCP342x devices
  MCP342x::generalCallReset();

  bool r = true;
  // Autoprobe to check ADCs are actually present
  for (int i = 0; i < numAxes; ++i) {
    adc[i] = MCP342x(adcAddressList[i]);
    addresses[i] = adcAddressList[i];
    channels[i] = adcChannelList[i];
    adcConfig[i] = MCP342x::Config(adcChannelList[i], false, 18, 1);
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


void FLC100::I2C::process(void)
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
      for (uint8_t i = 0; i < numAxes; ++i)
	magData[i] = LONG_MIN;
      for (uint8_t i = 0; i < numAxes * maxSamples; ++i)
	magDataSamples[i] = LONG_MIN;
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
      for (uint8_t i = 0; i < numAxes; ++i) {
	long tmp = 0;
	uint8_t count = 0;
	for (uint8_t j = 0; j < numSamples; ++j) {
	  uint16_t index = (j * numAxes) + i;
	  if (magDataSamples[index] != LONG_MIN) {
	    ++count;
	    tmp += magDataSamples[index];
	  }
	  magData[i] = tmp / count;
	}
      }
      
      state = poweringDown;
      break;
    }
    
    if (magNum >= numAxes) {
      // state = poweringDown;
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
	// magData[magNum] = adcResult;
	magDataSamples[(sampleNum * numAxes) + magNum] = adcResult;
	++magNum;
      }
      else if (timeout.isExpired()) {
	++magNum;
      }
    }
    break;
    
  case poweringDown:
    digitalWrite(powerPin, LOW);
    state = finished;
    break;

  case finished:
    // Do nothing, remain in this state
    break;
  }
}


void FLC100::I2C::finish(void)
{
  state = finished;
  digitalWrite(powerPin, LOW);
}


FLC100::Misc::Misc(void) : state(off)
{


}

bool FLC100::Misc::initialise(void)
{
  pinMode(MCU_TEMPERATURE_PWR, OUTPUT);
  return true;
}

void FLC100::Misc::process(void)
{
  switch (state) {
  case off:
    break;

  case initialiseAdc:
    power_adc_enable(); // ENable ADC inside the MCU
    digitalWrite(MCU_TEMPERATURE_PWR, HIGH); // Apply power to the sensor
    state = initialiseMcuTemp;
    break;

  case initialiseMcuTemp:
    analogRead(MCU_TEMPERATURE_ADC); // Thow away first reading
    state = getMcuTemp;
    break;
    
  case getMcuTemp:
    /* Voltage in millivolts is given by (for details see description
     * below for battery voltage)
     * mV = (100 * count) / 31;
     * and from LM61 data sheet
     * hundredthsDegC = 10*mV - 6000
     * Combining gives
     * hundredthsDegC = ((1000*count)/31) - 6000
     * Work as int32_t to avoid overflow
     */
    mcuTemperature = ((1000 * int32_t(analogRead(MCU_TEMPERATURE_ADC))) / 31)
      - 6000;
    digitalWrite(MCU_TEMPERATURE_PWR, LOW); // Remove power from the sensor
    state = initialiseVoltage;
    break;
    
  case initialiseVoltage:
    analogRead(BATTERY_ADC);
    state = getVoltage;
    break;
    
  case getVoltage:
    /* Battery voltage is given by
     * V = (count / 1023) * 3.3
     * Or for millivolts
     * mV = (count/1023) * 3300
     * which gives
     * mV = (100 * count) / 31;
     * NB: 100 * 1023 requires 17 bits
     */
    batteryVoltage = (uint32_t(analogRead(BATTERY_ADC)) * 100) / 31;
    state = poweringDown;
    break;

  case poweringDown:
    power_adc_disable();
    state = finished;
    break;
    
 case finished:
    // Do nothing, remain in this state
    break;    
  }

}


void FLC100::Misc::finish(void)
{
  state = finished;
  // Disable ADC?
}
