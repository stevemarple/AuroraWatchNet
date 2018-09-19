#include <limits.h>
#include <avr/eeprom.h>
#include <avr/power.h>

#include <Arduino.h>
#include <AwEeprom.h>
#include <RioLogger.h>
#include "median.h"

unsigned long RioLogger::powerUpDelay_ms = RioLogger::defaultPowerUpDelay_ms;
uint16_t RioLogger::presampleDelay_ms = 10;

RioLogger::RioLogger(void) : gpioAddress(0), state(off), axis(0), scanState(0),
                             adcMask(0), numSamples(1), useMedian(false), trimSamples(false)
{
    gpioAddress = eeprom_read_byte((const uint8_t*)EEPROM_RIO_GPIO_ADDRESS);
    if (gpioAddress < MCP23008_ADDRESS_MIN || gpioAddress > MCP23008_ADDRESS_MAX)
        gpioAddress = 0;

	numRows = eeprom_read_byte((const uint8_t*)EEPROM_RIO_NUM_ROWS);
	if (numRows >= maxRows)
		numRows = maxRows;

	numColumns = eeprom_read_byte((const uint8_t*)EEPROM_RIO_NUM_COLUMNS);
	if (numColumns >= maxColumns)
		numColumns = maxColumns;

    for (uint8_t i = 0; i < maxRows; ++i) {
    	houseKeepingAdcMask[i] = 0;
        scanMapping[i] = eeprom_read_byte((const uint8_t*)(EEPROM_RIO_SCAN_MAPPING + i));
    }
}


