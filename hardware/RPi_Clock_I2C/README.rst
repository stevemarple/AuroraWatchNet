Clock and I2C magnetometer infterface for Raspberry Pi
======================================================

This small PCB adds a suitable logic-level interface to the Raspberry
Pi so that it can communicate directly with the AuroraWatchNet
magnetomter sensor head. This method provides a low-cost and easy to
deploy alternative to placing the sensor and microcontroller unit
outside, at the cost of greater temperature dependence and human
disturbance. The PCB also contains a ral-time clock which enables the
Raspberry Pi to start with the correct time when the NTP is unable
(such as when the network is down).

Warning
-------

This design has not been tested and the software to support it is not
yet written.

