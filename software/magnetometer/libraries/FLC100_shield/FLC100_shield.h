#ifndef FLC100_SHIELD_H
#define FLC100_SHIELD_H

#include <stdint.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
//#include <RTCx.h>
#include <CounterRTC.h>

#define XRF_RESET 5
#define XRF_SLEEP 7
#define FLC100_POWER 9
#define FLC100_TEMPERATURE_CHANNEL 4
// #define BATTERY_ADC 2
// #define MCU_VCC_Vx100 3300
// #define MCU_TEMPERATURE_ADC 7
// #define MCU_TEMPERATURE_PWR A6

// FET switch to ensure FLC100 really does go off
#define FLC100_DUMP_CHARGE_PIN 10

class FLC100;


class FLC100 {
public:
  static const uint8_t numAxes = 3;
  static const unsigned long defaultPowerUpDelay_ms = 1000;
  static unsigned long powerUpDelay_ms;
  static const uint8_t maxSamples = 16;
  
  FLC100(void);
  // inline bool initialise(uint8_t pp, uint8_t adcAddressList[numAxes],
  // 			 uint8_t adcChannelList[numAxes]) {
  //   // Use temporary variable to ensure both functions are always called
  //   bool r = i2cHandler.initialise(pp, adcAddressList, adcChannelList);
  //   return r;
  // }

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
      if (n >= numAxes)
	return false;
      return adcPresent[n];
  }

  inline const int32_t* getMagData(void) const {
    return magData;
  }

  inline const int32_t* getMagDataSamples(uint8_t mag) const {
    return magDataSamples[mag];
  }

  inline int32_t getMagDataSamples(uint8_t mag, uint8_t sampleNum) const {
    return magDataSamples[mag][sampleNum];
  }

  inline const uint8_t* getMagResGain(void) const {
    return magResGain;
  }

  inline const int getState(void) const {
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

  
  bool initialise(uint8_t pp, uint8_t adcAddressList[numAxes],
		  uint8_t adcChannelList[numAxes]);
  void process(void);
  void finish(void);

private:

  enum state_t {
    off,
    poweringUp,
    readingTime,
    convertingTemp,
    readingTemp,
    configuringMags,
    convertingMags,
    readingMags,
    poweringDown,
    finished,
  };

  state_t state;
  uint8_t axis;
  uint8_t powerPin;

  MCP342x adc[FLC100::numAxes]; // X, Y, Z
  MCP342x::Config adcConfig[FLC100::numAxes];
  MCP342x::Config tempConfig;
  bool adcPresent[FLC100::numAxes];
  uint8_t addresses[FLC100::numAxes];
  uint8_t channels[numAxes];

  AsyncDelay delay;
  AsyncDelay timeout;

  // Data fields
  //RTCx::time_t timestamp;
  CounterRTC::time_t timestamp;
  int16_t sensorTemperature; // hundredths of degrees Celsius
  int32_t magData[numAxes];  // averaged from a number of samples
  int32_t magDataSamples[numAxes][maxSamples]; // individual results
  uint8_t magResGain[numAxes];

  uint8_t numSamples;
  bool useMedian;
  bool trimSamples;

  void aggregate(void);
  
};


#endif
