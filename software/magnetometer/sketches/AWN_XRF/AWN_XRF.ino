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
#include <RTCx.h>
#include <CounterRTC.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <MultiReadCircBuffer.h>

#include <SPI.h>
#include <SD.h>

#include <CircularStack.h>
#include "CommandHandler.h"
#include "CommsHandler.h"
#include "AwEeprom.h"

#include "xbootapi.h"
#include "disable_jtag.h"

const char firmwareVersion[AWPacket::firmwareNameLength] =
  "test-0.07b";
uint8_t rtcAddressList[] = {RTCx_MCP7941x_ADDRESS,
			    RTCx_DS1307_ADDRESS};

Stream& console = Serial;
Stream& xrf = Serial1;
uint8_t verbosity = 1;

FLC100 flc100;
CommandHandler commandHandler;

const uint8_t xrfSleepPin = 7;
const uint8_t xrfOnPin = 22;
const uint8_t xrfResetPin = 5;

const uint16_t commsBlockSize = 12; // Packets should be multiple of 12 long
const uint16_t commsStackBufferLen = 1024;
uint8_t commsStackBuffer[commsStackBufferLen];
CommsHandler commsHandler(xrf, commsStackBuffer, commsStackBufferLen);
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
CounterRTC::Time samplingInterval(8, 0);
bool samplingIntervalChanged = true;
//bool useSleepMode = true;
uint8_t hmacKey[EEPROM_HMAC_KEY_SIZE] = {
  255, 255, 255, 255, 255, 255, 255, 255, 
  255, 255, 255, 255, 255, 255, 255, 255};

// SD card data
bool useSd = false;
const int sdBufferLength = 1024;   // Size of buffer
uint8_t sdBuffer[sdBufferLength];  // Space for buffer
const uint8_t sdPacketSize = 32;   // Size of packet for SD card
MultiReadCircBuffer sdCircularBuffer(sdBuffer, sizeof(sdBuffer),
				     true, false, sdPacketSize);

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
			    
// /data/YYYY/MM/DD/YYYYMMDD.HH
// 123456789012345678901234567890
const uint8_t sdFilenameLen = 29; // Remember to include space for '\0'
char sdFilename[sdFilenameLen] = "OLD_FILE"; 
File sdFile;

volatile bool startSampling = false;
volatile bool callbackWasLate = true;

// Code to ensure watchdog is disabled after reboot code. Also takes a
// copy of MCUSR register.
uint8_t mcusrCopy __attribute__ ((section (".noinit")));
void get_mcusr(void)				\
  __attribute__((naked))			\
  __attribute__((section(".init3")));
void get_mcusr(void)
{
  mcusrCopy = MCUSR;
  MCUSR = 0;
  wdt_disable();
}

void startSamplingCallback(uint8_t alarmNum, bool late, const void *context)
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
  
  cRTC.setAlarm(0, t, startSamplingCallback);
}

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

void doSleep(uint8_t mode)
{
  disable_jtag();
  noInterrupts();
  set_sleep_mode(mode); // Set the mode
  sleep_enable();       // Make sleeping possible
  // TIFR2 |= (1 << OCF2A); // Ensure any pending interrupt is cleared
  interrupts();         // Make sure wake up is possible!

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
    sleep_cpu();          // Now go to sleep
  }

  // Now awake again
  sleep_disable();      // Make sure sleep can't happen until we are ready

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

  // DEBUG: message received, turn off LED
  digitalWrite(LED_BUILTIN, LOW);
  AWPacket::parsePacket(responseBuffer, responseBufferLen,
			&console,
			processResponseTags, AWPacket::printUnknownTag);
  if (verbosity) {
    console << "====\nResponse:\n";
    AWPacket::printPacket(responseBuffer, responseBufferLen, console);
    console << "====\n";
  }
}


// TODO: Fetch firmware update pages continuously after FW
// updated received. Reuse SD buffer for spmBuffer

uint8_t spmBuffer[SPM_PAGESIZE];
// Process the response sent back from the server. Context must be a stream
bool processResponseTags(uint8_t tag, const uint8_t *data, uint16_t dataLen,
			 void *context)
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
      if (verbosity > 1) {
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
      samplingIntervalChanged = true;
      (*s) << "SAMPLING INTERVAL CHANGED! "
	   << samplingInterval.getSeconds() << ',' 
	   << samplingInterval.getFraction() << endl;
    }
    break;

  case AWPacket::tagReboot:
    wdt_enable(WDTO_8S);
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
  }

  firstMessage = false;

  return false;
}

