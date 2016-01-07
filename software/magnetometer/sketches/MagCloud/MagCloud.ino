#include <avr/eeprom.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <avr/boot.h>
#include <util/atomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <Wire.h>
#include <Streaming.h>

#include <AWPacket.h>
#include <FLC100_shield.h>
#include <SoftWire.h>
#include <MLX90614.h>
#include <HIH61xx.h>

#ifdef USE_AS3935
#include <AS3935.h>
#endif

#include <HouseKeeping.h>

#include <RTCx.h>
#include <CounterRTC.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CircBuffer.h>
#include <CommsInterface.h>
#include <XRF_Radio.h>
#include <SPI.h>
#include <Ethernet.h>
#include <Dhcp.h>
#include <W5100_UDP.h>

//#include <SD.h>

#include <CircularStack.h>
#include <AwEeprom.h>
#include <DisableJTAG.h>

#include "CommandHandler.h"
#include "CommsHandler.h"

#include "xbootapi.h"

#include "MagCloud.h"

#ifdef SHOW_MEM_USAGE
#include <MemoryFree.h>
#endif 

const char firmwareVersion[AWPacket::firmwareNameLength] =
  "MagCloud-0.25a";
// 1234567890123456
uint8_t rtcAddressList[] = {RTCx::MCP7941xAddress,
			    RTCx::DS1307Address};


uint8_t ledPin = LED_BUILTIN;
const uint8_t fanPin = eeprom_read_byte((uint8_t*)EEPROM_FAN_PIN);
const uint8_t heaterPin = eeprom_read_byte((uint8_t*)EEPROM_HEATER_PIN);

// Flag to indicate if LED should be switched on. To ensure minimal
// power consumption it is always switched off.
bool useLed = false;

// Number of messages transmitted. Rollover is expected and must be
// planned for!
uint8_t messageCount = 0;

Stream& console = Serial;
uint8_t radioType;
XRF_Radio xrf(Serial1);
W5100_UDP w5100udp;
uint8_t verbosity = 1;

FLC100 flc100;
bool flc100Present = eeprom_read_byte((uint8_t*)EEPROM_FLC100_PRESENT);

MLX90614 mlx90614;
bool mlx90614Present = eeprom_read_byte((uint8_t*)EEPROM_MLX90614_PRESENT);

HIH61xx hih61xx;
bool hih61xxPresent = eeprom_read_byte((uint8_t*)EEPROM_HIH61XX_PRESENT);

#ifdef USE_AS3935
AS3935 as3935;
bool as3935Present = eeprom_read_byte((uint8_t*)EEPROM_AS3935_PRESENT);
CounterRTC::Time as3935Timestamp;
#endif

CommandHandler commandHandler;

const uint8_t xrfSleepPin = 7;
const uint8_t xrfOnPin = 23;
const uint8_t xrfResetPin = 5;

// Set if packets should be multiple of some particular length
uint16_t commsBlockSize = 0; 

const uint16_t commsStackBufferLen = 4096;
uint8_t commsStackBuffer[commsStackBufferLen];
CommsHandler commsHandler(commsStackBuffer, commsStackBufferLen);

const uint16_t responseBufferLen = 400;
uint8_t responseBuffer[responseBufferLen];

// Maximum allowable time error
const CounterRTC::Time maxTimeError(1, 0);

// Most recent time adjustment. Sent on all outgoing packets until a
// message acknowledgement is received, at which point it is set to
// zero.
CounterRTC::Time timeAdjustment(0, 0);

//AsyncDelay xrfResponseTimeout;
// uint32_t xrfResponseTimeout_ms = 1000;

// Don't sleep if samplingInterval is less than this value
uint16_t counter2Frequency = 0;
// const uint16_t minSleepInterval = 4; 
//uint32_t samplingInterval = 8;
CounterRTC::Time minSleepInterval(2, 0);
CounterRTC::Time samplingInterval(30, 0);
CounterRTC::Time minSamplingInterval(5, 0);
CounterRTC::Time maxSamplingInterval(600, 0);

bool samplingIntervalChanged = true;
bool enableSleep = true;
uint8_t hmacKey[EEPROM_HMAC_KEY_SIZE] = {
  255, 255, 255, 255, 255, 255, 255, 255, 
  255, 255, 255, 255, 255, 255, 255, 255};

// Flag indicating if all data samples should be sent, or just the aggregate
bool allSamples = false;

#if USE_SD_CARD
// SD card data
bool useSd = false;
const int sdBufferLength = 1024;   // Size of buffer
uint8_t sdBuffer[sdBufferLength];  // Space for buffer
// const uint8_t sdPacketSize = 64;   // Size of packet for SD card
// CircBuffer sdCircularBuffer(sdBuffer, sizeof(sdBuffer), sdPacketSize);
CircBuffer sdCircularBuffer(sdBuffer, sizeof(sdBuffer));
#endif

// After boot keep sending boot flags and firmware version until a
// response is received.
bool firstMessage = true;
bool sendFirmwareVersion = false;

// Name of firmware to upgrade to. Ensure room for trailing null to
// allow use of strcmp(). If empty string then not upgrading firmware.
char upgradeFirmwareVersion[AWPacket::firmwareNameLength + 1] = {
  '\0' };
uint16_t upgradeFirmwareNumBlocks;
uint16_t upgradeFirmwareCRC;

// Counter for the page number to be requested next time
uint16_t upgradeFirmwareGetBlockNumber;

// Send EEPROM values
uint16_t eepromContentsAddress = 0;
uint16_t eepromContentsLength = 0;

#if USE_SD_CARD
// /data/YYYY/MM/DD/YYYYMMDD.HH
// 123456789012345678901234567890
const uint8_t sdFilenameLen = 29; // Remember to include space for '\0'
char sdFilename[sdFilenameLen] = "OLD_FILE"; 
File sdFile;
#endif

volatile bool startSampling = true;
volatile bool callbackWasLate = true;

// Flag limiting calls Ethernet.maintain() to one per sampling
// interval.
bool maintainDhcpLease = false;

// Code to ensure watchdog is disabled after reboot code. Also takes a
// copy of MCUSR register.
static uint8_t mcusrCopy;
void get_mcusr(void)
{
  mcusrCopy = MCUSR;
  MCUSR = 0;
  wdt_disable();
}


void startSamplingCallback(uint8_t alarmNum __attribute__ ((unused)), bool late, const void *context __attribute__ ((unused)) )
{
  // Indicate that main loop should commence sampling
  startSampling = true;
  callbackWasLate = late;
}

void setAlarm(void)
{
  // Request the next alarm
  CounterRTC::Time t;
    
  if (callbackWasLate)
    // Set next alarm relative to current time.
    cRTC.getTime(t);
  else 
    // Set next alarm relative to the scheduled time.
    cRTC.getAlarm(0, t, NULL);

  t += samplingInterval;
  
  /*
  // --------------------
  if (callbackWasLate) {
    CounterRTC::Time now;
    cRTC.getTime(now);
    console << "startSamplingCallback()  LATE ====\n";
    extern CounterRTC::Time alarmBlockTime[CounterRTC::numAlarms];
    extern uint8_t alarmCounter[CounterRTC::numAlarms];
    console << "alarm block: " <<  alarmBlockTime[0].getSeconds()
	    << ' ' << alarmBlockTime[0].getFraction()
	    << ' ' << _DEC(alarmCounter[0])
	    << endl
	    << "now: " << now.getSeconds() << ' ' << now.getFraction() << endl;
  }
  else
    console << "startSamplingCallback()\n";
  console << "alarmTime: " << t.getSeconds() << ' ' << t.getFraction() << endl;
  // --------------------
  */
  cRTC.setAlarm(0, t, startSamplingCallback);
}