bool RioLogger::initialise(uint8_t pp, uint8_t adcAddressList[maxNumAdcs],
						   uint8_t adcChannelList[maxNumAdcs],
						   uint8_t adcResolutionList[maxNumAdcs],
						   uint8_t adcGainList[maxNumAdcs])
{
	powerPin = pp;
	pinMode(powerPin, OUTPUT);
	scanState = 0;
    initGpio();
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
//	// Autoprobe to check ADCs are actually present
//	adcMask = eeprom_read_byte((const uint8_t*)EEPROM_RIO_RIOMETER_ADC_MASK);
//	for (uint8_t i = 0; i < maxNumAdcs; ++i) {
//		adc[i] = MCP342x(adcAddressList[i]);
//		adcConfig[i] = MCP342x::Config(adcChannelList[i], false,
//									   adcResolutionList[i], adcGainList[i]);
//		if (adc[i].autoprobe(&adcAddressList[i], 1))
//			adcPresent[i] = true;
//		else {
//			adcPresent[i] = false;
//			r = false;
//		}
//	}

    // Resolution is for the same for all ADCs (for timing reasons)
    uint8_t resolution = eeprom_read_byte((const uint8_t*)EEPROM_RIO_RIOMETER_ADC_RESOLUTION);
	for (uint8_t i = 0; i < maxNumAdcs; ++i) {
	    uint8_t i2cAddress = adcAddressList[i];

	    // Use autoprobe to test if device is present. Exclude reserved addresses
		if (i2cAddress > 3 && i2cAddress < 120 && adc[i].autoprobe(&i2cAddress, 1)) // Fake an array of size 1
			adcPresent[i] = true;
		else {
			adcPresent[i] = false;
			r = false;  // One of the indicated ADCs is not present.
		}

        const uint8_t bitMask = 1 << i;
        if (adcPresent[i] && (adcMask & bitMask)) {
            // ADC present and the EEPROM setting in the mask indicates this ADC is to be used.
            uint8_t channel = eeprom_read_byte((const uint8_t*)EEPROM_RIO_RIOMETER_ADC_CHANNEL_LIST);
            uint8_t gain = eeprom_read_byte((const uint8_t*)EEPROM_RIO_RIOMETER_ADC_GAIN_LIST);
            adcConfig[i] = MCP342x::Config(channel, false, resolution, gain);
        }
        else {
            // Insert a sensible configuration anyway. This especically matters for adcConfig[0] since it's resolution
            // value is used to determine the delay and timeout when reading the data back.
            adcConfig[i] = MCP342x::Config(1, false, resolution, 1);
        }
	}

    static_assert(EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST_SIZE >= maxNumAdcs, "ADC channel list size too small");
    for (uint8_t rn = 0; rn < maxRows; ++rn) {
        const uint16_t eepromAddressOffset = rn * EEPROM_RIO_HOUSEKEEPING_SETTINGS_STEP;
        houseKeepingAdcMask[rn] = 0;
        houseKeepingAdcMask[rn] = eeprom_read_byte((const uint8_t*)(EEPROM_RIO_HOUSEKEEPING_0_ADC_MASK + eepromAddressOffset));
        uint16_t ns = eeprom_read_word((const uint16_t*)(EEPROM_RIO_HOUSEKEEPING_0_NUM_SAMPLES + eepromAddressOffset));
        housekeepingNumSamples[rn] = (ns == 0 || ns > maxSamples ? 1 : ns);  // Enforce sensible limits

        // Resolution is for the same for all ADCs (for timing reasons)
        uint8_t hkRes = eeprom_read_byte((const uint8_t*)(EEPROM_RIO_HOUSEKEEPING_0_ADC_RESOLUTION + eepromAddressOffset));

        for (uint8_t cn = 0; cn < maxNumAdcs; ++cn) {
            const uint8_t bitMask = 1 << cn;
            if (adcPresent[cn] && (houseKeepingAdcMask[rn] & bitMask)) {
                // ADC present and the EEPROM setting in the mask indicates this ADC is to be used.
                uint8_t channel = eeprom_read_byte((const uint8_t*)(EEPROM_RIO_HOUSEKEEPING_0_ADC_CHANNEL_LIST + eepromAddressOffset + cn));
                uint8_t gain = eeprom_read_byte((const uint8_t*)(EEPROM_RIO_HOUSEKEEPING_0_ADC_GAIN_LIST + eepromAddressOffset + cn));
                housekeepingConfig[rn][cn] = MCP342x::Config(channel, false, hkRes, gain);
            }
            else {
                // This won't be used to configure an ADC but set to sensible values anyway. It is important that the
                // configuration for cn=0 be correct for the resolution since this value is used to determine the
                // delay and timeout when reading the data back.
                housekeepingConfig[rn][cn] = MCP342x::Config(1, false, hkRes, 1);
            }

        }

    }

	tempConfig = MCP342x::Config(FLC100_TEMPERATURE_CHANNEL, false, 16, 1);
	return r;
}


void RioLogger::initGpio(void) const
{
    if (gpioAddress) {
        gpio.begin(gpioAddress & MCP23008_ADDRESS_MASK);
        // Make everything an input with a pullup
        for (uint8_t i = 0; i < 8; ++i) {
            gpio.pinMode(i, INPUT);
            gpio.pullUp(i, HIGH);
        }

        // Set the desired output pins
        for (uint8_t i = 1; i <= 5; ++i) {
            gpio.pinMode(i, OUTPUT);
            gpio.digitalWrite(i, LOW);
        }
    }
}


