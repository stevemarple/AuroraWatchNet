#include <AsyncDelay.h>
#include <Wire.h>
#include <RTCx.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <FLC100_shield.h>


const uint8_t outputPins[] = {5, // !XRF reset
			      7, // XRF sleep
			      SDA, SCL, // I2C interface
};
const uint8_t powerPin = 9;

void setup(void)
{
  Serial.begin(9600);
  for (uint8_t i = 0; i < sizeof(outputPins); ++i) {
    pinMode(outputPins[i], OUTPUT);
    digitalWrite(outputPins[i], LOW);
  }
  pinMode(powerPin, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
}


bool powerPinOn = false;

void loop(void)
{
  // TOGGLE the power pin
  digitalWrite(powerPin, powerPinOn);
  digitalWrite(LED_BUILTIN, powerPinOn);
  delay(100);
  powerPinOn = !powerPinOn;
  
  // Turn everything on, wait, then turn it off again and wait.
  for (uint8_t i = 0; i < 10; ++i) {
    for (uint8_t j = 0; j < sizeof(outputPins); ++j)
      digitalWrite(outputPins[j], (i % 2) == 0);
    delay(50);
  }
  
}