#ifdef PRINT_BINARY_BUFFER
Stream& printBinaryBuffer(Stream &s, const void* buffer, int len)
{
  const uint8_t *ptr = (uint8_t*)buffer;
  for (int i = 0; i < len; ++i) {
    if (i)
      s << ' ';
    if (*ptr < 0x10)
      s << '0';
    s << _HEX(*ptr);
    ++ptr;
  }
  return s;
}
#endif

#if USE_SD_CARD
void createFilename(char *ptr, const uint8_t len, RTCx::time_t t)
{
  struct RTCx::tm tm;
  RTCx::gmtime_r(&t, &tm);
  // /data/YYYY/MM/DD/YYYYMMDD.HH
  snprintf(ptr, len, "/data/%04d/%02d/%02d/%04d%02d%02d.%02d",
	   tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
	   tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
	   tm.tm_hour);
}
#endif

void doSleep(uint8_t mode)
{
  disableJTAG();

  while (ASSR & _BV(TCR2AUB))
    ; // Wait for any pending updates to have latched
  volatile uint8_t tccr2aCopy = TCCR2A;

  while (!startSampling) {
    // TODO: restrict how many times loop can run
    
    /*
     * Now sleep, but see caveat from the data sheet:
     *
     * If Timer/Counter2 is used to wake the device up from
     * Power-save or ADC Noise Reduction mode, precautions must be
     * taken if the user wants to re-enter one of these modes: The
     * interrupt logic needs one TOSC1 cycle to be reset. If the
     * time between wake-up and reentering sleep mode is less than
     * one TOSC1 cycle, the interrupt will not occur, and the
     * device will fail to wake up. If the user is in doubt
     * whether the time before re-entering Power-save or ADC Noise
     * Reduction mode is sufficient, the following algorithm can
     * be used to ensure that one TOSC1 cycle has elapsed:
     *
     * - a. Write a value to TCCR2x, TCNT2, or OCR2x.
     * - b. Wait until the corresponding Update Busy Flag in ASSR
     *      returns to zero.
     * - c. Enter Power-save or ADC Noise Reduction mode.
     */

    noInterrupts();
    TIFR2 |= (_BV(OCF2A) | _BV(OCF2B) | _BV(TOV2)); 
    interrupts();
    
    while (ASSR & _BV(TCR2AUB))
      ;
    TCCR2A = tccr2aCopy;
    //TCCR2A = 0;
    // Memory barrier to ensure the write to OCR2B isn't optimized away
    __asm volatile( "" ::: "memory" );
    
    //OCR2B = ocr2bCopy; // Write

    while((ASSR & (1 << TCR2AUB)) != 0)
      ; // Wait for changes to latch
     //while (ASSR & _BV(OCR2BUB))
     // ; // Wait for one TOSC1 cycle to complete
    __asm volatile( "" ::: "memory" );

    cli();
    set_sleep_mode(mode); // Set the mode
    sleep_enable();       // Make sleeping possible
    wdt_disable();
    sleep_bod_disable();  // Disable brown-out detection for sleeping
    // TIFR2 |= (1 << OCF2A); // Ensure any pending interrupt is cleared
    sei();                // Make sure wake up is possible!
    sleep_cpu();          // Now go to sleep
    // Asleep ....
    
    // Now awake again
    sleep_disable();      // Make sure sleep can't happen until we are ready
    sei();
    wdt_enable(WDTO_8S);
  }


  /*
   * Fix a suspected bug in the two-wire hardware which stops it
   * working after sleep. See
   * http://www.avrfreaks.net/index.php?name=PNphpBB2&file=viewtopic&t=22549
   */
  TWCR &= ~(_BV(TWSTO) + _BV(TWEN));
  TWCR |= _BV(TWEN); 
}

void processResponse(const uint8_t* responseBuffer, uint16_t responseBufferLen)
{
  // Cancel any previous time adjustment. (If there was one the
  // server is aware since we have received a response packet.)
  timeAdjustment = CounterRTC::Time(0, 0);

  // Cancel sending firmware version
  sendFirmwareVersion = false;
  
  // Cancel previous request for EEPROM contents
  eepromContentsLength = 0;
  
  // DEBUG: message received, turn off LED
  digitalWrite(ledPin, LOW);
  AWPacket::parsePacket(responseBuffer, responseBufferLen,
			&console,
			processResponseTags, AWPacket::printUnknownTag);
  if (verbosity) {
    console << "====\nResponse:\n";
    AWPacket::printPacket(responseBuffer, responseBufferLen, console);
    console << "====\n";
  }
  if (verbosity > 1 && flc100Present) {
    for (uint8_t i = 0; i < FLC100::numAxes; ++i) {
      console << char('X' + i) << ':';
      for (uint8_t j = 0; j < FLC100::maxSamples; ++j)
	console << ' ' << flc100.getMagDataSamples(i, j);
      console << '\n';
    }
    console << " -----------" << endl;
  }
}


// TODO: Fetch firmware update pages continuously after FW
// updated received. Reuse SD buffer for spmBuffer

