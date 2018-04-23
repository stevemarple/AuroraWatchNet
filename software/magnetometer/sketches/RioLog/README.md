# RioLog firmware

Arduino sketch for riometer logger,  based on `MagCloud` sketch. Due to
RAM and flash memory requirements an ATmega1284, ATmega1280 or better
is required. It uses `CommsInterface` to support the Ciseco XRF radio
module and the W5100 Ethernet module. `RTCx` is used to support common
real-time clocks, including the DS1338 and MCP7941x.

## Dependencies

The following dependencies are assumed:

  * Arduino IDE (v1.6+)
  * Calunium hardware support for Arduino IDE, https://github.com/stevemarple/Calunium

All other dependencies are included as git submodules.

## Communication methods

The firmware can be compiled with support for one or more
communication hardware types by defining the relevant preprocessor
macro(s), described below.

  * `COMMS_XRF`

    Enable support for the Wireless Things (formeerly Ciseco) XRF radio
    module. The radio communicates with with Serial1 at 9600
    baud.

  * `COMMS_W5100`

    Enable support for the original Arduino Ethernet shield, based
    on the WIZNet W5100 Ethernet controller. The standard Arduino
    `Ethernet` library is used. If compiled for the ATmega1284(P)
    it will probably be necessary to modify the Ethernet library so
    that the `SS` pin is correctly defined.

  * `COMMS_W5500`

    Enable support for the Arduino Ethernet2 shield, based on the
    WIZNet W5500 Ethernet controller. The `Ethernet2` library is
    used.

## Firmware features

Various features may be enabled by defining the appropriate compiler macro
as described below.

  * `FEATURE_AS3935`

    Include support for Austrian Microsystems AS3935 lightning
    detector.  As it was not possible to persuade the lightning
    detector module to generate interrupts this feature has not been
    properly tested. This feature is unlikely to be compatible with
    `FEATURE_AS3935` due to limits on the number of hardware
    interrupts.

  * `FEATURE_DATA_QUALITY`

	Include support for a pin which monitors and reports on possible
	data quality problems. The pin could be connected to an external
	switch used to indicate when local site disturbances are expected.

  * `FEATURE_FLC100`

    Include support for FLC100 fluxgate magnetometer sensor(s)
    connected to MCP3424 ADC(s). Required for the magnetometer, not
    necessary for cloud detector.

  * `FEATURE_GNSS`

    Use a GNSS module connected to Serial1 for timekeeping. It is
    expected that a pulse-per-second (PPS) signal is fed into one of
    the Arduino pins that includes interrupt capability. This
    feature is not compatible with `COMMS_XRF` as they both use
    the same serial port. This feature is unlikely to be compatible
    with `FEATURE_AS3935` due to limits on the number of hardware
    interrupts.

  * `FEATURE_HIH61XX`

    Use a Honeywell HIH61xx humidity and temperature sensor as part
    of the cloud detection measurements. The HIH61xx is connected
    via any two digital I/O pins and uses the `SoftWire` library.

  * `FEATURE_MEM_USAGE`

    Report the amount of free RAM available. Useful for tuning
    buffer sizes.

  * `FEATURE_MLX90614`

    Use a Melexis MLX90614 infra-red temperature sensor for cloud
    detection. measurements.

  * `FEATURE_SD_CARD`

    Save data to the SD card for later analysis. There is no method
    provided to copy the data from the card whilst the system is
    running. This feature was included in order to assess a site's
    geomagnetic suitability before installing a magnetometer and it
    is not intended as a production feature.

  * `FEATURE_VERBOSITY`

    Override the initial verbosity setting with the value of the
    macro to alter the quantity and content of debug messages output.


## Pin mapping

Pin numbers refer to the Calunium pin.

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
