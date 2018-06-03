#include <stdint.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <Adafruit_MCP23008.h>
#include <RTCx.h>
#include <Wire.h>
#include <HIH61xx.h>
#include <RioLogger.h>


#ifndef LED_BUILTIN
#define LED_BUILTIN 13
#endif

HIH61xx<TwoWire> hih(Wire);

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


bool readAdc(MCP342x &adc, MCP342x::Channel channel, float &volts, Stream &s)
{
    const long timeout_us = 1000000L;
    const MCP342x::Resolution res = MCP342x::resolution18;
    long value = 0;
    MCP342x::Config status;

    if (adc.convertAndRead(channel, MCP342x::oneShot, res, MCP342x::gain1, timeout_us, value, status) == 0) {
        long normCounts = value;
        MCP342x::normalise(normCounts, status);
        volts = float(normCounts) * (2.048 / float(1L << 20));

        s.print(F("    Value of channel "));
        s.print((int)channel);
        s.print(F(" is "));
        s.print(volts);
        s.print(F(" V ("));
        s.print(value);
        s.println(F(" counts)"));
        return true;
    }
    else {
        s.println(F("Failed to read ADC"));
        return false;
    }
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
            bool tryConvert = true;
            ++count;
            if (address == RTCx::MCP7941xAddress) {
                // Check if the associated EEPROM address present
                if (testDevicePresent(RTCx::MCP7941xEepromAddress)) {
                    Serial.print(F("Device found at 0x"));
                    Serial.print(address, HEX);
                    Serial.println(F("    (probably MCP7941 RTC, not MCP3424)"));
                    tryConvert = false;
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

            if (tryConvert) {
                Serial.println(F("    Attempting to read from ADC"));

                MCP342x adc(address);
                float volts;

                readAdc(adc, MCP342x::channel1, volts, Serial);
                readAdc(adc, MCP342x::channel4, volts, Serial);
                readAdc(adc, MCP342x::channel2, volts, Serial);
                if (i == 0) {
                    // Input voltage
                    Serial.print(F("    Input voltage is "));
                    Serial.print(volts * 5);
                    Serial.println(F(" V"));
                }
                if (i == 1) {
                    // Input voltage
                    Serial.print(F("    Supply voltage is "));
                    Serial.print(volts * 4);
                    Serial.println(F(" V"));
                }
                if (i == 2) {
                    // Input voltage
                    Serial.print(F("    Temperature is "));
                    Serial.print((volts - 0.6) * 100);
                    Serial.println(F(" Celsius"));
                }
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
            if (address == HIH61XX_DEFAULT_ADDRESS) {
                Serial.print(F("Device found at 0x"));
                Serial.print(address, HEX);
                Serial.println(F("    (could be HIH61xx)"));
            }
            else {
                Serial.print(F("Found MCP23008 at 0x"));
                Serial.println(address, HEX);
                Adafruit_MCP23008 gpio;
                Serial.println(F("    Toggling D5 to flash status LED"));
                delay(100);
                const uint8_t statusLed = 5;
                gpio.begin(address & 0x07);
                gpio.pinMode(statusLed, OUTPUT);
                for (uint8_t flash = 0; flash < 10; ++flash) {
                    const int duration = 500;
                    gpio.digitalWrite(statusLed, HIGH);
                    delay(duration);
                    gpio.digitalWrite(statusLed, LOW);
                    delay(duration);
                }
                gpio.pinMode(statusLed, INPUT);  // Restore to default pin state
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
    if (testDevicePresent(HIH61XX_DEFAULT_ADDRESS)) {
        Serial.print(F("Found device at 0x"));
        Serial.print(HIH61XX_DEFAULT_ADDRESS, HEX);
        Serial.println(F(", possibly HIH=H61xx or MCP23008, attempting to read"));
        if (hih.read()) {
            Serial.print("    Relative humidity: ");
            Serial.print(hih.getRelHumidity() / 100.0);
            Serial.println(" %");
            Serial.print("    Ambient temperature: ");
            Serial.print(hih.getAmbientTemp() / 100.0);
            Serial.println(" deg C");
            Serial.print("    Status: ");
            Serial.println(hih.getStatus());
        }
        else
            Serial.println(F("Could not read from HIH61xx"));
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