uint8_t spmBuffer[SPM_PAGESIZE];
// Process the response sent back from the server. Context must be a stream
bool processResponseTags(uint8_t tag, const uint8_t *data, uint16_t dataLen, void *context)
{
  Stream *s = (Stream*)context;
  switch (tag) {
  case AWPacket::tagCurrentUnixTime:
    {
      uint32_t secs;
      uint16_t frac;
      CounterRTC::Time ourTime;
      cRTC.getTime(ourTime);

      AWPacket::networkToAvr(&secs, data, sizeof(secs));
      AWPacket::networkToAvr(&frac, data + sizeof(secs), sizeof(frac));
      CounterRTC::Time serverTime(secs, frac);
      
      CounterRTC::Time timeError = ourTime - serverTime;
      if (abs_(timeError) > maxTimeError) {
      	cRTC.setTime(serverTime);
      	console << "Time set\n";
      	timeAdjustment = -timeError;
      }
      if (verbosity > 2) {
	console << "Server time: " << secs << ' ' << frac
		<< "\nOur time: "  << ourTime.getSeconds() << ' '
		<< ourTime.getFraction()
		<< "\ntimeError (our-server): " << timeError.getSeconds() << ' '
		<< timeError.getFraction() << endl;
      }
    }
    break;
    
  case AWPacket::tagSamplingInterval:
    {
      uint16_t u16;
      AWPacket::networkToAvr(&u16, data, sizeof(u16));
      samplingInterval = 
	CounterRTC::Time((u16 & 0xFFF0) >> 4,
			 (u16 & 0x000F) <<
			 (CounterRTC::fractionsPerSecondLog2 - 4));
      if (samplingInterval < minSamplingInterval)
	samplingInterval = minSamplingInterval;
      else if (samplingInterval > maxSamplingInterval)
	samplingInterval = maxSamplingInterval;
      samplingIntervalChanged = true;
      (*s) << "SAMPLING INTERVAL CHANGED! "
	   << samplingInterval.getSeconds() << ',' 
	   << samplingInterval.getFraction() << endl;
    }
    break;

  case AWPacket::tagReboot:
    wdt_enable(WDTO_1S);
    while (1)
      ;
    break;

  case AWPacket::tagUpgradeFirmware:
    if (upgradeFirmwareVersion[0] == '\0') {
      // Not currently upgrading, honour request
      memcpy(upgradeFirmwareVersion, data, AWPacket::firmwareNameLength);
      upgradeFirmwareVersion[sizeof(upgradeFirmwareVersion)-1] = '\0';
      console << "Received upgrade firmware tag: "
	      << upgradeFirmwareVersion << endl;
      if (strncmp(upgradeFirmwareVersion, firmwareVersion,
		  AWPacket::firmwareNameLength) == 0) {
	// Same as current so clear upgradeFirmwareVersion.
	upgradeFirmwareVersion[0] = '\0';
	console << "Already have firmware version " << firmwareVersion << endl;

	// TODO: Send firmwareVersion so that server knows to cancel
	// the request.
	sendFirmwareVersion = true;
       	break;
      }
      console << "Upgrade firmware to " << upgradeFirmwareVersion << endl;

      AWPacket::networkToAvr(&upgradeFirmwareNumBlocks,
			     data + AWPacket::firmwareNameLength,
			     sizeof(upgradeFirmwareNumBlocks));
      AWPacket::networkToAvr(&upgradeFirmwareCRC,
			     data + AWPacket::firmwareNameLength +
			     sizeof(upgradeFirmwareNumBlocks),
			     sizeof(upgradeFirmwareCRC));
      upgradeFirmwareGetBlockNumber = 0;
    }
    break;

  case AWPacket::tagFirmwarePage:
    uint16_t responsePageNumber;
    AWPacket::networkToAvr(&responsePageNumber,
			   data + AWPacket::firmwareNameLength,
			   sizeof(responsePageNumber));
    if (strncmp(upgradeFirmwareVersion, (const char*)data,
		AWPacket::firmwareNameLength) == 0 && 
	upgradeFirmwareGetBlockNumber == responsePageNumber &&
	upgradeFirmwareGetBlockNumber < upgradeFirmwareNumBlocks) {
      const uint8_t blocksPerSpmPage = (SPM_PAGESIZE /
					AWPacket::firmwareBlockSize);
      uint8_t i = upgradeFirmwareGetBlockNumber % blocksPerSpmPage;
      console << "Processing FW upgrade " << upgradeFirmwareGetBlockNumber
	      << " " << i << endl; 
      memcpy(spmBuffer + (i * AWPacket::firmwareBlockSize),
	     data + AWPacket::firmwareNameLength +
	     AWPacket::sizeOfFirmwarePageNumber,
	     AWPacket::firmwareBlockSize);
      if (i == blocksPerSpmPage - 1) {
	if (upgradeFirmwareGetBlockNumber == blocksPerSpmPage - 1) {
	  uint8_t r = xboot_app_temp_erase();
	  console << "Erased temporary application area in flash "
		  << r << endl;
	}
	
	// TODO: check if SPM page differs before writing to flash?
	uint32_t addr = ((upgradeFirmwareGetBlockNumber - i) *
			 (uint32_t)AWPacket::firmwareBlockSize);
	uint8_t r = xboot_app_temp_write_page(addr, spmBuffer, 0);
	console << "copied spmBuffer to flash: " << addr << " " << r << endl;
      }
      
      if (upgradeFirmwareGetBlockNumber == upgradeFirmwareNumBlocks - 1) {
	console << "Firmware download for " << upgradeFirmwareVersion
		<< " completed\n";
	
	if (i != blocksPerSpmPage - 1) {
	  // Ensure partially filled buffer to written to flash
	  memset(spmBuffer + ((i+1) * AWPacket::firmwareBlockSize), 0xFF,
		 (blocksPerSpmPage - (i+1)) * AWPacket::firmwareBlockSize);
	  // TODO: check if SPM page differs before writing to flash?
	  uint32_t addr = ((upgradeFirmwareGetBlockNumber - i) *
			   (uint32_t)AWPacket::firmwareBlockSize);
	  uint8_t r = xboot_app_temp_write_page(addr, spmBuffer, 0);

	  console << "copied partial spmBuffer to flash: " << addr
		  << " " << r << endl;
	}
	
	// Disable further upgrades
	// *upgradeFirmwareVersion = '\0';
	// TODO: CRC and issue command to upgrade/reboot
	uint16_t crc;
	uint8_t crcStatus = xboot_app_temp_crc16(&crc);
	console << "Firmware CRC: " << upgradeFirmwareCRC << endl
		<< "Download CRC: " << crc << endl
		<< "CRC status: " << crcStatus << endl;
	delay(100);
	uint8_t installResult =  xboot_install_firmware(upgradeFirmwareCRC);
	console << "Install FW result: " << installResult << endl;
	console.flush();
	delay(1000);
	xboot_reset();
      }
      ++upgradeFirmwareGetBlockNumber;

    }
    break;

  case AWPacket::tagReadEeprom:
    // Save values to report back in tagEepromContents
    AWPacket::networkToAvr(&eepromContentsAddress, data,
			   sizeof(eepromContentsAddress));
    AWPacket::networkToAvr(&eepromContentsLength,
			   data + sizeof(eepromContentsAddress),
			   sizeof(eepromContentsLength));
    break;
    
  case AWPacket::tagEepromContents:
    {
      uint16_t eepromAddress;
      AWPacket::networkToAvr(&eepromAddress, data, sizeof(eepromAddress));
      data += sizeof(eepromAddress);
      dataLen -= sizeof(eepromAddress);

      // Remember values to report back to server
      eepromContentsAddress = eepromAddress;
      eepromContentsLength = dataLen;
      
      while (dataLen--) {
	if (eepromAddress < EEPROM_HMAC_KEY ||
	    eepromAddress >= (EEPROM_HMAC_KEY + EEPROM_HMAC_KEY_SIZE))
	  // Data not encrypted, OTA key updates prohibited.
	  eeprom_update_byte((uint8_t*)eepromAddress, *data);
	++eepromAddress;
	++data;
      }
    }
    break;
  
  case AWPacket::tagNumSamples:
    {
      uint8_t numSamples, control;
      AWPacket::networkToAvr(&numSamples, data, sizeof(numSamples));
      data += sizeof(numSamples);
      if (numSamples) {
	AWPacket::networkToAvr(&control, data, sizeof(control));
	flc100.setNumSamples(numSamples,
			     control & EEPROM_AGGREGATE_USE_MEDIAN,
			     control & EEPROM_AGGREGATE_TRIM_SAMPLES);
      }
    }
    break;
    
  case AWPacket::tagAllSamples:
    {
      uint8_t all;
      AWPacket::networkToAvr(&all, data, sizeof(all));
      allSamples = (all != 0);
    }
    break;
    
  } // end of switch

  firstMessage = false;

  return false;
}


