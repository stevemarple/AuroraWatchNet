#include <AsyncDelay.h>
#include <Wire.h>
#include <RTCx.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <FLC100_shield.h>


// List of possible addresses for the ADC; 0x68 and 0x6F omitted since
// they clash with the address used by the DS1307 and similar
// real-time clocks and the MCP7941x.
const uint8_t numAddresses = 6;
const uint8_t adcAddressList[numAddresses] = {0x6E, 0x6A, 0x6C,  // Normal X, Y, Z
					      0x69, 0x6B, 0x6D}; // Other options
bool haveMCP342x[numAddresses];
MCP342x adc[numAddresses];
uint8_t found = 0;

uint8_t xrfSleepState = 0;
uint8_t xrfResetState = 1;
uint8_t adcPowerState = 1;

void setup(void)
{
  Serial.begin(9600);
  Serial1.begin(9600);
  Wire.begin();

  pinMode(XRF_RESET, OUTPUT);
  digitalWrite(XRF_RESET, xrfResetState);

  pinMode(XRF_SLEEP, OUTPUT);
  digitalWrite(XRF_SLEEP, xrfSleepState);

  pinMode(FLC100_POWER, OUTPUT);
  digitalWrite(FLC100_POWER, adcPowerState);
  
  pinMode(22, INPUT); // XRF On indicator
  // Turn on 5V supply so that the ADC can be probed
  adcPowerState = 1;
  digitalWrite(FLC100_POWER, adcPowerState);

  // Reset all MCP342x devices
  MCP342x::generalCallReset();
  delay(100);
  for (uint8_t i = 0; i < numAddresses; ++i)
    haveMCP342x[i] = adc[i].autoprobe(&adcAddressList[i], 1);

  // Print out found and missing, group
  for (uint8_t i = 0; i < numAddresses; ++i)
    if (haveMCP342x[i]) {
      Serial.print("Detected ADC at 0x");
      Serial.println(adcAddressList[i], HEX);
      ++found;
    }

  for (uint8_t i = 0; i < numAddresses; ++i)
    if (!haveMCP342x[i]) {
      Serial.print("Did not detect ADC at 0x");
      Serial.println(adcAddressList[i], HEX);
    }



}


const uint8_t bufLen = 30;
char buffer[bufLen + 1] = {'\0'};
uint8_t bufPos = 0;
unsigned long last = 0;
MCP342x::Gain gain = MCP342x::gain1;

void loop(void)
{
  while (Serial.available()) {
    char c = Serial.read();
    if ((c == '\r' || c == '\n')) {
      buffer[bufPos] = '\0';
      if (bufPos <= bufLen) {
	if (strcmp_P(buffer, PSTR("adcpower")) == 0) { 
	  adcPowerState = !adcPowerState;
	  digitalWrite(FLC100_POWER, adcPowerState);
	}
	else if (strcmp_P(buffer, PSTR("xrfsleep")) == 0) {
	  xrfSleepState = !xrfSleepState;
	  digitalWrite(XRF_SLEEP, xrfSleepState);
	}
	else if (strcmp_P(buffer, PSTR("xrfreset")) == 0) {
	  xrfResetState = !xrfResetState;
	  digitalWrite(XRF_RESET, xrfResetState);
	}
	else if (strcmp_P(buffer, PSTR("gain1")) == 0) {
	  gain = MCP342x::gain1;
	}
	else if (strcmp_P(buffer, PSTR("gain2")) == 0) {
	  gain = MCP342x::gain2;
	}
	else if (strcmp_P(buffer, PSTR("gain4")) == 0) {
	  gain = MCP342x::gain4;
	}
	else if (strcmp_P(buffer, PSTR("gain8")) == 0) {
	  gain = MCP342x::gain8;
	}
	else if (strcmp_P(buffer, PSTR("+++")) == 0) {
	  Serial1.print("+++");
	}
	else if (strncmp_P(buffer, PSTR("AT"), 2) == 0) {
	  Serial1.print(buffer);
	  Serial1.print("\r");
	}
	else {
	  Serial.print(buffer);
	  Serial.println(": ERROR");
	}
      }
      bufPos = 0;
    }
    else if (bufPos < bufLen)
      // Store character
      buffer[bufPos++] = c; 
  }

  while (Serial1.available())
    Serial.print((char)Serial1.read());
  
  if (millis() - last > 2000) {
    last = millis();
    Serial.println("--------------");
    Serial.print("ADC power: ");
    Serial.println(adcPowerState ? '1' : '0');
    Serial.print("ADC gain: ");
    Serial.print((1 << gain), DEC);
    Serial.println('x');
    Serial.print("XRF sleep: ");
    Serial.println(xrfSleepState ? '1' : '0');
    Serial.print("XRF reset: ");
    Serial.println(xrfResetState ? '1' : '0');
    Serial.print("XRF is on: ");
    Serial.println(digitalRead(22) ? '1' : '0');

    Serial.print("Vin: ");
    Serial.print((3.3 * analogRead(BATTERY_ADC)) / 1024);
    Serial.println(" V");
    if (adcPowerState) {
      float total = 0.0;
      for (uint8_t i = 0; i < numAddresses; ++i) {
	if (haveMCP342x[i]) {
	  // Sample channel 0
	  int32_t x;
	  MCP342x::Config status;
	  adc[i].convertAndRead(MCP342x::channel1, MCP342x::oneShot,
				MCP342x::resolution18, gain,
				300000UL, x, status);
	  Serial.print("ADC 0x");
	  Serial.print(adcAddressList[i], HEX);
	  Serial.print(": ");
	  Serial.println(x);
	  total += (double(x) * double(x));
	}
      }
      if (found == 3) {
	Serial.print("Total: ");
	Serial.println(sqrt(total));
      }
    }
    
  }
  
  
}

