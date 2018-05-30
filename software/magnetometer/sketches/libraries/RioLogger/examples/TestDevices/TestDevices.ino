#include <stdint.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <Adafruit_MCP23008.h>
#include <RTCx.h>
#include <HIH61xx.h>
#include <RioLogger.h>


#ifndef LED_BUILTIN
#define LED_BUILTIN 13
#endif


uint8_t generalCallReset(void)
{
	Wire.beginTransmission(0x00);
	Wire.write(0x06);
	return Wire.endTransmission();
}

uint8_t generalCallLatch(void)
{
	Wire.beginTransmission(0x00);
	Wire.write(0x04);
	return Wire.endTransmission();
}


bool testDevicePresent(uint8_t address)
{
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    Wire.requestFrom(address, (uint8_t)1);
    digitalWrite(LED_BUILTIN, LOW);
    return Wire.available();
}


void setup(void)
{
    uint8_t count;

    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

#if F_CPU >= 12000000L
    Serial.begin(115200);
#else
    Serial.begin(9600);
#endif
    Wire.begin();

    generalCallReset();
    delay(200);
    generalCallLatch();
    delay(200);


    Serial.println();
    Serial.println(F("========"));

    Serial.println(F("Scanning for RTC"));
    if (testDevicePresent(RTCx::PCF85263Address)) {
        Serial.print(F("Found PCF85263 RTC at 0x"));
        Serial.println(RTCx::PCF85263Address, HEX);
    }

    Serial.println(F("--------"));
    Serial.println(F("Scanning for MCP3424 devices"));
    count = 0;
    uint8_t adcAddresses[8] = {0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F};
    for (uint8_t i = 0; i < sizeof(adcAddresses)/sizeof(adcAddresses[0]); ++i) {
        uint8_t address = adcAddresses[i];
        if (testDevicePresent(address)) {
            ++count;
            if (address == RTCx::MCP7941xAddress) {
                // Check if the associated EEPROM address present
                if (testDevicePresent(RTCx::MCP7941xEepromAddress)) {
                    Serial.print(F("Device found at 0x"));
                    Serial.print(address, HEX);
                    Serial.println(F("    (probably MCP7941 RTC, not MCP3424)"));
                }
                else {
                    Serial.print(F("Device found at 0x"));
                    Serial.print(address, HEX);
                    Serial.println(F("    (probably MCP3424, not MCP7941 RTC)"));
                }
            }
            else if (address == RTCx::DS1307Address) {
                Serial.print(F("Device found at 0x"));
                Serial.print(address, HEX);
                Serial.println(F("    (could be DS1307 or similar RTC)"));
            }
            else {
                Serial.print(F("Found MCP3424 at 0x"));
                Serial.println(address, HEX);
            }
        }
        else {
            Serial.print(F("No device found at 0x"));
            Serial.println(address, HEX);
        }
    }
    Serial.print(F("Found "));
    Serial.print((int)count);
    Serial.println(F(" devices in the MCP3424 address list"));

    Serial.println(F("--------"));
    Serial.println(F("Scanning for MCP23008"));
    count = 0;

    for (uint8_t address = 0x20; address <= 0x27; ++address) {
        if (testDevicePresent(address)) {
            ++count;
            if (address == HIH61xx::defaultAddress) {
                Serial.print(F("Device found at 0x"));
                Serial.print(address, HEX);
                Serial.println(F("    (could be HIH61xx)"));
            }
            else {
                Serial.println(F("Found MCP23008 at 0x"));
                Serial.println(address, HEX);
            }
        }
        else {
            Serial.print(F("No device found at 0x"));
            Serial.println(address, HEX);
        }
    }

    Serial.print(F("Found "));
    Serial.print((int)count);
    Serial.println(F(" devices in the MCP23008 address range"));

    Serial.println(F("--------"));
    Serial.println(F("Scanning for HIH61xx"));
    if (testDevicePresent(HIH61xx::defaultAddress)) {
        Serial.print(F("Found device at 0x"));
        Serial.print(HIH61xx::defaultAddress, HEX);
        Serial.print(F(", possibly HIH=H61xx or MCP23008"));
    }
    else
        Serial.println(F("HIH61xx not present"));

    Serial.println(F("--------"));
    Serial.println(F("Done"));
}


void loop(void)
{
    delay(10);
}