#ifdef USE_AS3935
void as3935InterruptHandler(void)
{
  // The AS3935 interrupt handler is inline code
  as3935.interruptHandler(); 
}


// Record current time
void as3935TimestampCB(void)
{
  cRTC.getTime(as3935Timestamp);
}
#endif


bool dnsLookup(IPAddress dnsServer, const char *hostname,
	       IPAddress &result)
{
  DNSClient dns;
  dns.begin(dnsServer);
  return dns.getHostByName(hostname, result);
}

void printEthernetSettings(Stream &s,
			   const IPAddress &localIP, uint16_t localPort,
			   const IPAddress &subnetMask,
			   const IPAddress &gatewayIP,
			   const IPAddress (&dns)[EEPROM_NUM_DNS],
			   const IPAddress &remoteIP, uint16_t remotePort)
{
  s << "  Local: " << localIP << ':' << localPort << "\n  Mask: "
    << subnetMask << "\n  GW: "
    << gatewayIP << "\n  DNS: ";

  bool dnsFound = false;
  for (uint8_t n = 0; n < EEPROM_NUM_DNS; ++n)
    if (uint32_t((IPAddress)dns[n])) {
      if (dnsFound)
	s << ", ";
      s << dns[n];
      dnsFound = true;
    }
  if (!dnsFound)
    s << "(none)";

  s << "\n  Remote: " << remoteIP << ':' << remotePort << endl;
}


void beginW5100_UDP(void)
{
  uint8_t macAddress[6];
  uint8_t tmp[4];
  wdt_reset(); // This might take a while
  
  // Extract settings from EEPROM
  eeprom_read_block(macAddress, (void*)EEPROM_LOCAL_MAC_ADDRESS,
		    EEPROM_LOCAL_MAC_ADDRESS_SIZE);
  eeprom_read_block(tmp, (void*)EEPROM_LOCAL_IP_ADDRESS,
		    EEPROM_LOCAL_IP_ADDRESS_SIZE);
  IPAddress localIP(tmp);


  eeprom_read_block(tmp, (void*)EEPROM_NETMASK, EEPROM_NETMASK_SIZE);
  IPAddress netmask(tmp);

  eeprom_read_block(tmp, (void*)EEPROM_GATEWAY, EEPROM_GATEWAY_SIZE);
  IPAddress gateway(tmp);

  IPAddress dns[EEPROM_NUM_DNS];
  for (uint8_t n = 0; n < EEPROM_NUM_DNS; ++n) {
    eeprom_read_block(tmp, (void*)(EEPROM_DNS1 + n*EEPROM_DNS1_SIZE),
		      EEPROM_DNS1_SIZE);
    dns[n] = IPAddress(tmp);
  }
    
  eeprom_read_block(tmp, (void*)EEPROM_REMOTE_IP_ADDRESS,
		    EEPROM_REMOTE_IP_ADDRESS_SIZE);
  IPAddress remoteIP(tmp);
  uint16_t localPort
    = eeprom_read_word((const uint16_t*)EEPROM_LOCAL_IP_PORT);
  uint16_t remotePort
    = eeprom_read_word((const uint16_t*)EEPROM_REMOTE_IP_PORT);

  char remoteHostname[EEPROM_REMOTE_HOSTNAME_SIZE];
  eeprom_read_block(remoteHostname, (void*)EEPROM_REMOTE_HOSTNAME,
		    EEPROM_REMOTE_HOSTNAME_SIZE);

  console << "EEPROM settings:\n  MAC: ";
  for (uint8_t i = 0; i < 6; ++i) {
    if (i)
      console << ':';
    if (macAddress[i] < 16)
      console << '0';
    console << _HEX(macAddress[i]);
  }
  console << endl;
  
  printEthernetSettings(console, localIP, localPort,
			netmask, gateway, dns,
			remoteIP, remotePort);
  console << "  Remote hostname: " << remoteHostname << endl;
    
  console << "localIP uint32_t: " << (uint32_t(localIP)) << endl;
  wdt_reset();
  if (uint32_t(localIP))
    // Static IP
    Ethernet.begin(macAddress, localIP, dns[0], gateway, netmask);
  else {
    // Use DHCP to obtain dynamic IP
    Ethernet.begin(macAddress);
    dns[0] = Ethernet.dnsServerIP(); // Primary IP from DHCP
    // Disable sleeping. It prevents millis() from working correctly
    // which breaks the DHCP lease maintenance.
    enableSleep = false;
  }
  wdt_reset();

  if (isprint(remoteHostname[0])) {
    // Lookup IP address of remote hostname.
    IPAddress ip;
    bool found = false;
    for (uint8_t t = 0; t < 3; ++t) 
      for (uint8_t n = 0; n < EEPROM_NUM_DNS; ++n)
	// Attempt lookup only if DNS server IP non-zero
	if (uint32_t(dns[n]) &&
	    (dnsLookup(dns[n], remoteHostname, ip) == 1)) {
	  found = true;
	  break;
	}

    if (!found) {
      console.print("Cannot resolve ");
      console.println(remoteHostname);
      console.flush();
    }
    // Fall back to EEPROM setting for IP address
    remoteIP = ip;
  }


  if (uint32_t(remoteIP) == 0) {
    // Cannot resolve (or undefined) remote host and no fallback
    // IP. Reboot.
    wdt_enable(WDTO_8S);
    while (1)
      ;
  }
  
  console << "Active settings:\n";
  printEthernetSettings(console, Ethernet.localIP(), localPort,
			Ethernet.subnetMask(), Ethernet.gatewayIP(),
			dns, remoteIP, remotePort);
  console.println();
  
  w5100udp.begin(macAddress, localIP, localPort, remoteIP, remotePort,
		 10, 4);
}


