#include <avr/io.h>

#include "disable_jtag.h"


void disable_jtag(void)
{
  // Must run with interrupts off. Restore interrupt state afterwards.
  __asm__ __volatile__ (
			"in __tmp_reg__,__SREG__\n"
			"cli\n"
			"in  r24,%0\n"
			"ori r24,%1\n"
			"out %0,r24\n"
			"out %0,r24\n"
			"out __SREG__, __tmp_reg__\n" 
			// no outputs
			:
			// inputs are the constants MCUCR and _BV(JTD)
			: "I" (_SFR_IO_ADDR(MCUCR)),
			  "M" (1 << JTD)
			  // Clobber register 24
			: "r24"
			);
}

void enable_jtag(void)
{
  // Must run with interrupts off. Restore interrupt state afterwards.
  __asm__ __volatile__ (
			"in __tmp_reg__,__SREG__\n"
			"cli\n" 
			"in  r24,%0\n"
			"andi r24,%1\n"
			"out %0,r24\n"
			"out %0,r24\n"
			"out __SREG__, __tmp_reg__\n"
			// no outputs
			:
			// inputs are the constants MCUCR and _BV(JTD)
			: "I" (_SFR_IO_ADDR(MCUCR)),
			  "M" ((uint8_t)~(1 << JTD))
			  // Clobber register 24
			: "r24"
			);

}
