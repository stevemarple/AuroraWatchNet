#ifndef RIO_LOGGER_H
#define RIO_LOGGER_H

#include <stdint.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <Adafruit_MCP23008.h>
#define MCP23008_ADDRESS_MASK ((uint8_t)7)
#define MCP23008_ADDRESS_MIN ((uint8_t)MCP23008_ADDRESS)
#define MCP23008_ADDRESS_MAX ((uint8_t)(MCP23008_ADDRESS | MCP23008_ADDRESS_MASK))

#define FLC100_POWER 9
#define FLC100_TEMPERATURE_CHANNEL 4


class RioLogger;


class RioLogger {
public:
	static const uint8_t maxRows = EEPROM_RIO_NUM_ROWS_MAX;
	static const uint8_t maxColumns = EEPROM_RIO_NUM_COLUMNS_MAX;
	static const uint8_t maxNumAdcs = maxRows;
	static const uint8_t maxNumBeams = maxRows * maxColumns;
	static const unsigned long defaultPowerUpDelay_ms = 1000;
	static unsigned long powerUpDelay_ms;
	static uint16_t presampleDelay_ms;
	static const uint8_t maxSamples = 16;
    static const uint8_t numScanPins = 3; // ceil(log2(EEPROM_RIO_NUM_ROWS_MAX))
    // static const uint8_t numScanStates = 8; // pow(2, numScanPins)
    static const uint8_t scanMapping7[7];
    static const uint8_t scanMapping8[8];

	RioLogger(void);

	inline bool isFinished(void) const {
		return state == finished;
    }

	inline bool isSampling(void) const {
		return !(state == off || state == finished);
    }

	inline void start(void) {
		state = poweringUp;
		digitalWrite(powerPin, HIGH);
		delay.start(powerUpDelay_ms, AsyncDelay::MILLIS);
	}

    inline uint8_t getNumRows(void) const {
        return numRows;
    }

    inline uint8_t getNumColumns(void) const {
        return numColumns;
    }

    inline uint8_t getNumBeams(void) const {
        return numRows * numColumns;
    }

	inline CounterRTC::time_t getTimestamp(void) const {
		return timestamp;
	}

	inline int16_t getSensorTemperature(void) const {
		return sensorTemperature;
	}

	inline bool getAdcPresent(uint8_t n) const {
		if (n >= maxNumAdcs)
			return false;
		return adcPresent[n];
	}

	inline const int32_t* getData(void) const {
		return magData;
	}

	inline const int32_t* getDataSamples(uint8_t mag) const {
		return magDataSamples[mag];
	}

	inline int32_t getDataSamples(uint8_t mag, uint8_t sampleNum) const {
		return magDataSamples[mag][sampleNum];
	}

	inline uint8_t getResGain(uint8_t mag) const {
		return (mag < maxNumAdcs) ? (adcConfig[mag] & 0x0F) : 0;
	}

	inline int getState(void) const {
		return state;
	}

	inline void getNumSamples(uint8_t &numSamp, bool &useMed,
							  bool &trimSamp) const {
		numSamp = numSamples;
		useMed = useMedian;
		trimSamp = trimSamples;
	}

	inline void setNumSamples(uint8_t numSamp, bool useMed, bool trimSamp) {
		if (numSamp > 0 && numSamp <= maxSamples) {
			numSamples = numSamp;
			useMedian = useMed;
			trimSamples = trimSamp;
		}
	}

    inline uint8_t calcBeamNum(uint8_t r, uint8_t c) const
    {
        return (r * numColumns) + c;
    }

	bool initialise(uint8_t pp, uint8_t adcAddressList[maxNumAdcs],
					uint8_t adcChannelList[maxNumAdcs],
					uint8_t adcResolutionList[maxNumAdcs],
					uint8_t adcGainList[maxNumAdcs]);
	void process(void);
	void finish(void);

private:

	enum state_t {
		off,
		poweringUp,
		powerUpHold,
		readingTime,
		advanceScan,
		convertingTemp,
		readingTemp,
		presampleHold,
		configuringRioADCs,
		convertingRioADCs,
		readingRioADCs,
		poweringDown,
		finished,
	};

    uint8_t gpioAddress;
	state_t state;
	uint8_t axis;
	uint8_t numRows;
	uint8_t numColumns;
	uint8_t powerPin;
	uint8_t scanState;
    uint8_t scanPins[numScanPins];
    const uint8_t *scanMapping;

	MCP342x adc[maxNumAdcs]; // X, Y, Z
	MCP342x::Config adcConfig[maxNumAdcs];
	MCP342x::Config tempConfig;
	bool adcPresent[maxNumAdcs];

	AsyncDelay delay;
	AsyncDelay timeout;
	AsyncDelay presampleDelay;

    mutable Adafruit_MCP23008 gpio;

	// Data fields
	CounterRTC::time_t timestamp;
	int16_t sensorTemperature; // hundredths of degrees Celsius
	int32_t magData[maxNumBeams];  // averaged from a number of samples
	int32_t magDataSamples[maxNumAdcs][maxSamples]; // individual results from one row

	uint8_t numSamples;
	bool useMedian;
	bool trimSamples;

    void initGpio(void) const;
	void aggregate(void);
    void setScanPins() const;

};


#endif
