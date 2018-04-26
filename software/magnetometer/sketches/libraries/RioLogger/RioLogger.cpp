#include <limits.h>
#include <avr/eeprom.h>
#include <avr/power.h>

#include <Arduino.h>
#include <AwEeprom.h>
#include <RioLogger.h>
#include "median.h"

unsigned long RioLogger::powerUpDelay_ms = RioLogger::defaultPowerUpDelay_ms;
uint16_t RioLogger::presampleDelay_ms = 10;

const uint8_t RioLogger::scanMapping7[7] = {0, 1, 3, 2, 6, 4, 5}; // Almost a Gray code
const uint8_t RioLogger::scanMapping8[8] = {0, 1, 3, 2, 6, 7, 5, 4}; // Gray code

RioLogger::RioLogger(void) : state(off), axis(0), numSamples(1), scanState(0),
							 useMedian(false), trimSamples(false)
{
    numRows = eeprom_read_byte((uint8_t*)EEPROM_RIO_NUM_ROWS);
    if (numRows > EEPROM_RIO_NUM_ROWS_MAX)
        numRows = EEPROM_RIO_NUM_ROWS_MAX;

    numCols = eeprom_read_byte((uint8_t*)EEPROM_RIO_NUM_COLS);
    if (numCols > EEPROM_RIO_NUM_COLS_MAX)
        numCols = EEPROM_RIO_NUM_COLS_MAX;

    if (numRows == 7)
        // Not a Gray code but the best available for an odd number. The multi-bit change occurs when the sequence
        // wraps around, which is hopefully when it matters least.
        scanMapping = scanMapping7;
    else
        // Will only be a Gray code if numRows == 4 or numRows == 8. Any other value will need its own sequence.
        scanMapping = scanMapping8;
}


bool RioLogger::initialise(uint8_t pp, uint8_t adcAddressList[maxNumAdcs],
						   uint8_t adcChannelList[maxNumAdcs],
						   uint8_t adcResolutionList[maxNumAdcs],
						   uint8_t adcGainList[maxNumAdcs])
{
	powerPin = pp;
	pinMode(powerPin, OUTPUT);
    scanState = 0;
    // 5, 9 available; 7 possibly available if not needed for PPS.
    scanPins[0] = 23;
    scanPins[1] = 22;
    scanPins[2] = 14;

    for (uint8_t i = 0; i < numScanPins; ++i)
        pinMode(scanPins[i], OUTPUT);

    setScanPins();

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
	for (int i = 0; i < maxNumAdcs; ++i) {
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


void RioLogger::process(void)
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
			for (uint8_t i = 0; i < maxNumAdcs; ++i) {
				magData[i] = LONG_MIN;
				for (uint8_t j = 0; j < maxSamples; ++j)
					magDataSamples[i][j] = LONG_MIN;
			}

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
		state = advanceScan;
		break;

    case advanceScan:
        // TODO: Advance scan step
        setScanPins();
        presampleDelay.start(presampleDelay_ms, AsyncDelay::MILLIS);
        Serial.print("Advance scan: ");
        Serial.println(scanState);
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
				state = configuringRioADCs;
				magNum = 0;
				tmp = 0;
			}
			else if (timeout.isExpired()) {
				state = configuringRioADCs;
				magNum = 0;
				tmp = 0;
			}

		}
		break;

	case configuringRioADCs:
		// Write configuration to each ADC. Use tmp as flag to indicate a
		// failed configuration attempt (and therefore to use the timeout
		// delay).
		if (magNum >= numCols) {
			state = presampleHold;
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

    case presampleHold:
        if (presampleDelay.isExpired()) {
            state = convertingRioADCs;
        }
        break;

	case convertingRioADCs:
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
				state = readingRioADCs;
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
			state = readingRioADCs;
			magNum = 0;
		}
		break;

	case readingRioADCs:
		if (sampleNum >= numSamples) {
			// Calculate final result
			aggregate();

            ++scanState;
            if (scanState >= numRows) {
                scanState = 0;
			    state = poweringDown;
            }
            else
			    state = advanceScan;
			break;
		}

		if (magNum >= numCols) {
			++sampleNum;
			state = convertingRioADCs;
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
	    // If numRows is odd there will be a glitch when wrapping around scanMapping (it cannot be a Gray code).
	    // Set the scan pins now when it matters least.
	    setScanPins();
		if (powerUpDelay_ms)
			digitalWrite(powerPin, LOW);
		state = finished;
		break;

	case finished:
		// Do nothing, remain in this state
		break;
	}
}


void RioLogger::finish(void)
{
	state = finished;
	if (powerUpDelay_ms)
		digitalWrite(powerPin, LOW);
}


void RioLogger::aggregate(void)
{
	for (uint8_t i = 0; i < numCols; ++i) {
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


void RioLogger::setScanPins() const
{
    const uint8_t val = scanMapping[scanState];
    uint8_t mask = 1;

    for (uint8_t i = 0; i < numScanPins; ++i) {
        digitalWrite(scanPins[i], val & mask);
        mask <<= 1;
    }
}