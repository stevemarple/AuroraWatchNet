#ifndef RIO_LOG_H
#define RIO_LOG_H

#define SD_SECTOR_SIZE 512

// #define SHOW_MEM_USAGE


#define EXPAND_STR(s) _MY_EXPAND_STR(s)
#define _MY_EXPAND_STR(s) #s

#if F_CPU == 8000000UL
#define F_CPU_STR "8MHz"
#elif F_CPU == 12000000UL
#define F_CPU_STR "12MHz"
#elif F_CPU == 16000000UL
#define F_CPU_STR "16MHz"
#elif F_CPU == 20000000UL
#define F_CPU_STR "20MHz"
#else
#error Unknown F_CPU value
#endif

// Signatures to identify actual MCU fitted
#ifdef __AVR__
#define DEVICE_SIG_ATMEGA1284P 0x1e9705
#define DEVICE_SIG_ATMEGA1284 0x1e9706
#define DEVICE_SIG_ATMEGA644P 0x1e960a
#define DEVICE_SIG_ATMEGA644  0x1e9609
#endif

#ifndef CPU_NAME
#ifdef __AVR__
#define CPU_NAME __AVR_DEVICE_NAME__
#else
#error Please define CPU_NAME
#endif
#endif


#endif