void setup(void)
{
  wdt_disable();
  uint8_t adcAddressList[FLC100::numAxes] = {0x6E, 0x6A, 0x6B};
  uint8_t adcChannelList[FLC100::numAxes] = {1, 1, 1};

  pinMode(LED_BUILTIN, OUTPUT);
  
  MCUSR = 0; // Clear flags
  Serial.begin(9600);
  Serial1.begin(9600);

  console << "Firmware version: " << firmwareVersion << endl;

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
  console << "Uses RC oscillator: " << isRcOsc << endl;
  console << "CKSEL: " << _HEX(lowFuse & ckselMask) << endl;
  uint8_t sdSelect = eeprom_read_byte((uint8_t*)EEPROM_SD_SELECT);
  //useSd = (eeprom_read_byte((uint8_t*)EEPROM_USE_SD) == 1);
  
  // Ensure all SPI devices are inactive
  pinMode(4, OUTPUT);     // SD card if ethernet shield in use
  digitalWrite(4, HIGH); 
  pinMode(10, OUTPUT);    // WizNet on Ethernet shield
  digitalWrite(10, HIGH);

  console << "MCUSR: " << _HEX(mcusrCopy) << endl; 
  if (sdSelect < NUM_DIGITAL_PINS) {
    pinMode(sdSelect, OUTPUT); // Onboard SD card
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
  }
    
  // Get key
  eeprom_read_block(hmacKey, (uint8_t*)EEPROM_HMAC_KEY, EEPROM_HMAC_KEY_SIZE);
  AWPacket::setDefaultSiteId(eeprom_read_word((const uint16_t*)EEPROM_SITE_ID));
  
  flc100.initialise(FLC100_POWER, adcAddressList, adcChannelList);

  for (int i = 0; i < FLC100::numAxes; ++i)
    console << "ADC[" << i << "]: Ox" << _HEX(adcAddressList[i])
	    << ", channel: " << (adcChannelList[i]) << endl;
  console.flush();
  
  //pinMode(XRF_RESET, OUTPUT);
  //pinMode(XRF_SLEEP, OUTPUT);

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
    console << "Could not get time from real RTC\n";
  console.flush();

  console << "Setting up XRF...\n";
  console.flush();
  commsHandler.setup(xrfSleepPin, xrfOnPin, xrfResetPin);
  commsHandler.setKey(hmacKey, sizeof(hmacKey));
  console << "... done\n";
  console.flush();
    
  setAlarm();
}


