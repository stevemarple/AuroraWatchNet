/*
 * Test sketch to list the I2C devices.
 */

#include <Wire.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CounterRTC.h>
#include <AwEeprom.h>
#include <FLC100_shield.h>


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


void setup(void)
{
    Serial.begin(9600);
    Wire.begin();

	// Turn on 5V supply
	pinMode(FLC100_POWER, OUTPUT);
	digitalWrite(FLC100_POWER, HIGH);
	delay(FLC100::powerUpDelay_ms);

	Serial.println("The MCP3422 and MCP3426 use I2C address 0x68, all other devices can be");
	Serial.println("configured to use any address in the range 0x68 - 0x6F (inclusive).");
	Serial.println("Be aware that the DS1307 uses address 0x68.");
	Serial.println();

	generalCallReset();
	generalCallLatch();

	for (uint8_t add = 0X0; add < 0X80; add++) {
		//Serial.print("Trying ");
		//Serial.println(add);
		Wire.requestFrom(add, (uint8_t)1);
		if (Wire.available()) {
			Serial.print("Found device at: 0x");
			Serial.println(add, HEX);
		}
	}
	Serial.println("Done");
}

void loop(void)
{
	;
}