void setup(void)
{
  get_mcusr();
  wdt_enable(WDTO_8S);

  // Set all digital I/O as inputs with pullups, each library should
  // configure I/O as appropriate later.
  for (uint8_t i = 0; i < NUM_DIGITAL_PINS; ++i)
    pinMode(i, INPUT_PULLUP);

  // Set fan and heater pins off ASAP to avoid unwanted operation
  if (fanPin != 0xFF) {
    pinMode(fanPin, OUTPUT);
    digitalWrite(fanPin, LOW);
  }
  if (heaterPin != 0xFF) {
    pinMode(heaterPin, OUTPUT);
    digitalWrite(heaterPin, LOW);
  }
  

  uint8_t adcAddressList[FLC100::numAxes] = {0x6E, 0x6A, 0x6C};
  uint8_t adcChannelList[FLC100::numAxes] = {1, 1, 1};
  uint8_t adcResolutionList[FLC100::numAxes] = {18, 18, 18};
  uint8_t adcGainList[FLC100::numAxes] = {1, 1, 1};

  Serial.begin(9600);
  Serial1.begin(9600);
  
  // Explicitly set the pull-ups for the serial port in case the
  // Arduino IDE disables them.
#if defined (__AVR_ATmega644__) || defined (__AVR_ATmega644P__) \
  || defined (__AVR_ATmega1284__) || defined (__AVR_ATmega1284P__)
  MCUSR &= ~(1 << PUD); // Allow pull-ups on UARTS
  PORTD |= ((1 << PORTD0) | (1 << PORTD2)); 
#else
#error No pull-ups enabled for serial ports
#endif

  console.print((__FlashStringHelper*)PSTR("\nFirmware version: "));
  console.println(firmwareVersion);

  // Print fuses
  uint8_t lowFuse = boot_lock_fuse_bits_get(GET_LOW_FUSE_BITS);
  uint8_t highFuse = boot_lock_fuse_bits_get(GET_HIGH_FUSE_BITS);
  uint8_t extendedFuse = boot_lock_fuse_bits_get(GET_EXTENDED_FUSE_BITS);
  console << "Low fuse: " << _HEX(lowFuse) << endl
	  << "High fuse: " << _HEX(highFuse) << endl
	  << "Extended fuse: " << _HEX(extendedFuse) << endl;

  // Is the internal RC oscillator in use? Programmed fuses read low
  uint8_t ckselMask = (uint8_t)~(FUSE_CKSEL3 & FUSE_CKSEL2 &
				 FUSE_CKSEL1 & FUSE_CKSEL0);
  bool isRcOsc = ((lowFuse & ckselMask) ==
		  ((FUSE_CKSEL3 & FUSE_CKSEL2 & FUSE_CKSEL0) & ckselMask));
  console << "Uses RC osc.: " << isRcOsc
	  << "\nCKSEL: " << _HEX(lowFuse & ckselMask)
	  << "\nMCUSR: " << _HEX(mcusrCopy) << endl; 

  // Only use the LED following a reset initiated by user action
  // (JTAG, external reset and power on). Exclude brown-out and
  // watchdog resets.
  if (mcusrCopy & (JTRF | EXTRF | PORF))
    useLed = true;
  
  // Ensure all SPI devices are inactive
  pinMode(4, OUTPUT);     // SD card if ethernet shield in use
  digitalWrite(4, HIGH); 
  pinMode(10, OUTPUT);    // WizNet on Ethernet shield
  digitalWrite(10, HIGH);

  pinMode(14, OUTPUT);    // RFM12B (if fitted)
  digitalWrite(14, HIGH);

  // Fan control
  if (fanPin != 0xFF) {
    console.print((__FlashStringHelper*)PSTR("Fan temperature: "));
    console.println((int16_t)eeprom_read_word((const uint16_t*)
					      EEPROM_FAN_TEMPERATURE));
    console.print((__FlashStringHelper*)PSTR("Fan hysteresis: "));
    console.println((int16_t)eeprom_read_word((const uint16_t*)
					      EEPROM_FAN_HYSTERESIS));
  }
  
#if USE_SD_CARD
  uint8_t sdSelect = eeprom_read_byte((uint8_t*)EEPROM_SD_SELECT);
  useSd = (eeprom_read_byte((uint8_t*)EEPROM_USE_SD) == 1);
  if (sdSelect < NUM_DIGITAL_PINS) {
    pinMode(sdSelect, OUTPUT); // Onboard SD card
    digitalWrite(sdSelect, HIGH);
    if (useSd) {
      if (!SD.begin(sdSelect)) {
	console << "Cannot initialise SD card on #" << sdSelect << endl;
	useSd = false;
      }
      else
	console << "SD configured on #" << sdSelect << endl;
    }
    else {
      digitalWrite(sdSelect, HIGH);
      console << "SD disabled on #" << sdSelect << endl;
    }
  }
#endif

  // Copy key from EEPROM
  console << "HMAC key: ";
  for (uint8_t i = 0; i < EEPROM_HMAC_KEY_SIZE; ++i) {
    hmacKey[i] = eeprom_read_byte((const uint8_t*)(EEPROM_HMAC_KEY + i));
    console << ' ' << _HEX(hmacKey[i]);
  }
  console.println();
    
  // Turn on 5V supply
  pinMode(FLC100_POWER, OUTPUT);
  digitalWrite(FLC100_POWER, HIGH);
  delay(FLC100::powerUpDelay_ms);
  
  Wire.begin();

  
  // Get ADC addresses
  for (uint8_t i = 0; i < FLC100::numAxes; ++i) {
    if (i < EEPROM_ADC_ADDRESS_LIST_SIZE) {
      uint8_t customAddress =
	eeprom_read_byte((uint8_t*)(EEPROM_ADC_ADDRESS_LIST + i));
      if (customAddress > 0 && customAddress <= 127)
	adcAddressList[i] = customAddress;
    }
    if (i < EEPROM_ADC_CHANNEL_LIST_SIZE) {
      uint8_t chan =
	eeprom_read_byte((uint8_t*)(EEPROM_ADC_CHANNEL_LIST + i));
      if (chan && chan <= MCP342x::numChannels)
	adcChannelList[i] = chan; 
    }

    if (i < EEPROM_ADC_RESOLUTION_LIST_SIZE) {
      uint8_t res =
	eeprom_read_byte((uint8_t*)(EEPROM_ADC_RESOLUTION_LIST + i));
      if (res && res <= MCP342x::maxResolution)
	adcResolutionList[i] = res; 
    }

    if (i < EEPROM_ADC_GAIN_LIST_SIZE) {
      uint8_t gain =
	eeprom_read_byte((uint8_t*)(EEPROM_ADC_GAIN_LIST + i));
      if (gain && gain <= MCP342x::maxGain)
	adcGainList[i] = gain; 
    }
  }
    
  // Get key
  eeprom_read_block(hmacKey, (uint8_t*)EEPROM_HMAC_KEY, EEPROM_HMAC_KEY_SIZE);
  AWPacket::setDefaultSiteId(eeprom_read_word((const uint16_t*)EEPROM_SITE_ID));

  uint8_t numSamples = eeprom_read_byte((uint8_t*)EEPROM_NUM_SAMPLES);
  if (numSamples == 0 || numSamples > FLC100::maxSamples)
    numSamples = 1;
  uint8_t aggregate = eeprom_read_byte((uint8_t*)EEPROM_AGGREGATE);
  if (aggregate == 255)
    aggregate = EEPROM_AGGREGATE_USE_MEDIAN; // Not set in EEPROM
  allSamples = eeprom_read_byte((uint8_t*)EEPROM_ALL_SAMPLES);

  __FlashStringHelper* initialisingStr
    = (__FlashStringHelper*)PSTR("Initialising ");
  __FlashStringHelper* notStr = (__FlashStringHelper*)PSTR(" not");
  __FlashStringHelper* presentStr = (__FlashStringHelper*)PSTR(" present");
  __FlashStringHelper* powerUpDelayStr
    = (__FlashStringHelper*)PSTR(" power-up delay (ms): ");

  __FlashStringHelper* flc100Str = (__FlashStringHelper*)PSTR("FLC100");
  if (flc100Present) {
    console.print(initialisingStr);
    console.println(flc100Str);

    flc100.initialise(FLC100_POWER, adcAddressList, adcChannelList,
		      adcResolutionList, adcGainList);
    flc100.setNumSamples(numSamples, 
			 aggregate & EEPROM_AGGREGATE_USE_MEDIAN,
			 aggregate & EEPROM_AGGREGATE_TRIM_SAMPLES);
    
    for (int i = 0; i < FLC100::numAxes; ++i)
      console << "ADC[" << i << "]: Ox" << _HEX(adcAddressList[i])
	      << ", channel: " << (adcChannelList[i]) << endl;
    console << "numSamples: " << numSamples << endl
	    << "aggregate: " << (aggregate & EEPROM_AGGREGATE_TRIM_SAMPLES ? "trimmed " : "")
	    << (aggregate & EEPROM_AGGREGATE_USE_MEDIAN ? "median" : "mean") << endl;

    console.flush();
  }

  console.print(flc100Str);
  if (!flc100Present)
    console.print(notStr);
  console.println(presentStr);
  if (flc100Present) {
    console.print(flc100Str);
    console.print(powerUpDelayStr);
    console.println(FLC100::powerUpDelay_ms);
  }
  
  __FlashStringHelper* mlx90614Str = (__FlashStringHelper*)PSTR("MLX90614");   
  if (mlx90614Present) {
    console.print(initialisingStr);
    console.println(mlx90614Str);
    mlx90614.getSoftWire().setDelay_us(2);
    mlx90614Present = mlx90614.initialise();
  }

  console.print(mlx90614Str);
  if (!mlx90614Present)
    console.print(notStr);
  console.println(presentStr);
  if (mlx90614Present) {
    console.print(mlx90614Str);
    console.print(powerUpDelayStr);
    console.println(MLX90614::powerUpDelay_ms);
  }

  __FlashStringHelper* hih61xxStr = (__FlashStringHelper*)PSTR("HIH61xx");
  if (hih61xxPresent) {
    console.print(initialisingStr);
    console.println(hih61xxStr);
    hih61xxPresent = hih61xx.initialise(A4, A5);
  }
  console.print(hih61xxStr);
  if (!hih61xxPresent)
    console.print(notStr);
  console.println(presentStr);

#ifdef USE_AS3935
  __FlashStringHelper* as3935Str = (__FlashStringHelper*)PSTR("AS3935");
  if (as3935Present) {
    console.print(initialisingStr);
    console.println(as3935Str);
    // TODO: Have tunCap read from EEPROM or calibrate (which requires
    // accurate clock, not RC oscillator).
    uint8_t tunCap = eeprom_read_byte((uint8_t*)EEPROM_AS3935_TUN_CAP) & 0x0f;
    as3935Present = as3935.initialise(14, 17, 0x03, tunCap, false,
				      as3935TimestampCB);
    if (as3935Present) {
      // Start and set register values. Unlike other sensors this is
      // kept powered so needs starting only once, not at every
      // sampling interval.
      AsyncDelay d;
      as3935.start();
      d.start(1000, AsyncDelay::MILLIS);
      while (!d.isExpired())
	as3935.process();
      
      as3935.setNoiseFloor(0);
      as3935.setSpikeRejection(0);
    }
  }
  console.print(as3935Str);
  if (!as3935Present)
    console.print(notStr);
  console.println(presentStr);
#endif

  
  // Identify communications method to be used.
  radioType = eeprom_read_byte((const uint8_t*)EEPROM_COMMS_TYPE);
  if (radioType == 0xFF)
    // Not set so default to XRF as used in original version
    radioType = EEPROM_COMMS_TYPE_XRF;

  bool readVin = (radioType != EEPROM_COMMS_TYPE_W5100_UDP);
  houseKeeping.initialise(2, 7, A6, readVin, !readVin);
			  
  // Autoprobe to find RTC
  // TODO: avoid clash with known ADCs
  console << "Autoprobing to find RTC\n";
  console.flush();
  
  if (rtc.autoprobe(rtcAddressList, sizeof(rtcAddressList)))
    console << "Found RTC at address 0x" << _HEX(rtc.getAddress()) << endl;
  else
    console << "No RTC found" << endl;
  console.flush();
  
  // Enable the battery backup. This happens by default on the DS1307
  // but needs to be enabled on the MCP7941x.
  rtc.enableBatteryBackup();

  // Set the calibration register (ignored if not MCP7941x).
  rtc.setCalibration(eeprom_read_byte((uint8_t*)EEPROM_MCP7941X_CAL));
  
  // Ensure the oscillator is running.
  rtc.startClock();

  if (rtc.getDevice() == RTCx::MCP7941x) {
    console << "MCP7941x calibration: " << _DEC(rtc.getCalibration()) << endl;
    console.flush();
  }
  
  // Ensure square-wave output is enabled.
  rtc.setSQW(RTCx::freq4096Hz);
  pinMode(15, INPUT);

  // Warn, if it stops at this point it means the jumper isn't fitted.
  // TODO: test if jumper for RTC output is fitted.
  console << "Configuring MCU RTC\n";
  console.flush();
  
#if 0
  // Input: 4096Hz, prescaler is divide by 1, clock tick is 4096Hz
  cRTC.begin(4096, true, _BV(CS20));
  counter2Frequency = 4096;
#else
  // Input: 4096Hz, prescaler is divide by 256, clock tick is 16Hz
  cRTC.begin(16, true, (_BV(CS22) | _BV(CS21))); 
  counter2Frequency = 16;
#endif

  
  // Set counter RTC time from the hardware RTC
  struct RTCx::tm tm;
  if (rtc.readClock(&tm)) {
    CounterRTC::Time t;
    t.setSeconds(RTCx::mktime(tm));
    cRTC.setTime(t);
    console << "Set MCU RTC from hardware RTC\n";
  }
  else
    console << "Could not get time from hardware RTC\n";
  console.flush();

  // Set samplingInterval
  uint16_t samplingInterval_16th_s
    = eeprom_read_word((const uint16_t*)EEPROM_SAMPLING_INTERVAL_16TH_S);

  if (samplingInterval_16th_s && samplingInterval_16th_s != 0xFFFF) {
    samplingInterval
      = CounterRTC::Time((samplingInterval_16th_s & 0xFFF) >> 4,
			 (samplingInterval_16th_s & 0x000F) <<
			 (CounterRTC::fractionsPerSecondLog2 - 4));
  }
  if (samplingInterval < minSamplingInterval)
    samplingInterval = minSamplingInterval;
  else if (samplingInterval > maxSamplingInterval)
    samplingInterval = maxSamplingInterval;

  console.print((__FlashStringHelper*)PSTR("Sampling interval (s): "));
  console.print(samplingInterval.getSeconds());
  console.print((__FlashStringHelper*)PSTR(", "));
  console.println(samplingInterval.getFraction());
  console.flush();

  // Configure radio module or Ethernet adaptor.
  if (radioType == EEPROM_COMMS_TYPE_W5100_UDP) {
    beginW5100_UDP();
    
    disableJTAG();
    ledPin = 17; // JTAG TDO
    commsHandler.setCommsInterface(&w5100udp);
    useLed = true;
    
  }
  else {
    commsBlockSize = 12; // By default XRF sends 12 byte packets, set to reduce TX latency.
    xrf.begin(xrfSleepPin, xrfOnPin, xrfResetPin);
    commsHandler.setCommsInterface(&xrf);
  }

  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
  
  commsHandler.setKey(hmacKey, sizeof(hmacKey));

  console.println((__FlashStringHelper*)PSTR("Setup complete\n"));
  console.flush();
  
  setAlarm();
}


