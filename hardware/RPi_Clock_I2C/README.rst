Clock and I2C magnetometer infterface for Raspberry Pi
======================================================

This small PCB adds a suitable logic-level interface to the Raspberry
Pi so that it can communicate directly with the AuroraWatchNet
magnetometer sensor head. This method provides a low-cost and easy to
deploy alternative to placing the sensor and microcontroller unit
outside, at the cost of greater temperature dependence and more human
disturbances. The PCB also contains a real-time clock which enables
the Raspberry Pi to start with the correct time when the NTP not
available (such as when the network is down).

