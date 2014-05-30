# MagCloud

Arduino sketch for AuroraWatchNet magnetometer and cloud detector. It
uses CommsInterface to support the Ciseco XRF radio module and the
W5100 ethnernet module. RTCx is used to support common real-time
clocks, including the DS1338 and MCP7941x.

## Dependencies

The following dependencies are assumed:
  * Arduino IDE (v1.0)
  * Calunium hardware support for Arduino IDE, https://github.com/stevemarple/Calunium

All other dependencies are included as git submodules.

## Pin mapping

    0: RX0 XRF RX (via jumper) or console
	1: TX0 XRF TX (via jumper) or console
	2: RX1 XRF RX (via jumper)
	3: TX1 XRF TX (via jumper)
	4: (Reserved for Ethernet shield microSD CS)
	5: XRF /reset (via jumper)
	6: (Reserved for AS3935 lightning detector interrupt)
	7: XRF sleep (via jumper)
	8: Fan control
	9: MAX619 shutdown
	10: SS (Reserved for Ethernet shield WIZ5100 CS)
	11: MOSI (RFM12B etc)
	12: MISO (RFM12B etc)
	13: SCK (RFM12B etc) and LED
	14: (Reserved for AS3935 lightning detector SDA)
	15: RTC square-wave output
	16: JTAG TDI / MLX90614 software SDA
	17: JTAG TDO / (Reserved for AS3935 lightning detector SCL)
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

## Licence

Gnu GPL v2.