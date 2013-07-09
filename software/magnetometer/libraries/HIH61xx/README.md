HIH61xx
=======

HIH61xx is a library for accessing the humidity and temperature data
from the I2C range of Honeywell HIH61xx humidity sensors (HIH6120-021,
HIH6121-021, HIH6130-021 and HIH6131-021). Do not confuse these
sensors with the SPI versions (HIH6130-000 and HIH6131-000).

Software I2C is used to allow this sensor to be connected to any two
digital pins. An optional power pin can be used to control power to
the device. A state machione ensures the relevant timing constraints
are observed.


Requirements
------------

The following libraries are required
    AsyncDelay: see https://github.com/stevemarple/AsyncDelay
    SoftWire: see https://github.com/stevemarple/SoftWire

Examples
--------

The HIH61xx_demo sketch demonstrates the state machine operation.

License
-------

The HIH61xx library is released under the GNU Lesser General Public
License, version 2.1. See LICENSE.txt for details.
