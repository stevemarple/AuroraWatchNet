#ifndef MAG_CLOUD_H
#define MAG_CLOUD_H

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
#endif
