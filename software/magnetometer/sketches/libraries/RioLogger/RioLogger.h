#ifndef RIO_LOGGER_H
#define RIO_LOGGER_H

#include <stdint.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CounterRTC.h>

#define FLC100_POWER 9
#define FLC100_TEMPERATURE_CHANNEL 4


class RioLogger;


class RioLogger {
public:
	static const uint8_t maxRows = 8;
	static const uint8_t maxColumns = 8;
	static const uint8_t maxNumAdcs = maxRows;
	static const unsigned long defaultPowerUpDelay_ms = 1000;
	static unsigned long powerUpDelay_ms;
	static uint16_t presampleDelay_ms;
	static const uint8_t maxSamples = 16;
    static const uint8_t numScanPins = 3;
    static const uint8_t numScanStates = 8; // pow(2, numScanPins)
    static const uint8_t scanMapping[numScanStates];

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

	state_t state;
	uint8_t axis;
	uint8_t powerPin;
	uint8_t scanState;
    uint8_t scanPins[numScanPins];

	MCP342x adc[maxNumAdcs]; // X, Y, Z
	MCP342x::Config adcConfig[maxNumAdcs];
	MCP342x::Config tempConfig;
	bool adcPresent[maxNumAdcs];

	AsyncDelay delay;
	AsyncDelay timeout;
	AsyncDelay presampleDelay;

	// Data fields
	CounterRTC::time_t timestamp;
	int16_t sensorTemperature; // hundredths of degrees Celsius
	int32_t magData[maxNumAdcs];  // averaged from a number of samples
	int32_t magDataSamples[maxNumAdcs][maxSamples]; // individual results

	uint8_t numSamples;
	bool useMedian;
	bool trimSamples;

	void aggregate(void);
    void setScanPins() const;

};


#endif