bool resultsProcessed = false;
void loop(void)
{
  if (startSampling && !flc100.isSampling()) {
    flc100.start();

    // Set startSampling=false BEFORE setting the alarm. If the
    // computed alarm time is in the past then the callback will be
    // run immediately and will ensure startSampling is made true. If
    // the alarm is set before setting startSampling=false then an
    // alarm could be lost and sampling would stop.  time with
    startSampling = false;
    setAlarm();
    
    resultsProcessed = false;
    console << "Sampling started\n";
  }
  
  flc100.process();
  if (commsHandler.process(responseBuffer, responseBufferLen))
    processResponse(responseBuffer, responseBufferLen);
  
  commandHandler.process(console, xrf);

  // console << "I2C state: " << (flc100.getI2CState()) << endl;
  if (flc100.isFinished()) {
    // Process SD card when normal sampling is not running; SD card
    // access can be slow and block.
    
    if (resultsProcessed == false) {
      resultsProcessed = true;
      console << flc100.getTimestamp() << '\t'
	      << flc100.getSensorTemperature() << '\t'
	      << flc100.getMcuTemperature() << '\t'
	      << flc100.getBatteryVoltage();
      for (uint8_t i = 0; i < FLC100::numAxes; ++i)
	console << '\t' << (flc100.getMagData()[i]);
      console << endl;
      
      console << "#Timestamp: " << flc100.getTimestamp() << endl
	      << "#Sensor temperature: " << flc100.getSensorTemperature() << endl
	      << "#MCU temperature: " << flc100.getMcuTemperature() << endl
	      << "#Battery voltage: " << flc100.getBatteryVoltage() << endl;
      for (uint8_t i = 0; i < FLC100::numAxes; ++i)
	console << "#magData[" << i << "]: " << (flc100.getMagData()[i])
		<< endl;

      // Buffer for storing the binary AW packet. Will also be used
      // when writing to SD card.
      const uint16_t bufferLength = 512;
      uint8_t buffer[bufferLength]; // Sector size for SD card is 512 bytes


      if (useSd) {
	// Check if the SD card circular buffer should be written to disk
	char newFilename[sdFilenameLen];
	createFilename(newFilename, sizeof(newFilename), flc100.getTimestamp());
	if ((strcmp(sdFilename, newFilename) != 0 ||
	     sdCircularBuffer.getSize() == sizeof(sdBuffer))
	    && sdFile) {
	  while (sdCircularBuffer.getSize() >= sdPacketSize) {
	    int i = sdCircularBuffer.read(buffer, sizeof(buffer));
	    sdFile.write(buffer, i);
	    sdFile.flush();
	  }
	  console << "Wrote to " << sdFilename << endl;
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
      
      AWPacket packet;
      packet.setKey(hmacKey, sizeof(hmacKey));
      packet.setFlagBit(AWPacket::flagsSampleTimingErrorBit, callbackWasLate);
      //packet.setTimestamp(flc100.getTimestamp());
      CounterRTC::Time now;
      cRTC.getTime(now);
      packet.setTimestamp(now.getSeconds(), now.getFraction());
      
      packet.putHeader(buffer, sizeof(buffer));
      // printBinaryBuffer(console, buffer, 20);
      // console << endl;
      console << "Header length: " << AWPacket::getPacketLength(buffer) << endl;
      for (uint8_t i = 0; i < FLC100::numAxes; ++i)
	if (flc100.getAdcPresent(i))
	  packet.putMagData(buffer, sizeof(buffer),
			    AWPacket::tagMagDataX + i,
			    flc100.getMagResGain()[i],
			    flc100.getMagData()[i]);
      packet.putDataInt16(buffer, sizeof(buffer),
			  AWPacket::tagSensorTemperature,
			  flc100.getSensorTemperature());
      packet.putDataInt16(buffer, sizeof(buffer),
			  AWPacket::tagMCUTemperature,
			  flc100.getMcuTemperature());
      packet.putDataUint16(buffer, sizeof(buffer),
			   AWPacket::tagBatteryVoltage,
			   flc100.getBatteryVoltage());
      // Upper 3 nibbles is seconds, lowest nibble is 16ths of second
      packet.putDataUint16(buffer, sizeof(buffer),
			   AWPacket::tagSamplingInterval,
			   (uint16_t(samplingInterval.getSeconds() << 4) |
			    samplingInterval.getFraction() >>
			    (CounterRTC::fractionsPerSecondLog2 - 4)));
      // samplingInterval);
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
      if (timeAdjustment > CounterRTC::Time())
	// TODO: check against overflow in int32_t, int16_t
	packet.putTimeAdjustment(buffer, sizeof(buffer),
				 timeAdjustment.getSeconds(),
				 timeAdjustment.getFraction());

      console << "Unpadded length: " << AWPacket::getPacketLength(buffer) << endl;
      if (useSd && AWPacket::getPacketLength(buffer) <= sdPacketSize) {
	// Add the latest packet to the SD card circular buffer, add
	// padding so that final size matches sdPacketSize
	uint16_t originalLength = AWPacket::getPacketLength(buffer);
	packet.putPadding(buffer, sizeof(buffer),
			  sdPacketSize - originalLength);
	sdCircularBuffer.write(buffer, sdPacketSize);
	console << "SD packet size: " << sdPacketSize << endl;
	// printBinaryBuffer(console, buffer, sdPacketSize);
	console << endl;
	if (verbosity)
	  AWPacket::printPacket(buffer, bufferLength, console);
	// 'Remove' padding by reverting to the original packet length
	AWPacket::setPacketLength(buffer, originalLength);
      }

      // TODO: Add padding      
      
      // Add the signature and send by XRF
      packet.putSignature(buffer, sizeof(buffer), commsBlockSize); 

      commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
      // DEBUG: message queued, turn on LED
      digitalWrite(LED_BUILTIN, HIGH);

      if (verbosity)
	AWPacket::printPacket(buffer, bufferLength, console);
    
      console << "# -----------" << endl;
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
      // packet.setTimestamp(flc100.getTimestamp());
      CounterRTC::Time now;
      cRTC.getTime(now);
      packet.setTimestamp(now.getSeconds(), now.getFraction());
      
      packet.putHeader(buffer, sizeof(buffer));
      packet.putGetFirmwarePage(buffer, sizeof(buffer),
				upgradeFirmwareVersion,
				upgradeFirmwareGetBlockNumber);
      
       // Add the signature and send by XRF
      packet.putSignature(buffer, sizeof(buffer), commsBlockSize); 

      commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
      // DEBUG: message queued, turn on LED
      digitalWrite(LED_BUILTIN, HIGH);
      
    }
    
    
    // Test if can go to sleep
    // if (!xrf.available() && xrfResponseTimeout.isExpired() &&
    // startSampling == false) {
    if (startSampling == false &&
	commsHandler.isFinished() &&
	samplingInterval >= minSleepInterval &&
	commsHandler.xrfPowerOff()) {

      struct RTCx::tm tm;
      rtc.readClock(tm);
      RTCx::time_t hwcTime = RTCx::mktime(tm);
      CounterRTC::Time now;
      cRTC.getTime(now);
      // Setting the RTC is likely to slightly upset the timing as it
      // stops the hardware clock briefly. Only set
      
      if (labs(hwcTime-now.getSeconds()) > 2*maxTimeError.getSeconds()+1) {
      	RTCx::time_t t = now.getSeconds();
      	RTCx::gmtime_r(&t, &tm);
      	rtc.setClock(tm);
	console << "Set HW clock\n";
      }

      console.flush();
      doSleep(SLEEP_MODE_PWR_SAVE);
      console << "SLEEP!\n";
    }
  }
  
}
  


