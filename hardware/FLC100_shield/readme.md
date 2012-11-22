# FLC100_shield

Arduino shield for FLC100 magnetometer. A class supporting operation
of the board is provided in the software section of this repository.

## Description

The FLC100_shield supports the operation of the FLC100 magnetometer
for [AuroraWatchNet](http://aurorawatch.net/). The shield can be built
to operate in one of several modes.

* Using the remote FLC100 PCB, digital signals are sent to/from
  the board over I2C. The remote board generates the 5V supply whilst
  the FLC100 shield generates the 3.3V supply. The MCP3424 ADC resides
  on the remote board. This mode allows the sensor and critical
  analogue electronics to be located in a temperature-stabilised
  location (eg buried). Two or three axis operation is possible by
  configuring the MCP3424 ADCs to use different I2C addresses. This is
  the intended mode of operation.
* Fully self-contained, with the FLC100 and MCP3424 ADC located
  on-board. The shield provides both 3.3V and 5V supplies from an
  external 3V battery. This mode is the most compact but may expose
  the sensor to higher temperature variations and stray magnetic
  interference.
* Using the remote FLC100 PCB, analogue signals are sent to the
  MCP3424 ADC on the shield. This mode is likely to result in
  sub-optimal performance and was provided in case of difficulties
  driving I2C signals over the required distance; the concern appears
  unfounded.


