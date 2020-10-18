#ifndef RIO_LOGGER_H
#define RIO_LOGGER_H

#define RIO_LOGGER_VERSION "0.1.0"

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
	static const uint8_t maxNumAdcs = maxColumns;
	static const uint8_t maxNumBeams = maxRows * maxColumns;
	static const unsigned long defaultPowerUpDelay_ms = 1000;
	static unsigned long powerUpDelay_ms;
	static uint16_t presampleDelay_ms;
	static const uint8_t maxSamples = 16;
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

	inline bool getAdcPresent(uint8_t n) const {
		if (n >= maxNumAdcs)
			return false;
		return adcPresent[n];
	}

	inline const int32_t* getData(void) const {
		return data;
	}

	inline const int32_t* getDataSamples(uint8_t rio) const {
		return dataSamples[rio];
	}

	inline int32_t getDataSamples(uint8_t rio, uint8_t sampleNum) const {
		return dataSamples[rio][sampleNum];
	}

    inline const int32_t* getHousekeepingData(uint8_t rowNum) const {
        return housekeepingData[rowNum];
    }

    // Copy the housekeeping data to an external array, only taking results from the ADCs sampled.
    // Returns number of values copied (will not exceed bufferLen)
    uint8_t copyHousekeepingData(uint8_t rowNum, int32_t *buffer, uint8_t bufferLen) const;

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
	
	inline uint8_t getScanState(void) const {
		return scanState;
	};

	inline bool isScanFrozen(void) const {
		// Use maxRows here. This allows a 7x7 riometer system to have
		// a dummy 8th scan state that connects to riometers to a
		// noise source.
		return freezeScan < maxRows;
	}

	inline uint8_t getFreezeScan(void) const {
		return freezeScan;
	};

	inline void setFreezeScan(uint8_t freezeScanAtState) {
		freezeScan = freezeScanAtState;
	};

	inline bool isRioConnected(void) const {
		return rioConnected;
	}

	inline void setRioConnected(bool c) {
		rioConnected = c;
	}

private:

	enum state_t {
		off,
		poweringUp,
		powerUpHold,
		readingTime,
		advanceScan,
        configuringHousekeepingADCs,
        convertingHousekeepingADCs,
        readingHousekeepingADCs,
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
    uint8_t scanMapping[maxRows];

	MCP342x adc[maxNumAdcs]; // X, Y, Z
	MCP342x::Config adcConfig[maxNumAdcs];
	MCP342x::Config housekeepingConfig[maxRows][maxNumAdcs];
	MCP342x::Config tempConfig;
	bool adcPresent[maxNumAdcs];

    // Use a bitmask to indicate which ADCs are to be sampled for housekeeping data at each stage (LSB is first ADC).
    // This can be set for each row of the scan. This matches how the settings are stored in EEPROM.
    uint8_t adcMask;
    uint8_t houseKeepingAdcMask[maxRows];


    static_assert(maxNumAdcs <= 8 * sizeof(houseKeepingAdcMask[0]), "Not enough bits in houseKeepingAdcMask type");

	AsyncDelay delay;
	AsyncDelay timeout;
	AsyncDelay presampleDelay;

    mutable Adafruit_MCP23008 gpio;

	// Data fields
	CounterRTC::time_t timestamp;
	int32_t data[maxNumBeams];  // averaged from a number of samples
	int32_t dataSamples[maxNumAdcs][maxSamples]; // individual results from one row

    // Housekeeping data. One set of housekeeping data can be sampled (once, no oversampling) during the settling
    // time of the riometers.
    int32_t housekeepingData[maxRows][maxNumAdcs];

	uint8_t numSamples;
	uint8_t housekeepingNumSamples[maxRows];

	bool useMedian;
	bool trimSamples;
	uint8_t freezeScan;
	bool rioConnected;

    void initGpio(void) const;
	void aggregate(void);
	void aggregate(uint8_t useMask, long *results);
    void setScanPins() const;
};


#endif