void RioLogger::process(void)
{
	static uint8_t rioNum; // sub-state number
	static uint8_t tmp = 0;
	static uint8_t sampleNum = 0;

	switch (state) {
	case off:
		break;

	case poweringUp:
		timestamp = 0;
		sensorTemperature = INT_MIN; // Clear previous readings
		for (uint8_t i = 0; i < getNumBeams(); ++i)
			data[i] = LONG_MIN;

        for (uint8_t rn = 0; rn < maxRows; ++rn)
            for (uint8_t cn = 0; cn < maxNumAdcs; ++cn)
            housekeepingData[rn][cn] = LONG_MIN;

		state = powerUpHold;
		break;

	case powerUpHold:
		if (delay.isExpired()) {
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
		setScanPins();
		presampleDelay.start(presampleDelay_ms, AsyncDelay::MILLIS);
		for (uint8_t i = 0; i < numColumns; ++i) {
			for (uint8_t j = 0; j < maxSamples; ++j)
				dataSamples[i][j] = LONG_MIN;
		}

		state = configuringHousekeepingADCs;
		break;

	case configuringHousekeepingADCs:
        // Write configuration to each ADC. Use tmp as flag to indicate a
		// failed configuration attempt (and therefore to use the timeout
		// delay).
		if (houseKeepingAdcMask[scanState] == 0) {
		    state = configuringRioADCs;
            rioNum = 0;
			tmp = 0;
			sampleNum = 0;
			break;
		}

		if (rioNum >= numColumns) {
			state = convertingHousekeepingADCs;
			rioNum = 0;
			tmp = 0;
			sampleNum = 0;
			break;
		}

		if ((houseKeepingAdcMask[scanState] & (1 << rioNum)) && (tmp == 0 ||!timeout.isExpired())) {
			// ADC present and, either no attempts made to configure this ADC
			// or still within the timeout period.
			if (adc[rioNum].configure(housekeepingConfig[scanState][rioNum]) == MCP342x::errorNone) {
				++rioNum;
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
			++rioNum;
		break;

    case convertingHousekeepingADCs:
		// Start conversions
		if (tmp == 0 || !timeout.isExpired()) {
			if (MCP342x::generalCallConversion() == 0) {
				// Conversion command succeeded, start the timers. Delay is
				// used to indicate when to first attempt reading the
				// results. Timeout is when to give up.

				unsigned long conversionTime = housekeepingConfig[scanState][0].getConversionTime();

				delay.start(conversionTime, AsyncDelay::MICROS);
				timeout.start(conversionTime + (conversionTime / 2), AsyncDelay::MICROS);
				// state = readingRioADCs;
				state = readingHousekeepingADCs;
				rioNum = 0;
				tmp = 0;
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
			// state = readingRioADCs;
			state = readingHousekeepingADCs;
			rioNum = 0;
			tmp = 0;
		}
		break;

    case readingHousekeepingADCs:
		if (sampleNum >= numSamples) {
			// Calculate final result
			aggregate(houseKeepingAdcMask[scanState], &(housekeepingData[scanState][0]));

            state = configuringRioADCs;
            rioNum = 0;
            tmp = 0;
			break;
		}

		if (rioNum >= numColumns) {
			++sampleNum;
			state = convertingHousekeepingADCs;
			rioNum = 0;
			tmp = 0;
			break;
		}

		if (!adcPresent[rioNum]) {
			++rioNum;
			break;
		}

		if (delay.isExpired()) {
			uint8_t err;
			MCP342x::Config status;
			long adcResult;

			err = adc[rioNum].read(adcResult, status);
			if (!err && status.isReady()) {
				// Have valid data
				MCP342x::normalise(adcResult, status);
				// Store the housekeeping results in the same array as used for the data. It will be aggregated before
				// the actual data is sampled.
				dataSamples[rioNum][sampleNum] = adcResult;
				++rioNum;
			}
			else if (timeout.isExpired()) {
				++rioNum;
			}
		}
		break;

	case configuringRioADCs:
		// Write configuration to each ADC. Use tmp as flag to indicate a
		// failed configuration attempt (and therefore to use the timeout
		// delay).
		if (rioNum >= numColumns) {
			state = presampleHold;
			rioNum = 0;
			tmp = 0;
			sampleNum = 0;
			break;
		}

		if (adcPresent[rioNum] && (tmp == 0 || !timeout.isExpired())) {
			// ADC present and, either no attempts made to configure this ADC
			// or still within the timeout period.
			if (adc[rioNum].configure(adcConfig[rioNum]) ==
				MCP342x::errorNone) {
				++rioNum;
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
			++rioNum;
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
				rioNum = 0;
				tmp = 0;
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
			rioNum = 0;
			tmp = 0;
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

		if (rioNum >= numColumns) {
			++sampleNum;
			state = convertingRioADCs;
			rioNum = 0;
			tmp = 0;
			break;
		}

		if (!adcPresent[rioNum]) {
			++rioNum;
			break;
		}

		if (delay.isExpired()) {
			uint8_t err;
			MCP342x::Config status;
			long adcResult;

			err = adc[rioNum].read(adcResult, status);
			if (!err && status.isReady()) {
				// Have valid data
				MCP342x::normalise(adcResult, status);
				dataSamples[rioNum][sampleNum] = adcResult;
				++rioNum;
			}
			else if (timeout.isExpired()) {
				++rioNum;
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
	for (uint8_t i = 0; i < numColumns; ++i) {
		if (!adcPresent[i])
			continue;

		if (useMedian)
			data[calcBeamNum(scanState, i)] = median<long>(dataSamples[i], numSamples);
		else {
			// Mean. Ignore any values which are LONG_MIN since they
			// represent sampling errors.
			long tmp = 0;
			long smallest, largest; // Initialised when first valid sample found
			uint8_t count = 0;
			for (uint8_t j = 0; j < numSamples; ++j) {
				if (dataSamples[i][j] != LONG_MIN) {
					// Sample is valid
					if (count) {
						if (dataSamples[i][j] < smallest)
							smallest = dataSamples[i][j];
						if (dataSamples[i][j] > largest)
							largest = dataSamples[i][j];
					}
					else
						largest = smallest = dataSamples[i][j];
					++count;
					tmp += dataSamples[i][j];
				}
				if (trimSamples && count >= 3) {
					// Remove largest and smallest values
					tmp = tmp - largest - smallest;
					count -= 2;
				}
				data[calcBeamNum(scanState, i)] = tmp / count;
			}
		}
	}
}


void RioLogger::aggregate(uint8_t useMask, long *results)
{
	for (uint8_t i = 0; i < numColumns; ++i) {
	    const uint8_t bitMask = 1 << i;
		if ((useMask & bitMask) == 0)
			continue;

		if (useMedian)
			results[i] = median<long>(dataSamples[i], numSamples);
		else {
			// Mean. Ignore any values which are LONG_MIN since they
			// represent sampling errors.
			long tmp = 0;
			long smallest, largest; // Initialised when first valid sample found
			uint8_t count = 0;
			for (uint8_t j = 0; j < numSamples; ++j) {
				if (dataSamples[i][j] != LONG_MIN) {
					// Sample is valid
					if (count) {
						if (dataSamples[i][j] < smallest)
							smallest = dataSamples[i][j];
						if (dataSamples[i][j] > largest)
							largest = dataSamples[i][j];
					}
					else
						largest = smallest = dataSamples[i][j];
					++count;
					tmp += dataSamples[i][j];
				}
				if (trimSamples && count >= 3) {
					// Remove largest and smallest values
					tmp = tmp - largest - smallest;
					count -= 2;
				}
				results[i] = tmp / count;
			}
		}
	}
}

void RioLogger::setScanPins() const
{
	const uint8_t val = scanMapping[scanState];
	uint8_t mask = 1;

	if (gpioAddress) {
	    uint8_t d = 0;
	    d |= ((val & 7) << 1); // Uses GPIO bits 1-3 inclusive
	    d |= ((scanState & 1) << 5); // Set status LED (GPIO bit 5)
	    gpio.writeGPIO(d);
	}

}


uint8_t RioLogger::copyHousekeepingData(uint8_t rowNum, int32_t *buffer, uint8_t bufferLen) const
{
    uint8_t r = 0;
    if (rowNum < numRows) {
        for (uint8_t i = 0; i < maxNumAdcs && r < bufferLen; ++i) {
            const uint8_t bitMask = 1 << i;
            if (houseKeepingAdcMask[rowNum] & bitMask)
                buffer[r++] = housekeepingData[rowNum][i];
        }
    }
    return r;

}

