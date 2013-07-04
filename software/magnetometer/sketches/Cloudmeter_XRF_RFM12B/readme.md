# AWN_XRF_RFM12B

Arduino sketch for AuroraWatchNet magnetometer. It uses CommsInterface to Support both the Ciseco
XRF and Hope RFM12B radio modules for wireless communication. RTCx is used to support common 
real-time clocks, including DS1338 and MCP7941x.

## Dependencies

The following dependencies are assumed:
  * Arduino IDE (v1.0)
  * Calunium hardware support for Arduino IDE, ttps://github.com/stevemarple/Calunium

All other dependencies are included as git submodules.

## Pin mapping

    0: RX0 XRF RX (via jumper) or console
	1: TX0 XRF TX (via jumper) or console
	2: RX1 XRF RX (via jumper)
	3: TX1 XRF TX (via jumper)
	4: (Reserved for Ethernet shield microSD CS)
	5: XRF /reset (via jumper)
	6: RTC / RFM12B radio (selected by jumper)
	7: XRF sleep (via jumper)
	8: 
	9: MAX619 shutdown
	10: SS (Reserved for Ethernet shield WIZ5100 CS)
	11: MOSI (RFM12B etc)
	12: MISO (RFM12B etc)
	13: SCK (RFM12B etc) and LED
	14: RFM12B radio module CS
	15: RTC square-wave output
	16: JTAG TDI / MLX90614 software SDA
	17: JTAG TDO 
	18: JTAG TMS / MLX90614 power
	19: JTAG TCK / MLX90614 software SCL
	20: SDA (RTC, MCP3424 etc)
	21: SCL (RTC, MCP3424 etc)
	22: Calunium microSD CS
	23: XRF on indicator
	A0: 
	A1:
	A2: Vin voltage measurement (via jumper)
	A3: 
	A4: (Reserved, SDA on Arduino Uno)
	A5: (Reserved, SCL on Arduino Uno)
	A6: LM61 power
	A7: LM61 output

## I2C addresses

	DS1307: 0x68
	MCP7941x (RTC): 0x6F
	MCP7941x (EEPROM): 0x57
	MCP3424: configurable to be one of 0x68 - 0x6F
    HIH6120, HIH6121, HIH6130, HIH6131: 0x27

## Licence

Gnu GPL v2.
