# MagCloud firmware

Arduino-type firmware to support the magnetometer and/or cloud
detector. Due to RAM and flash memory requirements an ATmega1284,
ATmega1280 or better is required.

The firmware can be compiled with one or more support for one or
communication hardware types by defining the relevant preprocessor
macro(s), described below.

  ``COMMS_XRF``:
      Enable support for the Wireless Things (formeerly Ciseco) XRF radio
      module. The radio communicates with with Serial1 at 9600
      baud. 

  ``COMMS_W5100``:
      Enable support for the original Arduino Ethernet shield, based
      on the WIZNet W5100 Ethernet controller. The standard Arduino
      ``Ethernet`` library is used. If compiled for the ATmega1284(P)
      it will probably be necessary to modify the Ethernet library so
      that the SS pin is correctly defined.

  ``COMMS_W5500``:
      Enable support for the Arduino Ethernet2 shield, based on the
      WIZNet W5500 Ethernet controller. The ``Ethernet2`` library is
      used.


The firmware can also be built with different features enabled, by
defining the following preprocessor macros.

  ``FEATURE_AS3935``:
      Include support for Austrian Microsystems AS3935 lightning
      detector.  As it was not possible to persuade the lightning
      detector module to generate interrupts this feature has not been
      properly tested. This feature is unlikely to be compatible with
      ``FEATURE_AS3935`` due to limits on the number of hardware
      interrupts.

  ``FEATURE_FLC100``:
      Include support for FLC100 fluxgate magnetometer sensor(s)
      connected to MCP3424 ADC(s). Required for the magnetometer, not
      necessary for cloud detector.

  ``FEATURE_GNSS``:
      Use a GNSS module connected to Serial1 for timekeeping. It is
      expected that a pulse-per-second (PPS) signal is fed into one of
      the Arduino pins that includes interrupt capability. This
      feature is not compatible with ``COMMS_XRF`` as they both use
      the same serial port. This feature is unlikely to be compatible
      with ``FEATURE_AS3935`` due to limits on the number of hardware
      interrupts.

  ``FEATURE_HIH61XX``:
      Use a Honeywell HIH61xx humidity and temperature sensor as part
      of the cloud detection measurements. The HIH61xx is connected
      via any two digital I/O pins and uses the ``SoftWire`` library.

  ``FEATURE_MEM_USAGE``:
      Report the amount of free RAM available. Useful for tuning
      buffer sizes.

  ``FEATURE_MLX90614``:
      Use a Melexis MLX90614 infra-red temperature sensor for cloud
      detection. measurements.

  ``FEATURE_SD_CARD``:
      Save data to the SD card for later analysis. There is no method
      provided to copy the data from the card whilst the system is
      running. This feature was included in order to assess a site's
      geomagnetic suitability before installing a magnetometer and it
      is not intended as a production feature.

  ``FEATURE_VERBOSITY``:
      Override the initial verbosity setting with the value of the
      macro to alter the quantity and content of debug messages output.

