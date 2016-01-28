#ifndef CUSTOM_INCLUDE_H
#define CUSTOM_INCLUDE_H

// This file is used when compiling from the IDE to define
// communication hardware support. It is not used by the Makefile.
//#define COMMS_XRF
#define COMMS_W5100
//#define COMMS_W5500

#define FEATURE_FLC100

#define FEATURE_GNSS
#define FEATURE_VERBOSITY 1
#define FEATURE_MEM_USAGE

#if 1
// Include cloud detector sensors
#define FEATURE_HIH61XX
#define FEATURE_MLX90614
// #define FEATURE_AS3935
#endif


#endif
