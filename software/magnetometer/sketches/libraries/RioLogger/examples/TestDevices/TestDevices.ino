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

#include <avr/boot.h>
#include <avr/fuse.h>

#include "TestDevices.h"

#ifndef LED_BUILTIN
#define LED_BUILTIN 13
#endif

HIH61xx<TwoWire> hih(Wire);

HardwareSerial& console = Serial;

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


const char* createDeviceName(uint32_t deviceSignature)
{
	const char *deviceName = "Unknown MCU";

#if defined(__AVR_ATmega644__) || defined(__AVR_ATmega644P__) || defined(__AVR_ATmega1284__) || defined(__AVR_ATmega1284P__)
    switch (deviceSignature) {
        case DEVICE_SIG_ATMEGA644:
            deviceName = "atmega644";
            break;
        case DEVICE_SIG_ATMEGA644P:
            deviceName = "atmega644p";
            break;
        case DEVICE_SIG_ATMEGA1284:
            deviceName = "atmega1284";
            break;
        case DEVICE_SIG_ATMEGA1284P:
            deviceName = "atmega1284p";
            break;
    }
#endif
	return deviceName;
}


void setup(void)
{
    uint8_t count;
	uint32_t deviceSignature = 0;
	const char *deviceName = nullptr;

    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

#if F_CPU >= 12000000L
    console.begin(115200);
#else
    console.begin(9600);
#endif
    Wire.begin();

    generalCallReset();
    delay(200);
    generalCallLatch();
    delay(200);


    console.println();
    console.println(F("========"));

	// Print fuses
	uint8_t lowFuse = boot_lock_fuse_bits_get(GET_LOW_FUSE_BITS);
	uint8_t highFuse = boot_lock_fuse_bits_get(GET_HIGH_FUSE_BITS);
	uint8_t extendedFuse = boot_lock_fuse_bits_get(GET_EXTENDED_FUSE_BITS);

    // Get (and print) the signature of the actual device, not what the code was compiled for!
	for (uint8_t i = 0; i < 3; ++i) {
	    deviceSignature <<= 8;
    	deviceSignature |= (boot_signature_byte_get(i * 2) & 0xFF);
    }
	deviceName = createDeviceName(deviceSignature);

    console.print(F("Target MCU: "));
	console.println(F(EXPAND_STR(CPU_NAME)));

    console.print(F("Actual MCU: "));
	console.println(deviceName);

#ifdef __AVR__QQQ
	console.print(F("Signature: "));
	console.println(deviceSignature, HEX);
	console.print(F("Low fuse: "));
	console.println(lowFuse, HEX);
	console.print(F("High fuse: "));
	console.println(highFuse, HEX);
	console.print(F("Extended fuse: "));
	console.println(extendedFuse, HEX);


	// Is the internal RC oscillator in use? Programmed fuses read low
	uint8_t ckselMask = (uint8_t)~(FUSE_CKSEL3 & FUSE_CKSEL2 &
								   FUSE_CKSEL1 & FUSE_CKSEL0);
	bool isRcOsc = ((lowFuse & ckselMask) ==
					((FUSE_CKSEL3 & FUSE_CKSEL2 & FUSE_CKSEL0) & ckselMask));
	console.print(F("RC osc.: "));
	console.print(F("CKSEL: "));
	console.println((lowFuse & ckselMask), HEX);
	console.print(F("MCUSR: "));
	console.println(mcusrCopy, HEX);
	
#endif


	// Print the firmware version, clock speed and supported
	// communication protocols. Place in one long string to minimise
	// flash usage.
	console.print(F("MCU clock: "));
	console.print(F_CPU_STR);
	console.println();


    console.println(F("Scanning for RTC"));
    if (testDevicePresent(RTCx::PCF85263Address)) {
        console.print(F("Found PCF85263 RTC at 0x"));
        console.println(RTCx::PCF85263Address, HEX);
    }

    console.println(F("--------"));
    console.println(F("Scanning for MCP3424 devices"));
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
                    console.print(F("Device found at 0x"));
                    console.print(address, HEX);
                    console.println(F("    (probably MCP7941 RTC, not MCP3424)"));
                    tryConvert = false;
                }
                else {
                    console.print(F("Device found at 0x"));
                    console.print(address, HEX);
                    console.println(F("    (probably MCP3424, not MCP7941 RTC)"));
                }
            }
            else if (address == RTCx::DS1307Address) {
                console.print(F("Device found at 0x"));
                console.print(address, HEX);
                console.println(F("    (could be DS1307 or similar RTC)"));
            }
            else {
                console.print(F("Found MCP3424 at 0x"));
                console.println(address, HEX);
            }

            if (tryConvert) {
                console.println(F("    Attempting to read from ADC"));

                MCP342x adc(address);
                float volts;

                readAdc(adc, MCP342x::channel1, volts, Serial);
                readAdc(adc, MCP342x::channel4, volts, Serial);
                readAdc(adc, MCP342x::channel2, volts, Serial);
                if (i == 0) {
                    // Input voltage
                    console.print(F("    Input voltage is "));
                    console.print(volts * 5);
                    console.println(F(" V"));
                }
                if (i == 1) {
                    // Input voltage
                    console.print(F("    Supply voltage is "));
                    console.print(volts * 4);
                    console.println(F(" V"));
                }
                if (i == 2) {
                    // Input voltage
                    console.print(F("    Temperature is "));
                    console.print((volts - 0.6) * 100);
                    console.println(F(" Celsius"));
                }
            }

        }
        else {
            console.print(F("No device found at 0x"));
            console.println(address, HEX);
        }
    }
    console.print(F("Found "));
    console.print((int)count);
    console.println(F(" devices in the MCP3424 address list"));

    console.println(F("--------"));
    console.println(F("Scanning for MCP23008"));
    count = 0;

    for (uint8_t address = 0x20; address <= 0x27; ++address) {
        if (testDevicePresent(address)) {
            ++count;
            if (address == HIH61XX_DEFAULT_ADDRESS) {
                console.print(F("Device found at 0x"));
                console.print(address, HEX);
                console.println(F("    (could be HIH61xx)"));
            }
            else {
                console.print(F("Found MCP23008 at 0x"));
                console.println(address, HEX);
                Adafruit_MCP23008 gpio;
                console.println(F("    Toggling D5 to flash status LED"));
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
            console.print(F("No device found at 0x"));
            console.println(address, HEX);
        }
    }

    console.print(F("Found "));
    console.print((int)count);
    console.println(F(" devices in the MCP23008 address range"));

    console.println(F("--------"));
    console.println(F("Scanning for HIH61xx"));
    if (testDevicePresent(HIH61XX_DEFAULT_ADDRESS)) {
        console.print(F("Found device at 0x"));
        console.print(HIH61XX_DEFAULT_ADDRESS, HEX);
        console.println(F(", possibly HIH=H61xx or MCP23008, attempting to read"));
        if (hih.read()) {
            console.print("    Relative humidity: ");
            console.print(hih.getRelHumidity() / 100.0);
            console.println(" %");
            console.print("    Ambient temperature: ");
            console.print(hih.getAmbientTemp() / 100.0);
            console.println(" deg C");
            console.print("    Status: ");
            console.println(hih.getStatus());
        }
        else
            console.println(F("Could not read from HIH61xx"));
    }
    else
        console.println(F("HIH61xx not present"));

    console.println(F("--------"));
    console.println(F("Done"));
}


void loop(void)
{
    delay(10);
}