bool resultsProcessed = false;
CounterRTC::Time sampleStartTime;
void loop(void)
{
  wdt_reset();
  
  if (startSampling) {
    cRTC.getTime(sampleStartTime);
    
    if (flc100Present && !flc100.isSampling())
      flc100.start();
    
    if (!mlx90614.isSampling()) 
      mlx90614.start();
    
    if (!hih61xx.isSampling())
      hih61xx.start();

    // AS3935 does not need starting here. It is kept powered.
    
    if (!houseKeeping.isSampling())
      houseKeeping.start();
     
    // Set startSampling=false BEFORE setting the alarm. If the
    // computed alarm time is in the past then the callback will be
    // run immediately and will ensure startSampling is made true. If
    // the alarm is set before setting startSampling=false then an
    // alarm could be lost and sampling would stop.
    startSampling = false;
    setAlarm();

    resultsProcessed = false;
    console << "Sampling started\n";

    maintainDhcpLease = true; // Only do this once per sampling interval    
  }

  if (flc100Present)
    flc100.process();
  if (mlx90614Present)
    mlx90614.process();
  if (hih61xxPresent)
    hih61xx.process();
#ifdef USE_AS3935
  if (as3935Present)
    as3935.process();
#endif
  houseKeeping.process();

  if (commsHandler.process(responseBuffer, responseBufferLen))
    processResponse(responseBuffer, responseBufferLen);
  
  commandHandler.process(console);

  // console << "I2C state: " << (flc100.getI2CState()) << endl;
  if ((flc100Present == false || flc100.isFinished())
      && (mlx90614Present == false || mlx90614.isFinished())
      && (hih61xxPresent == false || hih61xx.isFinished())
      && houseKeeping.isFinished()) {
    // Process SD card when normal sampling is not running; SD card
    // access can be slow and block.
    
    if (resultsProcessed == false) {
      resultsProcessed = true;
      // for (uint8_t i = 0; i < FLC100::numAxes; ++i)
      // 	console << '\t' << (flc100.getMagData()[i]);
      // console << endl;
      
      console << "Timestamp: " << sampleStartTime.getSeconds()
	      << ", " << sampleStartTime.getFraction() << endl
	      << "Sensor temperature: " << flc100.getSensorTemperature() << endl
	      << "System temperature: " << houseKeeping.getSystemTemperature()
	      << endl;
      if (houseKeeping.getReadVin())
	console << "Battery voltage: " << houseKeeping.getVin() << endl;

      if (mlx90614Present) {
	console << "MLX temp: " << mlx90614.getAmbient() << endl
		<< "Object 1: " << mlx90614.getObject1() << endl;
	if (mlx90614.isDualSensor())
	  console << "Object 2: " << mlx90614.getObject2() << endl;
      }

      if (hih61xxPresent) 
	console << "Humidity: " << hih61xx.getRelHumidity() << endl
		<< "Ambient: " << hih61xx.getAmbientTemp() << endl;
     
      if (flc100Present)
	for (uint8_t i = 0; i < FLC100::numAxes; ++i)
	  console << "magData[" << i << "]: " << (flc100.getMagData()[i])
		  << endl;

      // Buffer for storing the binary AW packet. Will also be used
      // when writing to SD card.
      const uint16_t bufferLength = SD_SECTOR_SIZE;
      uint8_t buffer[bufferLength]; // Sector size for SD card is 512 bytes

      // Check system temperature
      if (fanPin != 0xFF) {
	int16_t fanTemperature
	  = (int16_t)eeprom_read_word((const uint16_t*)EEPROM_FAN_TEMPERATURE);
	uint16_t fanHysteresis
	  = eeprom_read_word((const uint16_t*)EEPROM_FAN_HYSTERESIS);
	if (houseKeeping.getSystemTemperature() >
	    (fanTemperature + (int16_t)(fanHysteresis/2)))
	  digitalWrite(fanPin, HIGH);
	if (houseKeeping.getSystemTemperature() <
	    (fanTemperature - (int16_t)(fanHysteresis/2)))
	  digitalWrite(fanPin, LOW);
      }
	    
      
#if USE_SD_CARD
      if (useSd) {
	// Check if the SD card circular buffer should be written to disk
	char newFilename[sdFilenameLen];
	createFilename(newFilename, sizeof(newFilename),
		       sampleStartTime.getSeconds());
	if ((strcmp(sdFilename, newFilename) != 0 ||
	     sdCircularBuffer.getSize() >= bufferLength ||
	     sdCircularBuffer.getSizeRemaining() <= 64)
	    && sdFile) {
	  while (1) {
	    int bytesRead = sdCircularBuffer.read(buffer, sizeof(buffer));
	    if (bytesRead == 0)
	      break;
	    sdFile.write(buffer, bytesRead);
	    sdFile.flush();
	    console << "Wrote to " << bytesRead << " to " << sdFilename << endl;
	  } 
	}
	
	if (strcmp(sdFilename, newFilename) != 0) {
	  if (sdFile) {
	    console << "Closing " << sdFilename << endl;
	    sdFile.close();
	  }
	  strncpy(sdFilename, newFilename, sizeof(sdFilename));
	  // Make directory
	  char *ptr = strrchr(newFilename, '/');
	  if (ptr) {
	    *ptr = '\0'; // Remove filename part
	    if (SD.mkdir(newFilename))
	      console << "Created directory " << newFilename << endl;
	  }
	  if ((sdFile = SD.open(sdFilename, FILE_WRITE)) == true)
	    console << "Opened " << sdFilename << endl;
	  else
	    console << "Failed to open " << sdFilename << endl;
	}
      }
#endif

      
      AWPacket packet;
      packet.setKey(hmacKey, sizeof(hmacKey));
      packet.setFlagBit(AWPacket::flagsSampleTimingErrorBit, callbackWasLate);
      packet.setTimestamp(sampleStartTime.getSeconds(),
			  sampleStartTime.getFraction());
      
      packet.putHeader(buffer, sizeof(buffer));
#ifdef PRINT_BINARY_BUFFER
      // printBinaryBuffer(console, buffer, 20);
      // console << endl;
#endif
      
      console << "Header length: " << AWPacket::getPacketLength(buffer) << endl;

      if (flc100Present) {
	uint8_t numSamples;
	bool median;
	bool trimmed;
	flc100.getNumSamples(numSamples, median, trimmed);
	
	for (uint8_t i = 0; i < FLC100::numAxes; ++i)
	  if (flc100.getAdcPresent(i)) {
	    packet.putMagData(buffer, sizeof(buffer),
			      AWPacket::tagMagDataX + i,
			      flc100.getMagResGain(i),
			      flc100.getMagData()[i]);
	    if (allSamples)
	      packet.putDataArray(buffer, sizeof(buffer),
				  AWPacket::tagMagDataAllX + i, 4,
				  numSamples, flc100.getMagDataSamples(i));
	  }
            
	packet.putDataInt16(buffer, sizeof(buffer),
			    AWPacket::tagSensorTemperature,
			    flc100.getSensorTemperature());
	packet.putDataUint16(buffer, sizeof(buffer),
			     AWPacket::tagNumSamples, 
			     (uint16_t(numSamples) << 8) | 
			     (uint16_t(trimmed) << 1) | 
			     median);

      }
      
      packet.putDataInt16(buffer, sizeof(buffer),
			  AWPacket::tagMCUTemperature,
			  houseKeeping.getSystemTemperature());
      if (houseKeeping.getReadVin())
	packet.putDataUint16(buffer, sizeof(buffer),
			     AWPacket::tagBatteryVoltage,
			     houseKeeping.getVin());
      // Upper 3 nibbles is seconds, lowest nibble is 16ths of second
      packet.putDataUint16(buffer, sizeof(buffer),
			   AWPacket::tagSamplingInterval,
			   (uint16_t(samplingInterval.getSeconds() << 4) |
			    samplingInterval.getFraction() >>
			    (CounterRTC::fractionsPerSecondLog2 - 4)));

      if (mlx90614Present) {
	packet.putDataInt16(buffer, sizeof(buffer),
			    AWPacket::tagCloudTempAmbient,
			    mlx90614.getAmbient());
	packet.putDataInt16(buffer, sizeof(buffer),
			    AWPacket::tagCloudTempObject1,
			    mlx90614.getObject1());
	if (mlx90614.isDualSensor())
	  packet.putDataUint16(buffer, sizeof(buffer),
			       AWPacket::tagCloudTempObject2,
			       mlx90614.getObject2());
      }

      if (hih61xxPresent) {
	packet.putDataInt16(buffer, sizeof(buffer),
			    AWPacket::tagAmbientTemp,
			    hih61xx.getAmbientTemp());
	packet.putDataUint16(buffer, sizeof(buffer),
			     AWPacket::tagRelHumidity,
			     hih61xx.getRelHumidity());
      }
      
      if (firstMessage) {
	// Cancelled when first response is received
	packet.putDataUint8(buffer, sizeof(buffer),
			    AWPacket::tagRebootFlags, mcusrCopy);
	packet.putString(buffer, sizeof(buffer),
			 AWPacket::tagCurrentFirmware, firmwareVersion);
      }
      else if (sendFirmwareVersion)
	packet.putString(buffer, sizeof(buffer),
			 AWPacket::tagCurrentFirmware, firmwareVersion);
      if (timeAdjustment != CounterRTC::Time(0, 0))
	// TODO: check against overflow in int32_t, int16_t
	packet.putTimeAdjustment(buffer, sizeof(buffer),
				 timeAdjustment.getSeconds(),
				 timeAdjustment.getFraction());
      
      if (eepromContentsLength) {
	console << "EEPROM contents length: " << eepromContentsLength << endl;
	packet.putEepromContents(buffer, sizeof(buffer),
				 eepromContentsAddress, eepromContentsLength);
      }
			       
      // Add the signature
      packet.putSignature(buffer, sizeof(buffer), commsBlockSize);

#if USE_SD_CARD
      // Log to a file (if desired)
      if (useSd)
	sdCircularBuffer.write(buffer, AWPacket::getPacketLength(buffer));
#endif
      
      // Send by radio
      commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
      ++messageCount;
      // DEBUG: message queued, turn on LED
      if (useLed) {
	uint8_t maxMessages
	  = eeprom_read_byte((uint8_t*)EEPROM_MAX_MESSAGES_LED);
	if (maxMessages && messageCount >= maxMessages)
	  useLed = false;
	digitalWrite(ledPin, useLed);
      }
      
      //if (verbosity)
      //AWPacket::printPacket(buffer, bufferLength, console);
    
      console << " -----------" << endl;
    }
    
    if (startSampling == false &&
	*upgradeFirmwareVersion != '\0' &&
	upgradeFirmwareGetBlockNumber < upgradeFirmwareNumBlocks &&
	commsHandler.isWaitingForMessages()) {
      // Request another firmware page. Since
      // commsHandler.isFinished() == TRUE there are no
      // acknowledgements pending and standard sampling isn't
      // occuring at this time. Once a message has been queued for
      // transmission commsHandler.isFinished() != TRUE until the
      // acknowledgement has been received.

      // Increment the sequence number since the timestamp inside
      // flc100 will not change until the next sampling action.
      AWPacket::incrementDefaultSequenceId();

      // Buffer for storing the binary AW packet
      const uint16_t bufferLength = 256;
      uint8_t buffer[bufferLength];

      AWPacket packet;
      packet.setKey(hmacKey, sizeof(hmacKey));
      CounterRTC::Time now;
      cRTC.getTime(now);
      packet.setTimestamp(now.getSeconds(), now.getFraction());
      
      packet.putHeader(buffer, sizeof(buffer));
      packet.putGetFirmwarePage(buffer, sizeof(buffer),
				upgradeFirmwareVersion,
				upgradeFirmwareGetBlockNumber);
      
       // Add the signature and send by radio
      packet.putSignature(buffer, sizeof(buffer), commsBlockSize); 

      commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
      ++messageCount;
      // Message queued, turn on LED
      if (useLed) {
	uint8_t maxMessages
	  = eeprom_read_byte((uint8_t*)EEPROM_MAX_MESSAGES_LED);
	if (maxMessages && messageCount >= maxMessages)
	  useLed = false;
	digitalWrite(ledPin, useLed);
      }
      
    }
    
    
    // Test if can go to sleep
    // if (!radio.available() && radioResponseTimeout.isExpired() &&
    // startSampling == false) {
    if (startSampling == false &&
	commsHandler.isFinished() &&
	commsHandler.getCommsInterface()->powerOff()) {
      
      struct RTCx::tm tm;
      rtc.readClock(tm);
      RTCx::time_t hwcTime = RTCx::mktime(tm);
      CounterRTC::Time now;
      cRTC.getTime(now);
      // Setting the RTC is likely to slightly upset the timing as it
      // stops the hardware clock briefly. Only set if necessary.
      if (labs(hwcTime-now.getSeconds()) > 2*maxTimeError.getSeconds()+1) {
      	RTCx::time_t t = now.getSeconds();
      	RTCx::gmtime_r(&t, &tm);
      	rtc.setClock(tm);
	console << "Set HW clock\n";
      }

      if (radioType == EEPROM_COMMS_TYPE_W5100_UDP && maintainDhcpLease) {
	maintainDhcpLease = false;
	uint8_t m = Ethernet.maintain();
	console << "DHCP ";
	switch (m) {
	case DHCP_CHECK_NONE:
	  console << "nothing done\n";
	  break;
	case DHCP_CHECK_RENEW_FAIL:
	case DHCP_CHECK_REBIND_FAIL:
	  console << "lease failed, rebooting\n";
	  // Reboot
	  wdt_enable(WDTO_8S);
	  while (1)
	    ;
	  break;
	case DHCP_CHECK_RENEW_OK:
	  console << "lease renewed\n";
	  break;
	case DHCP_CHECK_REBIND_OK:
	  console << "lease rebind\n";
	  break;
	default:
	  console << "maintain returned " << _DEC(m) << endl;
	}
      }

#ifdef SHOW_MEM_USAGE
      console << "Free mem: " << freeMemory() << endl;
#endif
      
      if (enableSleep && samplingInterval >= minSleepInterval) {
	console << "SLEEP!\n";
	console.flush();
	doSleep(SLEEP_MODE_PWR_SAVE);
	console << "AWAKE!\n";
	console.flush();
      }
    }
  }
  
}
  


