#include <avr/eeprom.h>
#include <avr/pgmspace.h>
#include <avr/wdt.h>
#include <stdlib.h>
#include <string.h>

#include <Arduino.h>
#include <Streaming.h>
#include <CounterRTC.h>
#include <AWPacket.h>
#include <AwEeprom.h>
#include "CommandHandler.h"

extern uint8_t sdSelect;
extern CounterRTC::Time samplingInterval;
extern const CounterRTC::Time minSamplingInterval;
extern const CounterRTC::Time maxSamplingInterval;
extern uint8_t verbosity;

#if USE_SD_CARD
extern bool useSd;
#endif


bool startsWith_P(const char *match, const char *str, char **ep)
{
  char c;
  while ((c = pgm_read_byte_far((uint_farptr_t)match)) != '\0') {
    if (*str++ != c)
      return false;
    else
      ++match;
  }
  if (ep)
    *ep = (char*)str;
  return true;
}


// bool CommandHandler::checkTime(RTCx::time_t t, RTCx::time_t &err)
// {
//   struct RTCx::tm tm;
//   if (rtc.readClock(tm)) {
//     RTCx::time_t now = RTCx::mktime(tm);
//     err = now - t;
//     return true;
//   }
//   return false;
// }


// bool CommandHandler::setTime(RTCx::time_t t)
// {
//   struct RTCx::tm tm;
//   RTCx::gmtime_r(&t, &tm);
//   AWPacket::incrementDefaultSequenceId();
  
//   // Time changing so increment the sequenceId to prevent replay
//   // attacks. Normally the timestamp is increasing but it is possible
//   // that it has decreased slightly, giving an attacker a potential
//   // opportunity to replay a server response and set time back
//   // again. By incrementing the sequenceId we guarantee old responses
//   // will be invalid.
//   AWPacket::incrementDefaultSequenceId();
  
//   return rtc.setClock(&tm);
// }


Stream& printEepromContents(Stream &s, uint16_t address, uint16_t size)
{
  s << "EEPROM values:\n";
  while (address <= E2END && size--) {
    s << "0x" << _HEX(address) << ": 0x";
    if (0 && address >= EEPROM_HMAC_KEY &&
	address < EEPROM_HMAC_KEY + EEPROM_HMAC_KEY_SIZE)
      s << "??\n"; // Don't print key!
    else
      s << _HEX(eeprom_read_byte((uint8_t*)address)) << endl;
    ++address;
  }
  return s;
}

void CommandHandler::process(Stream &console)
{
  while (console.available()) {
    char c = console.read();
    if ((c == '\r' || c == '\n') && ptr > buffer) {
      // Check for matching substr
      char *ep;
      if (startsWith_P(PSTR("eepromRead="), buffer, &ep)) {
	char *ep2;
	long address = strtol(ep, &ep2, 0);
	long size;
	if (address >= 0 && address <= E2END && ep2 != ep && *ep2 == ',' &&
	    (ep = ++ep2, size = strtol(ep, &ep2, 0)) > 0 &&
	    (address + size) <= E2END && ep2 != ep && *ep2 =='\0') {
	  printEepromContents(console, (uint16_t)address, (uint16_t)size);
	}
	else
	  console << "ERROR: bad values for eepromRead\n";
      }
      else if (startsWith_P(PSTR("eepromWrite="), buffer, &ep)) {
	char *ep2;
	long address = strtol(ep, &ep2, 0);
	uint16_t size = 0;
	if (ep2 != ep && *ep2 == ',') {
	  if (*(ep2+1) == '\'') {
	    // Parse string data
	    ep = ep2 + 2;
	    while(address >= 0 && address <= E2END) {
	      uint8_t val = *ep++;
	      eeprom_update_byte((uint8_t*)address, val);
	      ++size;
	      ++address;
	      if (val == 0)
		break;
	    }
	  }
	  else {
	    while(address >= 0 && address <= E2END) {
	      ep = ++ep2;
	      long val = strtol(ep, &ep2, 0);
	      if (val >= 0 && val <= 255 && ep2 != ep &&
		  (*ep2 == ',' || *ep2 == '\0')) {
		//if (address < EEPROM_HMAC_KEY ||
		//address >= (EEPROM_HMAC_KEY + EEPROM_HMAC_KEY_SIZE))
		// // Do not allow key to be updated
		eeprom_update_byte((uint8_t*)address, val);
		++size;
		++address;
	      }
	      else
		break;
	    }
	  }
	  printEepromContents(console, (uint16_t)(address-size),
			      (uint16_t)size);
	}
	else
	  console << "ERROR: bad values for eepromWrite\n";
      }
      else if (startsWith_P(PSTR("REBOOT=true"), buffer, &ep)) {
	console << "Rebooting ..." << endl;
	console.flush();
	xboot_reset();
	//wdt_enable(WDTO_8S);
	//while (1)
	//;
      }
      else if (startsWith_P(PSTR("samplingInterval_16th_s"), buffer, &ep)) {
	if (*ep++ == '=') {
	  char *ep2;
	  long s = strtol(ep, &ep2, 0);
	  if (s > 0 && ep2 != ep && *ep2 == '\0') {
	    CounterRTC::Time tmp = 
	      CounterRTC::Time((s & 0xFFF0) >> 4,
			       (s & 0x000F) <<
			       (CounterRTC::fractionsPerSecondLog2 - 4));
	    if (tmp >= minSamplingInterval && tmp <= maxSamplingInterval) 
	      samplingInterval = tmp;
	    
	  }
	}
	console << "samplingInterval_16th_s:"
		<< ((samplingInterval.getSeconds() * 16) +
		    (samplingInterval.getFraction() >> (CounterRTC::fractionsPerSecondLog2 - 4))) << endl;
	
	
      }
#if USE_SD_CARD
      else if (startsWith_P(PSTR("useSd"), buffer, &ep)) {
	if (*ep++ == '=') {
	  char *ep2;
	  long s = strtol(ep, &ep2, 0);
	  if (s >= 0 && s <= 1 && ep2 != ep && *ep2 == '\0') {
	    // Need to update both EEPROM and RAM values since the RAM
	    // value might differ (eg card couldn't be initialized).
	    useSd = s;
	    eeprom_update_byte((uint8_t*)EEPROM_USE_SD, s);
	    // TODO: call SD.begin(sdSelect) if necessary
	  }
	}
	console << "useSd:"
		<<  useSd << " (current), "
		<< eeprom_read_byte((const uint8_t*)EEPROM_USE_SD)
		<< " (EEPROM)" << endl;
      }
#endif
      else  if (startsWith_P(PSTR("verbosity"), buffer, &ep)) {
	if (*ep++ == '=') {
	  char *ep2;
	  long v = strtol(ep, &ep2, 0);
	  if (v >= 0 && v <= 255 && ep2 != ep && *ep2 == '\0') {
	    verbosity = v;
	  }
	}
	console << F("verbosity:") << verbosity << endl;
      }
      else {
	console << F("ERROR: unknown command: '") << buffer << F("'\n");
      }
      
      memset(buffer, 0, sizeof(buffer));
      ptr = buffer;
    }
    else if (ptr - buffer < bufferLen && isprint(c)) {
      // Add to buffer
      *ptr++ = c;
    }
  }

}
