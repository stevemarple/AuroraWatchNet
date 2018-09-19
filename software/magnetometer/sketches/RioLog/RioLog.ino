/*
 * RioLog
 *
 * Firmware to support AuroraWatchNet magnetometer and cloud detector
 * hardware.
 *
 * Debugging and informational messages are sent to Serial. For 8MHz
 * and lower system clock frequencies the baud rate is 9600, otherwise
 * 115200 baud is used. Commands can be sent to Serial to alter the
 * behaviour from default; the behaviour is not persistent across
 * reboots, set EEPROM values for that. For the full list of commands
 * see CommandHandler.cpp. Commands should be terminated with a
 * carriage return or newline character.
 *
 * By default a minimal set of information is output to Serial, the
 * verbosity can be increased by sending "verbosity=n" where n is an
 * integer value to Serial.
 *
 * verbosity:
 *  0: minimal output (firmware update messages, system clock updated, DHCP)
 *  1: extended output
 *  2: differences between system and server or GNSS clock
 *  10: print message and response
 *  11: print all magnetometer data samples, print riometer data samples
 *  12: print GNSS messages
 */

#include <avr/eeprom.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <avr/boot.h>
#include <util/atomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "RioLog.h"

#include <Wire.h>
#include <Streaming.h>

#include <AWPacket.h>


// Fix up #defines for the ATmega1284 (non-P) to be more similar to the ATmega1284P #defines.
#if defined(FUSE_SUT_CKSEL0) && ! defined(FUSE_CKSEL0)
#define FUSE_CKSEL0 FUSE_SUT_CKSEL0
#endif
#if defined(FUSE_SUT_CKSEL1) && ! defined(FUSE_CKSEL1)
#define FUSE_CKSEL1 FUSE_SUT_CKSEL1
#endif
#if defined(FUSE_SUT_CKSEL2) && ! defined(FUSE_CKSEL2)
#define FUSE_CKSEL2 FUSE_SUT_CKSEL2
#endif
#if defined(FUSE_SUT_CKSEL3) && ! defined(FUSE_CKSEL3)
#define FUSE_CKSEL3 FUSE_SUT_CKSEL3
#endif


#if defined (FEATURE_FLC100) && defined (FEATURE_RIOMETER)
#error Cannot include FEATURE_FLC100 and FEATURE_RIOMETER simultaneously
#endif

#ifdef FEATURE_FLC100
#include <FLC100_shield.h>
#endif

#ifdef FEATURE_RIOMETER
#include <RioLogger.h>
#endif

#ifdef FEATURE_MLX90614
#include <SoftWire.h>
#include <MLX90614.h>
#endif

#ifdef FEATURE_HIH61XX
#error Please use FEATURE_HIH61XX_SOFTWIRE or FEATURE_HIH61XX_WIRE
#endif
#if defined(FEATURE_HIH61XX_SOFTWIRE) && defined(FEATURE_HIH61XX_WIRE)
#error No support for simultaneous SoftWare and Wire connections to HIH61xx
#endif

#ifdef FEATURE_HIH61XX_SOFTWIRE
#define FEATURE_HIH61XX
#include <SoftWire.h>
#include <HIH61xx.h>
#endif

#ifdef FEATURE_HIH61XX_WIRE
#define FEATURE_HIH61XX
#include <Wire.h>
#include <HIH61xx.h>
#endif

#ifdef FEATURE_AS3935
#include <AS3935.h>
#endif

#ifdef FEATURE_HOUSEKEEPING
#include <HouseKeeping.h>
#endif

#include <RTCx.h>
#include <CounterRTC.h>
#include <AsyncDelay.h>
#include <MCP342x.h>
#include <CircBuffer.h>
#include <CommsInterface.h>


#ifdef FEATURE_GNSS
// Sanity check, they use the same serial port
#ifdef COMMS_XRF
#error Cannot support both XRF communications and GNSS clock
#endif
#include <MicroNMEA.h>
#include <GNSS_Clock.h>
#endif

#if defined (COMMS_W5100) && defined (COMMS_W5500)
#error Cannot build for both WIZnet W5100 and W5500 simultaneously
#endif

#undef COMMS_ARCH_DEFINED

#ifdef COMMS_XRF
#define COMMS_ARCH_DEFINED
#include <XRF_Radio.h>
#endif

#ifdef COMMS_W5100
#define COMMS_ARCH_DEFINED
#include <SPI.h>
#include <EthernetWDT.h>
#include <Dns.h>
#include <Dhcp.h>
#include <WIZnet_UDP.h>
#endif

#ifdef COMMS_W5500
#define COMMS_ARCH_DEFINED
#include <SPI.h>
#include <Ethernet2.h>
#include <Dns.h>
#include <Dhcp.h>
#include <WIZnet_UDP.h>
#endif

#ifndef COMMS_ARCH_DEFINED
// One or more communication architectures are required. Build from
// command line or include custom_include.h.
#error No communications architecture defined
#endif

//#include <SD.h>

#include <CircularStack.h>
#include <AwEeprom.h>
#include <DisableJTAG.h>

#include <CommandHandler.h>
#include "CommsHandler.h"

#include "xbootapi.h"

#ifdef FEATURE_MEM_USAGE
#include <MemoryFree.h>
#endif


#define STRINGIFY(a) STRINGIFY2(a)
#define STRINGIFY2(a) #a

#define FIRMWARE_VERSION "RioLog-0.2a"
//                        1234567890123456
// Firmware version limited to 16 characters

const char firmwareVersion[AWPacket::firmwareNameLength] = FIRMWARE_VERSION;

const char features_P[] PROGMEM = {
    "Features:"
#ifdef FEATURE_HOUSEKEEPING
    " HOUSEKEEPING"
#endif
#ifdef FEATURE_FLC100
    " FLC100"
#endif
#ifdef FEATURE_RIOMETER
     " RIOMETER"
#endif
#ifdef FEATURE_HIH61XX_SOFTWIRE
     " HIH61XX(SoftWire)"
#endif
#ifdef FEATURE_HIH61XX_WIRE
     " HIH61XX(Wire)"
#endif
#ifdef FEATURE_MLX90614
     " MLX90614"
#endif
#ifdef FEATURE_GNSS
     " GNSS"
#endif
#ifdef FEATURE_DATA_QUALITY
     " DATA_QUALITY"
#endif
#ifdef FEATURE_BUSY_TIME_PIN
    " BUSY_TIME_PIN(" EXPAND_STR(FEATURE_BUSY_TIME_PIN) ")"
#endif
#ifdef FEATURE_MEM_USAGE
     " MEM_USAGE"
#endif
};

const char comms_P[] PROGMEM = {
    "Comms:"
#ifdef COMMS_XRF
     " XRF"
#endif
#ifdef COMMS_W5100
     " W5100"
#ifdef ETHERNETWDT_USE_WDT
     "(wdt_reset)"
#endif
#endif
#ifdef COMMS_W5500
     " W5500"
#ifdef ETHERNET2_USE_WDT
     "(wdt_reset)"
#endif
#endif
};

const char *sep = ", ";

uint8_t ledPin = LED_BUILTIN;
const uint8_t fanPin = eeprom_read_byte((uint8_t*)EEPROM_FAN_PIN);
const uint8_t heaterPin = eeprom_read_byte((uint8_t*)EEPROM_HEATER_PIN);

// Flag to indicate if LED should be switched on. To ensure minimal
// power consumption it is always switched off.
bool useLed = false;
uint8_t maxMessagesLed = eeprom_read_byte((uint8_t*)EEPROM_MAX_MESSAGES_LED);

// Number of messages transmitted. Rollover is expected and must be
// planned for!
uint8_t messageCount = 0;

HardwareSerial& console = Serial;
uint8_t radioType;

#ifdef COMMS_XRF
HardwareSerial& xrfSerial = Serial1;
XRF_Radio xrf(xrfSerial);
const uint8_t xrfSleepPin = 7;
const uint8_t xrfOnPin = 23;
const uint8_t xrfResetPin = 5;
#endif

#if defined(COMMS_W5100) || defined(COMMS_W5500)
WIZnet_UDP wiz_udp;
#endif

#ifdef FEATURE_VERBOSITY
uint8_t verbosity = FEATURE_VERBOSITY;
#else
uint8_t verbosity = 0;
#endif

uint16_t maxTimeNoAck = eeprom_read_word((const uint16_t*)EEPROM_MAX_TIME_NO_ACK);

#ifdef FEATURE_FLC100
#define SENSOR_FLASH_STRING "Mag"
typedef FLC100 SensorShield_t;
FLC100 sensorShield;
bool sensorShieldPresent = eeprom_read_byte((uint8_t*)EEPROM_FLC100_PRESENT);
#endif

#ifdef FEATURE_RIOMETER
#define SENSOR_FLASH_STRING "Rio"
typedef RioLogger SensorShield_t;
RioLogger sensorShield;
bool sensorShieldPresent = eeprom_read_byte((uint8_t*)EEPROM_RIO_PRESENT);
#endif

#ifdef FEATURE_MLX90614
MLX90614 mlx90614;
bool mlx90614Present = eeprom_read_byte((uint8_t*)EEPROM_MLX90614_PRESENT);
#endif

#ifdef FEATURE_HIH61XX_SOFTWIRE
SoftWire hih61xxSoftWire(A4, A5);
HIH61xx<SoftWire> hih61xx(hih61xxSoftWire);
#endif

#ifdef FEATURE_HIH61XX_WIRE
HIH61xx<TwoWire> hih61xx(Wire);
#endif

#ifdef FEATURE_HIH61XX
bool hih61xxPresent = eeprom_read_byte((uint8_t*)EEPROM_HIH61XX_PRESENT);
#endif

#ifdef FEATURE_AS3935
AS3935 as3935;
bool as3935Present = eeprom_read_byte((uint8_t*)EEPROM_AS3935_PRESENT);
CounterRTC::Time as3935Timestamp;
#endif


#ifdef FEATURE_GNSS
HardwareSerial& gnssSerial = Serial1;
const uint8_t gnssPpsPin = 6;
volatile bool ppsTriggered = false;
volatile AsyncDelay ppsTimeout;
volatile bool useGnss = false;
char gnssBuffer[85];
RTCx::time_t gnssFixTime;
bool gnssFixValid = false;
long gnssLocation[3];
bool altitudeValid;
char navSystem;
uint8_t numSat;
uint8_t hdop;
#endif

#ifdef FEATURE_DATA_QUALITY
bool dataQualityWarning = false;
uint8_t dataQualityInputPin = eeprom_read_byte((uint8_t*)EEPROM_DATA_QUALITY_INPUT_PIN);
uint8_t dataQualityInputActiveLow = eeprom_read_byte((uint8_t*)EEPROM_DATA_QUALITY_INPUT_ACTIVE_LOW);
// Flag set by dataQualityISR() to indicate sleep mode should be
// terminated early
volatile bool dataQualityChanged = false;
#endif

//uint8_t deviceSignature[3] = {0, 0, 0};
uint32_t deviceSignature = 0;
const __FlashStringHelper *deviceName = nullptr;

// Commands
void cmdEepromRead(const char *s);
void cmdEepromWrite(const char *s);
void cmdVerbosity(const char *s);
void cmdReboot(const char *s);
void cmdSamplingInterval(const char *s);
#if USE_SD_CARD
void cmdUseSd(const char *s);
#endif
void unknownCommand(const char *s);
void commandTooLong(int);

CommandHandler commandHandler;
char commandBuffer[80];

#if USE_SD_CARD
    const int numCommands = 6;
#else
    const int numCommands = 5;
#endif
CommandOption commands[numCommands] = {
    CommandOption("eepromRead=", cmdEepromRead),
    CommandOption("eepromWrite=", cmdEepromWrite),
    CommandOption("verbosity", cmdVerbosity),
    CommandOption("reboot=TRUE", cmdReboot),
    CommandOption("samplingInterval_16th_s", cmdSamplingInterval),
#if USE_SD_CARD
    CommandOption("useSd"), cmdUseSd),
#endif
};


// ----- Configure the communications handler -----
// Set if packets should be multiple of some particular length
uint16_t commsBlockSize = 0;

// Allocate a buffer to use for messages. This must be able to hold the biggest message.
#ifdef FEATURE_RIOMETER
const uint16_t commsMessageBufferLen = 1024;
#else
const uint16_t commsMessageBufferLen = 512;
#endif
uint8_t commsMessageBuffer[commsMessageBufferLen];

// The comms handler stores unacknowledged messages in a stack. Allocate a suitable size buffer for the stack to use.
const uint16_t commsStackBufferLen = 8192;
uint8_t commsStackBuffer[commsStackBufferLen];
//CommsHandler commsHandler(commsStackBuffer, commsStackBufferLen);
CommsHandler commsHandler(commsMessageBuffer, commsMessageBufferLen, commsStackBuffer, commsStackBufferLen);
// -----

CounterRTC::Time lastAcknowledgement;

const uint16_t responseBufferLen = 400;
uint8_t responseBuffer[responseBufferLen];

// Maximum allowable time error for the system clock (cRTC)
const CounterRTC::Time maxSystemTimeError(1, 0);

// Hardware clock can only be set to nearest second
const RTCx::time_t maxHardwareClockTimeError = 2;

// Most recent time adjustment. Sent on all outgoing packets until a
// message acknowledgement is received, at which point it is set to
// zero.
CounterRTC::Time timeAdjustment(0, 0);

// Don't sleep if samplingInterval is less than this value
uint16_t counter2Frequency = 0;
CounterRTC::Time minSleepInterval(2, 0);
CounterRTC::Time samplingInterval(30, 0);
CounterRTC::Time minSamplingInterval(5, 0); // Overridden later for Ethernet
CounterRTC::Time maxSamplingInterval(600, 0);

bool enableSleep = true;
uint8_t hmacKey[EEPROM_HMAC_KEY_SIZE] = {
	255, 255, 255, 255, 255, 255, 255, 255,
	255, 255, 255, 255, 255, 255, 255, 255};

// Flag indicating if all data samples should be sent, or just the aggregate
bool allSamples = false;

#ifdef FEATURE_SD_CARD
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

#ifdef FEATURE_SD_CARD
// /data/YYYY/MM/DD/YYYYMMDD.HH
// 123456789012345678901234567890
const uint8_t sdFilenameLen = 29; // Remember to include space for '\0'
char sdFilename[sdFilenameLen] = "OLD_FILE";
File sdFile;
#endif

volatile bool crtcTriggered = true;
volatile bool callbackWasLate = true;

// Code to ensure watchdog is disabled after reboot code. Also takes a
// copy of MCUSR register.
static uint8_t mcusrCopy;
void get_mcusr(void)
{
	mcusrCopy = MCUSR;
	MCUSR = 0;
	wdt_disable();
}


void crtcCallback(uint8_t alarmNum __attribute__ ((unused)), bool late, const void *context __attribute__ ((unused)) )
{
	// Indicate that main loop should commence sampling
	crtcTriggered = true;
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
    console << F("crtcCallback()  LATE ====\n");
    extern CounterRTC::Time alarmBlockTime[CounterRTC::numAlarms];
    extern uint8_t alarmCounter[CounterRTC::numAlarms];
    console << F("alarm block: ") <<  alarmBlockTime[0].getSeconds()
	<< ' ' << alarmBlockTime[0].getFraction()
	<< ' ' << _DEC(alarmCounter[0])
	<< F("\nnow: ") << now.getSeconds() << ' ' << now.getFraction() << endl;
	}
	else
    console << F("crtcCallback()\n");
	console << F("alarmTime: ") << t.getSeconds() << ' ' << t.getFraction() << endl;
	// --------------------
	*/
	cRTC.setAlarm(0, t, crtcCallback);
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

#ifdef FEATURE_SD_CARD
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

	while (!crtcTriggered
#ifdef FEATURE_DATA_QUALITY
		   && !dataQualityChanged
#endif
		   ) {
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
#if defined(BODS) && defined(BODSE)
#if defined(__AVR_ATmega644P__) || defined(__AVR_ATmega1284P__)
        // The only significant difference of the ATmega1284 (non-P) from the ATmega1284P is the inability
        // to disable brownout detection during sleeping. Don't try disabling BOD if the signature byte
        // indicates code compiled for an ATmega1284P is actually running on an ATmega1284 (non-P). Likewise for '644,.
        if (deviceSignature != DEVICE_SIG_ATMEGA644 && deviceSignature != DEVICE_SIG_ATMEGA1284)
    		sleep_bod_disable();  // Disable brown-out detection for sleeping
#else
        sleep_bod_disable();  // Disable brown-out detection for sleeping
#endif
#else
#warning Brownout cannot be disabled in sleep mode for this MCU
#endif
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
	// Cancel sending firmware version, boot flags etc
	firstMessage = false;

	// Cancel any previous time adjustment. If there was one the server
	// is aware since we have received a response packet.
	timeAdjustment = CounterRTC::Time(0, 0);

	// Cancel sending firmware version
	sendFirmwareVersion = false;

	// Cancel previous request for EEPROM contents
	eepromContentsLength = 0;

	// Message received, turn off LED
	digitalWrite(ledPin, LOW);

	AWPacket::parsePacket(responseBuffer, responseBufferLen,
						  &console,
						  processResponseTags, AWPacket::printUnknownTag);
	if (verbosity == 10) {
		console << F("====\nResponse:\n");
		AWPacket::printPacket(responseBuffer, responseBufferLen, console);
		console << F("====\n");
	}

	// Update the time of the last acknowledgement. Do this after
	// processing the tags since the system clock may have been updated
	// from the server.
	cRTC.getTime(lastAcknowledgement);
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
#ifdef FEATURE_GNSS
		// When GNSS timing is in operation don't adjust the clock based
		// on time received from the server
		if (useGnss)
			break;

#endif
		{
			int32_t secs;
			int16_t frac;
			CounterRTC::Time ourTime;
			cRTC.getTime(ourTime);

			AWPacket::networkToAvr(&secs, data, sizeof(secs));
			AWPacket::networkToAvr(&frac, data + sizeof(secs), sizeof(frac));
			CounterRTC::Time serverTime(secs, frac);

			CounterRTC::Time timeError = ourTime - serverTime;
			CounterRTC::Time absTimeError = abs_(timeError);

			if (absTimeError > maxSystemTimeError) {
				cRTC.setTime(serverTime);
				if (absTimeError > samplingInterval)
					// Update alarm since it might be a long time in the future
					cRTC.setAlarm(0, serverTime + samplingInterval,
								  crtcCallback);

				console << F("Time set from server\n");
				timeAdjustment = -timeError;
			}
			if (verbosity > 1) {
				console << F("Server time: ") << secs << ' ' << frac
						<< F("\nOur time: ")  << ourTime.getSeconds() << ' '
						<< ourTime.getFraction()
						<< F("\nTime error (our-server): ")
						<< timeError.getSeconds() << sep
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

			(*s) << F("SAMPLING INTERVAL CHANGED! ")
				 << samplingInterval.getSeconds() << sep
				 << samplingInterval.getFraction() << endl;
		}
		break;

	case AWPacket::tagReboot:
		console << F("Reboot command received from server\n");
		console.flush();
		reboot();
		break;

	case AWPacket::tagUpgradeFirmware:
		if (upgradeFirmwareVersion[0] == '\0') {
			// Not currently upgrading, honour request
			memcpy(upgradeFirmwareVersion, data, AWPacket::firmwareNameLength);
			upgradeFirmwareVersion[sizeof(upgradeFirmwareVersion)-1] = '\0';
			console << F("Received upgrade firmware tag: ")
					<< upgradeFirmwareVersion << endl;
			if (strncmp(upgradeFirmwareVersion, firmwareVersion,
						AWPacket::firmwareNameLength) == 0) {
				// Same as current so clear upgradeFirmwareVersion.
				upgradeFirmwareVersion[0] = '\0';
				console << F("Already have firmware version ") << firmwareVersion
						<< endl;

				// TODO: Send firmwareVersion so that server knows to cancel
				// the request.
				sendFirmwareVersion = true;
				break;
			}
			console << F("Upgrade firmware to ") << upgradeFirmwareVersion << endl;

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
			console << F("Processing FW upgrade ") << upgradeFirmwareGetBlockNumber
					<< ' ' << i << endl;
			memcpy(spmBuffer + (i * AWPacket::firmwareBlockSize),
				   data + AWPacket::firmwareNameLength +
				   AWPacket::sizeOfFirmwarePageNumber,
				   AWPacket::firmwareBlockSize);
			if (i == blocksPerSpmPage - 1) {
				if (upgradeFirmwareGetBlockNumber == blocksPerSpmPage - 1) {
					uint8_t r = xboot_app_temp_erase();
					console << F("Erased temporary application area in flash ")
							<< r << endl;
				}

				// TODO: check if SPM page differs before writing to flash?
				uint32_t addr = ((upgradeFirmwareGetBlockNumber - i) *
								 (uint32_t)AWPacket::firmwareBlockSize);
				uint8_t r = xboot_app_temp_write_page(addr, spmBuffer, 0);
				console << F("copied spmBuffer to flash: ") << addr << ' ' << r << endl;
			}

			if (upgradeFirmwareGetBlockNumber == upgradeFirmwareNumBlocks - 1) {
				console << F("Firmware download for ") << upgradeFirmwareVersion
						<< F(" completed\n");

				if (i != blocksPerSpmPage - 1) {
					// Ensure partially filled buffer to written to flash
					memset(spmBuffer + ((i+1) * AWPacket::firmwareBlockSize), 0xFF,
						   (blocksPerSpmPage - (i+1)) * AWPacket::firmwareBlockSize);
					// TODO: check if SPM page differs before writing to flash?
					uint32_t addr = ((upgradeFirmwareGetBlockNumber - i) *
									 (uint32_t)AWPacket::firmwareBlockSize);
					uint8_t r = xboot_app_temp_write_page(addr, spmBuffer, 0);

					console << F("copied partial spmBuffer to flash: ") << addr
							<< ' ' << r << endl;
				}

				// Disable further upgrades
				// *upgradeFirmwareVersion = '\0';
				// TODO: CRC and issue command to upgrade/reboot
				uint16_t crc;
				uint8_t crcStatus = xboot_app_temp_crc16(&crc);
				console << F("Firmware CRC: ") << upgradeFirmwareCRC
						<< F("\nDownload CRC: ") << crc
						<< F("\nCRC status: ") << crcStatus << endl;
				delay(100);
				uint8_t installResult =  xboot_install_firmware(upgradeFirmwareCRC);
				console << F("Install FW result: ") << installResult << endl;
				console.flush();
				reboot();
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

#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
	case AWPacket::tagNumSamples:
		{
			uint8_t numSamples, control;
			AWPacket::networkToAvr(&numSamples, data, sizeof(numSamples));
			data += sizeof(numSamples);
			if (numSamples) {
				AWPacket::networkToAvr(&control, data, sizeof(control));
				sensorShield.setNumSamples(numSamples,
										   control & EEPROM_AGGREGATE_USE_MEDIAN,
										   control & EEPROM_AGGREGATE_TRIM_SAMPLES);
			}
		}
		break;
#endif

	case AWPacket::tagAllSamples:
		{
			uint8_t all;
			AWPacket::networkToAvr(&all, data, sizeof(all));
			allSamples = (all != 0);
		}
		break;

	} // end of switch

	return false;
}


#ifdef FEATURE_AS3935
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


#if defined(COMMS_W5100) || defined(COMMS_W5500)
int dnsLookup(IPAddress dnsServer, const char *hostname,
			  IPAddress &result)
{
	DNSClient dns;
#if (defined(COMMS_W5100) && !defined(ETHERNETWDT_USE_WDT)) || (defined(COMMS_W5500) && !defined(ETHERNET2_USE_WDT))
    // Temporarily disable watchdog timer because slow DNS responses
    // can force an endless reboot cycle.
    wdt_disable();
#endif

	dns.begin(dnsServer);
	int r = dns.getHostByName(hostname, result);
#if (defined(COMMS_W5100) && !defined(ETHERNETWDT_USE_WDT)) || (defined(COMMS_W5500) && !defined(ETHERNET2_USE_WDT))
	wdt_enable(WDTO_8S);
#endif
	return r;
}

void printEthernetSettings(Stream &s,
						   const IPAddress &localIP, uint16_t localPort,
						   const IPAddress &subnetMask,
						   const IPAddress &gatewayIP,
						   const IPAddress (&dns)[EEPROM_NUM_DNS],
						   const IPAddress &remoteIP, uint16_t remotePort)
{
	s << F("  Local: ") << localIP << ':' << localPort << F("\n  Mask: ")
	  << subnetMask << F("\n  GW: ")
	  << gatewayIP << F("\n  DNS: ");

	bool dnsFound = false;
	for (uint8_t n = 0; n < EEPROM_NUM_DNS; ++n)
		if (uint32_t((IPAddress)dns[n])) {
			if (dnsFound)
				s << sep;
			s << dns[n];
			dnsFound = true;
		}
	if (!dnsFound)
		s << F("(none)");

	s << F("\n  Remote: ") << remoteIP << ':' << remotePort << endl;
}


void begin_WIZnet_UDP(void)
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

	console << F("EEPROM settings:\n  MAC: ");
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
	console << F("  Remote hostname: ") << remoteHostname << endl;

	wdt_reset();
	if (uint32_t(localIP)) {
		// Static IP
		console << F("Using static IP\n");
		Ethernet.begin(macAddress, localIP, dns[0], gateway, netmask);
	}
	else {
		// Use DHCP to obtain dynamic IP
		console << F("Requesting IP... ");
		console.flush();
#if (defined(COMMS_W5100) && !defined(ETHERNETWDT_USE_WDT)) || (defined(COMMS_W5500) && !defined(ETHERNET2_USE_WDT))
		// Temporarily disable watchdog timer because slow DHCP requests
		// can force an endless reboot cycle.
		wdt_disable();
#endif
		if (Ethernet.begin(macAddress) == 0) {
			console << F("DHCP failed");
			console.flush();
			reboot();
		}
		wdt_enable(WDTO_8S);

		dns[0] = Ethernet.dnsServerIP(); // Primary IP from DHCP
		// Disable sleeping. It prevents millis() from working correctly
		// which breaks the DHCP lease maintenance.
		enableSleep = false;
		console.println(F("done"));
	}
	wdt_reset();

	if (isprint(remoteHostname[0])) {
		// Lookup IP address of remote hostname.
		console << F("Looking up ") << remoteHostname << endl;
		IPAddress ip;
		bool found = false;
		for (uint8_t t = 0; t < 3; ++t)
			for (uint8_t n = 0; n < EEPROM_NUM_DNS; ++n) {
				wdt_reset();
				// Attempt lookup only if DNS server IP non-zero. Check also
				// the IP address is non-zero.
				if (uint32_t(dns[n]) &&
					(dnsLookup(dns[n], remoteHostname, ip) == 1 && ip)) {
					found = true;
					break;
				}
			}
		if (found) {
			console << remoteHostname << F(" resolves to ") << ip;
			remoteIP = ip;
		}
		else
			// Fall back to EEPROM setting for IP address
			console << F("Cannot resolve ") << remoteHostname;

		console.println();
	}

	if (uint32_t(remoteIP) == 0) {
		// Cannot resolve (or undefined) remote host and no fallback
		// IP. Try broadcasting on local subnet in the hope of finding a
		// server.
		IPAddress broadcastIP(uint32_t(Ethernet.localIP()) |
							  ~uint32_t(Ethernet.subnetMask()));
		remoteIP = broadcastIP;

		// Override the value of maxTimeNoAck to force a reboot to occur
		// soon. If the problem is due to a misconfiguration this approach
		// may give some opportunity for remote recovery; if the failure
		// is just due to DNS problems then it should recover when DNS
		// returns.
#define REMOTE_HOST_RECOVERY_PERIOD 120
		maxTimeNoAck = REMOTE_HOST_RECOVERY_PERIOD;
		console << F("No remote host, trying for "
					 STRINGIFY(REMOTE_HOST_RECOVERY_PERIOD)
					 "s to communicate to ") << broadcastIP << endl;
	}

	console << F("Active settings:\n");
	printEthernetSettings(console, Ethernet.localIP(), localPort,
						  Ethernet.subnetMask(), Ethernet.gatewayIP(),
						  dns, remoteIP, remotePort);
	console.flush();
	wiz_udp.begin(localPort, remoteIP, remotePort, 10, 4);
}
#endif


#ifdef FEATURE_GNSS
void gnssPpsCallback(volatile const GNSS_Clock __attribute__((unused)) &clock)
{
#ifdef FEATURE_BUSY_TIME_PIN
    digitalWrite(FEATURE_BUSY_TIME_PIN, HIGH);
#endif

	if (!clock.isValid()) {
		useGnss = false;
		return;
	}

	if (useGnss)
		if (ppsTimeout.isExpired()) {
			// Don't use this pulse, nor the next one.
			useGnss = false;
			return;
		}
		else
			ppsTriggered = true;
	else
		// Don't use this pulse but accept the next one if it occurs
		// within the expected time interval
		useGnss = true;

	// Allow for some delay in responding to the the PPS interrupt and
	// for timing errors by millis() as the system clock frequency may
	// not be accurate.
	ppsTimeout.start(1200, AsyncDelay::MILLIS);
}
#endif

#ifdef FEATURE_DATA_QUALITY
void dataQualityISR(void)
{
	dataQualityChanged = true;
}
#endif


#if defined(COMMS_W5100) || defined(COMMS_W5500)
void maintainDhcpLease(void)
{
	if (radioType == EEPROM_COMMS_TYPE_XRF)
		return;
	uint8_t m = Ethernet.maintain();

	__FlashStringHelper* dhcpStr = (__FlashStringHelper*)PSTR("DHCP lease ");
  
	if (m == DHCP_CHECK_NONE) {
		if (verbosity == 1) {
			console.print(dhcpStr);
			console.println(F("ok"));
		}
		return;
	}

	// Always print all remaining conditions, even with verbosity == 0
	console.print(dhcpStr);
	switch (m) {
		//  case DHCP_CHECK_NONE:
		// Already processed above
		// break;
	case DHCP_CHECK_RENEW_FAIL:
	case DHCP_CHECK_REBIND_FAIL:
		console.println(F("failed"));
		console.flush();
		reboot();
		break;
	case DHCP_CHECK_RENEW_OK:
		console.println(F("renewed"));
		break;
	case DHCP_CHECK_REBIND_OK:
		console.println(F("rebind"));
		break;
	default:
		console << F("maintain returned ") << _DEC(m) << endl;
	}

}
#endif


void generalCallReset(void)
{
	Wire.beginTransmission(0x00);
	Wire.write(0x06);
	Wire.endTransmission();
}


void generalCallLatch(void)
{
	Wire.beginTransmission(0x00);
	Wire.write(0x04);
	Wire.endTransmission();
}


void createDeviceName(void)
{
    deviceName = F("Unknown MCU");

    // __FlashStringHelper *deviceName = F("Unknown MCU");
#if defined(__AVR_ATmega644__) || defined(__AVR_ATmega644P__) || defined(__AVR_ATmega1284__) || defined(__AVR_ATmega1284P__)
    switch (deviceSignature) {
        case DEVICE_SIG_ATMEGA644:
            deviceName = F("atmega644");
            break;
        case DEVICE_SIG_ATMEGA644P:
            deviceName = F("atmega644p");
            break;
        case DEVICE_SIG_ATMEGA1284:
            deviceName = F("atmega1284");
            break;
        case DEVICE_SIG_ATMEGA1284P:
            deviceName = F("atmega1284p");
            break;
    }
#endif
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

#ifdef FEATURE_BUSY_TIME_PIN
    pinMode(FEATURE_BUSY_TIME_PIN, OUTPUT);
    digitalWrite(FEATURE_BUSY_TIME_PIN, LOW);
#endif

#if defined (FEATURE_FLC100)
	uint8_t adcAddressList[SensorShield_t::maxNumAdcs] = {0x6E, 0x6A, 0x6C};
	uint8_t adcChannelList[SensorShield_t::maxNumAdcs] = {1, 1, 1};
	uint8_t adcResolutionList[SensorShield_t::maxNumAdcs] = {18, 18, 18};
	uint8_t adcGainList[SensorShield_t::maxNumAdcs] = {1, 1, 1};
#elif defined (FEATURE_RIOMETER)
	uint8_t adcAddressList[SensorShield_t::maxNumAdcs] = {
		0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F};
	uint8_t adcChannelList[SensorShield_t::maxNumAdcs] = {
		1, 1, 1, 1, 1, 1, 1, 1 };
	uint8_t adcResolutionList[SensorShield_t::maxNumAdcs] = {
		14, 14, 14, 14, 14, 14, 14, 14};
	uint8_t adcGainList[SensorShield_t::maxNumAdcs] = {
		1, 1, 1, 1, 1, 1, 1, 1 };
#endif

	uint32_t consoleBaudRate;
	eeprom_read_block(&consoleBaudRate, (void*)EEPROM_CONSOLE_BAUD_RATE,
					  EEPROM_CONSOLE_BAUD_RATE_SIZE);

	if (consoleBaudRate > 260000L || consoleBaudRate < 4800)
		// Ignore EEPROM  value and use a sensible default
		if (F_CPU > 8000000L)
			console.begin(115200);
		else
			console.begin(9600);
	else
		console.begin(consoleBaudRate);
	console.flush();

	// Explicitly set the pull-ups for the serial port in case the
	// Arduino IDE disables them.
#if defined (__AVR_ATmega644__) || defined (__AVR_ATmega644P__)			\
	|| defined (__AVR_ATmega1284__) || defined (__AVR_ATmega1284P__)
	MCUSR &= ~(1 << PUD); // Allow pull-ups on UARTS
	PORTD |= ((1 << PORTD0) | (1 << PORTD2));
#else
#error No pull-ups enabled for serial ports
#endif

	// Print fuses
	uint8_t lowFuse = boot_lock_fuse_bits_get(GET_LOW_FUSE_BITS);
	uint8_t highFuse = boot_lock_fuse_bits_get(GET_HIGH_FUSE_BITS);
	uint8_t extendedFuse = boot_lock_fuse_bits_get(GET_EXTENDED_FUSE_BITS);

    // Get (and print) the signature of the actual device, not what the code was compiled for!
	for (uint8_t i = 0; i < 3; ++i) {
	    deviceSignature <<= 8;
    	deviceSignature |= (boot_signature_byte_get(i * 2) & 0xFF);
    }

    console << F("\n\n--------\nTarget MCU: " EXPAND_STR(CPU_NAME));

#if defined(__AVR_ATmega644__) || defined(__AVR_ATmega644P__) || defined(__AVR_ATmega1284__) || defined(__AVR_ATmega1284P__)
    switch (deviceSignature) {
        case DEVICE_SIG_ATMEGA644:
            deviceName = F("atmega644");
            break;
        case DEVICE_SIG_ATMEGA644P:
            deviceName = F("atmega644p");
            break;
        case DEVICE_SIG_ATMEGA1284:
            deviceName = F("atmega1284");
            break;
        case DEVICE_SIG_ATMEGA1284P:
            deviceName = F("atmega1284p");
            break;
    }
#endif

    console << F("\nActual MCU: ") << deviceName;

#ifdef __AVR__
	console << F("\nSignature: ") << _HEX(deviceSignature)
	        << F("\nLow fuse: ") << _HEX(lowFuse)
			<< F("\nHigh fuse: ") << _HEX(highFuse)
			<< F("\nExtended fuse: ") << _HEX(extendedFuse);

	// Is the internal RC oscillator in use? Programmed fuses read low
	uint8_t ckselMask = (uint8_t)~(FUSE_CKSEL3 & FUSE_CKSEL2 &
								   FUSE_CKSEL1 & FUSE_CKSEL0);
	bool isRcOsc = ((lowFuse & ckselMask) ==
					((FUSE_CKSEL3 & FUSE_CKSEL2 & FUSE_CKSEL0) & ckselMask));
	console << F("\nRC osc.: ") << isRcOsc
			<< F("\nCKSEL: ") << _HEX(lowFuse & ckselMask)
			<< F("\nMCUSR: ") << _HEX(mcusrCopy);
#endif


	// Print the firmware version, clock speed and supported
	// communication protocols. Place in one long string to minimise
	// flash usage.
	console << F(
	        "\n"
             "MCU clock: " F_CPU_STR "\n"
             "Firmware: " FIRMWARE_VERSION "\n"
             "Epoch: " STRINGIFY(RTCX_EPOCH) "\n")
            << ((__FlashStringHelper*)comms_P) << endl
            << ((__FlashStringHelper*)features_P) << endl;

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
    console << F("Fan temp.: ")
			<< ((int16_t)eeprom_read_word((const uint16_t*)
		EEPROM_FAN_TEMPERATURE))
			<< endl;
    console << F("Fan hyst.: ")
			<< ((int16_t)eeprom_read_word((const uint16_t*)
		EEPROM_FAN_HYSTERESIS))
			<< endl;
    }

#ifdef FEATURE_SD_CARD
	uint8_t sdSelect = eeprom_read_byte((uint8_t*)EEPROM_SD_SELECT);
	useSd = (eeprom_read_byte((uint8_t*)EEPROM_USE_SD) == 1);
	if (sdSelect < NUM_DIGITAL_PINS) {
        pinMode(sdSelect, OUTPUT); // Onboard SD card
        digitalWrite(sdSelect, HIGH);
        if (useSd) {
        if (!SD.begin(sdSelect)) {
        console << F("Cannot initialise SD card on #") << sdSelect << endl;
        useSd = false;
        }
        else
            console << F("SD configured on #") << sdSelect << endl;
        }
        else {
        digitalWrite(sdSelect, HIGH);
        console << F("SD disabled on #") << sdSelect << endl;
        }
    }
#endif

	console << F("Site ID: ")
			<< eeprom_read_word((const uint16_t*)EEPROM_SITE_ID)
			<< endl;

	// Copy key from EEPROM
	console << F("HMAC key: ");
	for (uint8_t i = 0; i < EEPROM_HMAC_KEY_SIZE; ++i) {
        hmacKey[i] = eeprom_read_byte((const uint8_t*)(EEPROM_HMAC_KEY + i));
        console << ' ' << _HEX(hmacKey[i]);
    }
	console.println();

	Wire.begin();
    generalCallReset();
    generalCallLatch();

	// Get key
	eeprom_read_block(hmacKey, (uint8_t*)EEPROM_HMAC_KEY, EEPROM_HMAC_KEY_SIZE);
	AWPacket::setDefaultSiteId(eeprom_read_word((const uint16_t*)EEPROM_SITE_ID));

	__FlashStringHelper* initialisingStr
		= (__FlashStringHelper*)PSTR("Initialising ");
	__FlashStringHelper* notStr = (__FlashStringHelper*)PSTR(" not");
	__FlashStringHelper* presentStr = (__FlashStringHelper*)PSTR(" present");
	__FlashStringHelper* powerUpDelayStr
		= (__FlashStringHelper*)PSTR(" power-up delay (ms): ");

#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
	// Turn on 5V supply
	pinMode(FLC100_POWER, OUTPUT);
	digitalWrite(FLC100_POWER, HIGH);
	delay(SensorShield_t::powerUpDelay_ms);

	// Get ADC addresses
	uint16_t eepromAddress;
	uint8_t sz;
	for (uint8_t i = 0; i < SensorShield_t::maxNumAdcs; ++i) {
#if defined (FEATURE_FLC100)
		eepromAddress = EEPROM_ADC_ADDRESS_LIST;
		sz =  EEPROM_ADC_ADDRESS_LIST_SIZE;
#elif defined (FEATURE_RIOMETER)
		eepromAddress = EEPROM_GENERIC_ADC_ADDRESS_LIST;
		sz =  EEPROM_GENERIC_ADC_ADDRESS_LIST_SIZE;
#endif    
		if (i < sz) {
			uint8_t i2cAddress =
				eeprom_read_byte((uint8_t*)(eepromAddress + i));
			if (i2cAddress > 0 && i2cAddress <= 127)
				adcAddressList[i] = i2cAddress;
		}

#if defined (FEATURE_FLC100)
		eepromAddress = EEPROM_ADC_CHANNEL_LIST;
		sz =  EEPROM_ADC_CHANNEL_LIST_SIZE;
#elif defined (FEATURE_RIOMETER)
		eepromAddress = EEPROM_RIO_RIOMETER_ADC_CHANNEL_LIST;
		sz =  EEPROM_RIO_RIOMETER_ADC_CHANNEL_LIST_SIZE;
#endif    
		if (i < sz) {
			uint8_t chan =
				eeprom_read_byte((uint8_t*)(eepromAddress + i));
			if (chan && chan <= MCP342x::numChannels)
				adcChannelList[i] = chan;
		}

		uint8_t res = 0;
#if defined (FEATURE_FLC100)
		if (i < EEPROM_ADC_RESOLUTION_LIST_SIZE)
			res = eeprom_read_byte((uint8_t*)(EEPROM_ADC_RESOLUTION_LIST + i));
#elif defined (FEATURE_RIOMETER)
		// Same for all
		res = eeprom_read_byte((uint8_t*)(EEPROM_RIO_RIOMETER_ADC_RESOLUTION));
#else
#error Bad logic
#endif
		if (res && res <= MCP342x::maxResolution)
			adcResolutionList[i] = res;
    
		uint8_t gain = 0;
#if defined (FEATURE_FLC100)
		if (i < EEPROM_ADC_GAIN_LIST_SIZE)
			gain = eeprom_read_byte((uint8_t*)(EEPROM_ADC_GAIN_LIST + i));
#elif defined (FEATURE_RIOMETER)
		if (i < EEPROM_RIO_RIOMETER_ADC_GAIN_LIST_SIZE)
			gain = eeprom_read_byte((uint8_t*)(EEPROM_RIO_RIOMETER_ADC_GAIN_LIST + i));
#else
#error Bad logic
#endif
		if (gain && gain <= MCP342x::maxGain)
			adcGainList[i] = gain;
    
	}

	uint8_t numSamples = eeprom_read_byte((uint8_t*)EEPROM_NUM_SAMPLES);
	if (numSamples == 0 || numSamples > SensorShield_t::maxSamples)
		numSamples = 1;
	uint8_t aggregate = eeprom_read_byte((uint8_t*)EEPROM_AGGREGATE);
	if (aggregate == 255)
		aggregate = EEPROM_AGGREGATE_USE_MEDIAN; // Not set in EEPROM
	allSamples = eeprom_read_byte((uint8_t*)EEPROM_ALL_SAMPLES);

	__FlashStringHelper* sensorFlashStr = (__FlashStringHelper*)PSTR(SENSOR_FLASH_STRING);
	if (sensorShieldPresent) {
		console.print(initialisingStr);
		console.println(sensorFlashStr);

		sensorShield.initialise(FLC100_POWER, adcAddressList, adcChannelList,
								adcResolutionList, adcGainList);
		sensorShield.setNumSamples(numSamples,
								   aggregate & EEPROM_AGGREGATE_USE_MEDIAN,
								   aggregate & EEPROM_AGGREGATE_TRIM_SAMPLES);

		for (int i = 0; i < SensorShield_t::maxNumAdcs; ++i)
			console << F("ADC[") << i << F("]: Ox") << _HEX(adcAddressList[i])
					<< F(" ch. ") << (adcChannelList[i])
					<< (sensorShield.getAdcPresent(i) ? F(" present\n") : F(" missing\n"));

		console << F("numSamples: ") << numSamples
				<< F("\naggregate: ");
		if (aggregate & EEPROM_AGGREGATE_TRIM_SAMPLES)
			console << F("trimmed ");
		console << (aggregate & EEPROM_AGGREGATE_USE_MEDIAN ? F("median\n")
					: F("mean\n"));

		console.flush();
	}

	console.print(sensorFlashStr);
	if (!sensorShieldPresent)
		console.print(notStr);
	console.println(presentStr);
	if (sensorShieldPresent) {
		console.print(sensorFlashStr);
		console.print(powerUpDelayStr);
		console.println(SensorShield_t::powerUpDelay_ms);
	}
#endif

#ifdef FEATURE_MLX90614
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
#endif

#ifdef FEATURE_HIH61XX
	__FlashStringHelper* hih61xxStr = (__FlashStringHelper*)PSTR("HIH61xx");
	if (hih61xxPresent) {
		console.print(initialisingStr);
		console.println(hih61xxStr);
		hih61xxPresent = hih61xx.initialise();
	}
	console.print(hih61xxStr);
	if (!hih61xxPresent)
		console.print(notStr);
	console.println(presentStr);
#endif

#ifdef FEATURE_AS3935
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
		attachInterrupt(2, as3935InterruptHandler, RISING);
	}
	console.print(as3935Str);
	if (!as3935Present)
		console.print(notStr);
	console.println(presentStr);
#endif


	// Identify communications method to be used.
	radioType = eeprom_read_byte((const uint8_t*)EEPROM_COMMS_TYPE);
#ifdef COMMS_XRF
	if (radioType == 0xFF) {
		// Not set so default to XRF as used in original version
		radioType = EEPROM_COMMS_TYPE_XRF;
	}
#endif


#ifdef FEATURE_GNSS
	gnssSerial.begin(115200);
	gnss_clock.begin(gnssBuffer, sizeof(gnssBuffer), gnssPpsPin);

	// TODO: reset GNSS  module

	// Compatibility mode off
	MicroNMEA::sendSentence(gnssSerial, "$PNVGNME,2,7,1");

	// Clear the list of messages which are sent.
	MicroNMEA::sendSentence(gnssSerial, "$PORZB");

	// Send RMC and GGA messages.
	MicroNMEA::sendSentence(gnssSerial, "$PORZB,RMC,1,GGA,1");

#endif

#ifdef FEATURE_DATA_QUALITY
	if (dataQualityInputPin != 255) {
		pinMode(dataQualityInputPin, INPUT_PULLUP);
		attachInterrupt(digitalPinToInterrupt(dataQualityInputPin),
						dataQualityISR, CHANGE);
	}
#endif

#ifdef FEATURE_HOUSEKEEPING
	uint8_t VinDivider = eeprom_read_byte((uint8_t*)EEPROM_VIN_DIVIDER);
	if (VinDivider == 0xFF)
		VinDivider = 1; // For compatibility with older firmware
	houseKeeping.initialise(2, 7, A6, VinDivider,
							(radioType != EEPROM_COMMS_TYPE_XRF &&
							 radioType != EEPROM_COMMS_TYPE_RFM12B));
#endif

	// Autoprobe to find RTC. Device type and address can be set in
	// the EEPROM to void clashes with other devices. Even if the
	// device details are configured in the EEPROM autoprobe() as
	// check that it is working correctly.
	console << F("Autoprobing to find ");

	RTCx::device_t rtcxDevice = (RTCx::device_t)eeprom_read_byte((uint8_t*)EEPROM_RTCX_DEVICE_TYPE);
	uint8_t rtcxAddress = eeprom_read_byte((uint8_t*)EEPROM_RTCX_DEVICE_ADDRESS);
	uint8_t foundRtc = false;
	if (rtcxDevice <= RTCX_NUM_SUPPORTED_DEVICES && rtcxAddress > 7 && rtcxAddress < 120) {
		console << RTCx::getDeviceName(rtcxDevice) << endl;
		foundRtc = rtc.autoprobe(&rtcxDevice, &rtcxAddress, 120);
	}
	else {
		console.println("RTC");
		foundRtc = rtc.autoprobe();
	}

	if (foundRtc)
		console << F("Found ") << rtc.getDeviceName() << F(" at address 0x") << _HEX(rtc.getAddress()) << endl;
	else
		console << F("No RTC found\n");
	console.flush();

	// Initialise the RTC to get some sensible settings, such as
	// ensuring the battery backup is enabled. This also zeros the
	// calibration.
	rtc.init();

	// Set the calibration register
	uint8_t rtcCal = eeprom_read_byte((uint8_t*)EEPROM_MCP7941X_CAL);
	if (rtcCal == 0xFF)
		rtcCal = 0; // EEPROM location probably not programmed.
	if (rtc.setCalibration(rtcCal == 0XFF ? 0 : rtcCal)) {
		// Calibration is supported so display the value set.
		console << F("RTC calibration: ") << _DEC(rtcCal) << endl;
		console.flush();
	}

	pinMode(15, INPUT);

	// Warn, if it stops at this point it means the jumper isn't fitted.
	// TODO: test if jumper for RTC output is fitted.
	console << F("Configuring system clock\n");
	console.flush();


#if defined(COMMS_XRF) && (F_CPU) == 8000000L
	// Assume battery-powered operation. Efficient sleep cycles are
	// required. Have the counter RTC ticking at 16Hz, giving maximum
	// sleep time of 16s.

	// Ensure square-wave output is enabled.
	rtc.setSQW(RTCx::freq4096Hz);

	// Input: 4096Hz, prescaler is divide by 256, clock tick is 16Hz
	cRTC.begin(16, true, (_BV(CS22) | _BV(CS21)));
	counter2Frequency = 16;

#else
	// XRF communications are not compiled in, or the clock speed is
	// wrong for battery operation. Assume efficient sleeping is not
	// important so optimize the counter RTC for high resolution
	// measurements instead.

	// Ensure square-wave output is enabled. Set the highest input
	// frequency possible so that register changes which rely upon
	// transtions of TOSC1 happen fastest.
	rtc.setSQW(RTCx::freq32768Hz);

	// Input: 32768Hz, prescaler is divide by 1, clock tick is 32768Hz
	cRTC.begin(32768, true, _BV(CS20));
	counter2Frequency = 32768;

#endif /* Matches #if defined(COMMS_XRF) && (F_CPU) == 8000000L */

	console << F("System clock: ") << counter2Frequency << "Hz\n";


	// Set counter RTC time from the hardware RTC
	struct RTCx::tm tm;
	CounterRTC::Time t;
	if (rtc.readClock(&tm)) {
		//CounterRTC::Time t;
		t.setSeconds(RTCx::mktime(tm));
		cRTC.setTime(t);
		lastAcknowledgement = t;
		console << F("System clock set from hardware RTC\n");
	}
	else
		console << F("Could not get time from hardware RTC\n");
	console.flush();

	// Configure radio module or Ethernet adaptor.
#if defined(COMMS_W5100) || defined(COMMS_W5500)
	if (radioType == EEPROM_COMMS_TYPE_W5100_UDP) {
		begin_WIZnet_UDP();

		disableJTAG();
		//ledPin = 17; // JTAG TDO
		commsHandler.setCommsInterface(&wiz_udp);
		useLed = true;

		// Enable faster sampling rates for Ethernet communication
		// minSamplingInterval.setSeconds(1);
		minSamplingInterval = CounterRTC::Time(0, CounterRTC::fractionsPerSecond / 16);
	}
#endif

#ifdef COMMS_XRF
	if (radioType == EEPROM_COMMS_TYPE_XRF) {
		console.println("Initialising XRF");
		xrfSerial.begin(9600);
		commsBlockSize = 12; // By default XRF sends 12 byte packets, set to reduce TX latency.
		xrf.begin(xrfSleepPin, xrfOnPin, xrfResetPin);
		commsHandler.setCommsInterface(&xrf);
	}
#endif


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

	console << F("Sampling interval (s): ") << samplingInterval.getSeconds()
			<< sep << samplingInterval.getFraction() << endl;
	console.flush();


	pinMode(ledPin, OUTPUT);
	digitalWrite(ledPin, LOW);

	commsHandler.setKey(hmacKey, sizeof(hmacKey));

#ifdef FEATURE_GNSS
	gnss_clock.set1ppsCallback(gnssPpsCallback);
#endif

	console.println(F("Configuration complete"));
	console.flush();

    commandHandler.begin(commandBuffer, sizeof(commandBuffer), commands, numCommands, unknownCommand, commandTooLong);

    // Attempt to send a message with useful information about the system. If the logging daemon is not running then
    // message stack could become full and none of these messages will be delivered. The messages are put into the
    // queue but are not sent until commsHandler.process() is called inside loop(). The message most recently added
    // to the queue transmitted first so add them in the reverse order to the desired reception order.
    const uint16_t bufferLength = 512;
    uint8_t buffer[bufferLength];
    cRTC.getTime(t);

    AWPacket packet;
#ifdef FEATURE_RIOMETER
    // Send 4th page of EEPROM (riometer configuration)
    packet.setKey(hmacKey, sizeof(hmacKey));
    packet.setTimestamp(t.getSeconds(), t.getFraction());
    packet.putHeader(buffer, sizeof(buffer));
    packet.putEepromContents(buffer, sizeof(buffer), 0x300, 256);
    packet.putSignature(buffer, sizeof(buffer), commsBlockSize);
    commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));

    // Send 3rd page of EEPROM (riometer housekeeping configuration)
    packet.setKey(hmacKey, sizeof(hmacKey));
    packet.setTimestamp(t.getSeconds(), t.getFraction());
    packet.putHeader(buffer, sizeof(buffer));
    packet.putEepromContents(buffer, sizeof(buffer), 0x200, 256);
    packet.putSignature(buffer, sizeof(buffer), commsBlockSize);
    commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));

    // Send 2nd page of EEPROM (generic ADC logger configuration)
    packet.setKey(hmacKey, sizeof(hmacKey));
    packet.setTimestamp(t.getSeconds(), t.getFraction());
    packet.putHeader(buffer, sizeof(buffer));
    packet.putEepromContents(buffer, sizeof(buffer), 0x100, 256);
    packet.putSignature(buffer, sizeof(buffer), commsBlockSize);
    commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
#endif

    // Send first page of 256 bytes of EEPROM. putEepromContents() automatically redacts the key.
    packet.setKey(hmacKey, sizeof(hmacKey));
    packet.setTimestamp(t.getSeconds(), t.getFraction());
    packet.putHeader(buffer, sizeof(buffer));
    packet.putEepromContents(buffer, sizeof(buffer), 0, 256);
    packet.putSignature(buffer, sizeof(buffer), commsBlockSize);
    commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));

    // Send hardware and firmware details
    char actualMcu[40];
    packet.setKey(hmacKey, sizeof(hmacKey));
    packet.setTimestamp(t.getSeconds(), t.getFraction());
    packet.putHeader(buffer, sizeof(buffer));
    packet.putDataUint8(buffer, sizeof(buffer), AWPacket::tagRebootFlags, mcusrCopy);
    packet.putString(buffer, sizeof(buffer), AWPacket::tagCurrentFirmware, firmwareVersion);
    packet.putLogMessage_P(buffer, sizeof(buffer), F("Target MCU: " EXPAND_STR(CPU_NAME)));
    strlcpy_P(actualMcu, PSTR("Actual MCU: "), sizeof(actualMcu));
    strlcat_P(actualMcu, (const char*)deviceName, sizeof(actualMcu)); // Device name is stored in flash
    packet.putLogMessage(buffer, sizeof(buffer), actualMcu);
    packet.putLogMessage_P(buffer, sizeof(buffer), PSTR("Frequency: " F_CPU_STR));
    packet.putLogMessage_P(buffer, sizeof(buffer), comms_P);
    packet.putLogMessage_P(buffer, sizeof(buffer), features_P);
    packet.putSignature(buffer, sizeof(buffer), commsBlockSize);
    commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));

    // Set the alarm to start taking samples
    console << F("Setting sample timers") << endl;
    setAlarm();

    console << F("Setup done") << endl;
}


bool resultsProcessed = true;
CounterRTC::Time sampleStartTime;
void loop(void)
{
    bool crtcTriggeredCopy = crtcTriggered; // Read actual volatile value only one in loop().
	bool startSampling = false;
	wdt_reset();

	// Decide when to start sampling. Use the GNSS PPS input if
	// possible, otherwise use the alarm feature of the CounterRTC
	// clock. Read the flags which are set by ISRs only once (they might change during loop()!)
#ifdef FEATURE_GNSS
    bool ppsTriggeredCopy;
	RTCx::time_t gnssNow;
	bool gnssNowOk = false;

    // Only attempt to clear if we have already seen it is set (to avoid race conditions).
    ppsTriggeredCopy = ppsTriggered;
    if (ppsTriggeredCopy) {
        ppsTriggered = false;
		gnssNowOk = gnss_clock.readClock(gnssNow);
    }

	if (useGnss && samplingInterval.getFraction() == 0) {
		if (gnssNowOk && (gnssNow % samplingInterval.getSeconds() == 0)) {
			startSampling = true;
			sampleStartTime = CounterRTC::Time(gnssNow, 0);
        }
	}
	else {
		if (crtcTriggeredCopy) {
			startSampling = true;
			cRTC.getTime(sampleStartTime);
        }
	}

#else
	if (crtcTriggeredCopy) {
		startSampling = true;
		cRTC.getTime(sampleStartTime);
    }
#endif

#ifdef FEATURE_DATA_QUALITY
	if (dataQualityChanged)
		startSampling = true;
#endif

#ifdef FEATURE_GNSS
	if (ppsTriggeredCopy) {
		// Set CounterRTC clock from GNSS
		if (gnssNowOk)  {
			CounterRTC::Time ourTime;
			cRTC.getTime(ourTime);
			CounterRTC::Time gnssTime(gnssNow, 0);
			CounterRTC::Time timeError = ourTime - gnssTime;
			CounterRTC::Time absTimeError = abs_(timeError);

			// Update clock
			cRTC.setTime(gnssTime);
			if (absTimeError > samplingInterval)
				// Update alarm since it might be a long time in the future
				cRTC.setAlarm(0, gnssTime + samplingInterval,
							  crtcCallback);

			if (verbosity > 1) {
				console << F("Time error (our-GNSS): ")
						<< timeError.getSeconds() << sep
						<< timeError.getFraction() << endl;
			}
		}
	}
#endif



	if (startSampling) {
#ifdef FEATURE_BUSY_TIME_PIN
        digitalWrite(FEATURE_BUSY_TIME_PIN, HIGH);
#endif

#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
		if (sensorShieldPresent && !sensorShield.isSampling())
			sensorShield.start();
#endif
#ifdef FEATURE_MLX90614
		if (!mlx90614.isSampling())
			mlx90614.start();
#endif

#ifdef FEATURE_HIH61XX
		if (!hih61xx.isSampling())
			hih61xx.start();
#endif

		// AS3935 does not need starting here. It is kept powered.

#ifdef FEATURE_HOUSEKEEPING
		if (!houseKeeping.isSampling())
			houseKeeping.start();
#endif

		startSampling = false;
		resultsProcessed = false;

#ifdef FEATURE_GNSS
		// Save the GNSS fix data
		gnssFixValid = gnss_clock.readClock(gnssFixTime, gnssLocation[0],
											gnssLocation[1], gnssLocation[2],
											altitudeValid, navSystem,
											numSat, hdop);
		// readClock() returns current time at second boundary, adjust to
		// get true time of position fix
		--gnssFixTime;
#endif

#ifdef FEATURE_DATA_QUALITY
		dataQualityWarning = false;
#endif

		if (verbosity)
			console << F("--\nSampling started\n");
	}

	if (crtcTriggeredCopy) {
		// Set crtcTriggered=false BEFORE setting the alarm. If the
		// computed alarm time is in the past then the callback will be
		// run immediately and will ensure crtcTriggered is made true. If
		// the alarm is set before setting crtcTriggered=false then an
		// alarm could be lost and sampling would stop.
		crtcTriggered = false;
		setAlarm();
	}

#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
	if (sensorShieldPresent)
		sensorShield.process();
#endif
#ifdef FEATURE_MLX90614
	if (mlx90614Present)
		mlx90614.process();
#endif
#ifdef FEATURE_HIH61XX
	if (hih61xxPresent)
		hih61xx.process();
#endif
#ifdef FEATURE_AS3935
	if (as3935Present)
		as3935.process();
#endif
#ifdef FEATURE_HOUSEKEEPING
	houseKeeping.process();
#endif

#ifdef FEATURE_GNSS
	while (gnssSerial.available()) {
		char c = gnssSerial.read();
		if (verbosity == 12)
			console.print(c);
		gnss_clock.process(c);
	}
#endif

#ifdef FEATURE_DATA_QUALITY
	if (dataQualityInputPin != 255) {
		dataQualityChanged = false;
		bool i = digitalRead(dataQualityInputPin);
		if (dataQualityInputActiveLow)
			i = !i;

		dataQualityWarning |= i;
	}
#endif


	if (commsHandler.process(responseBuffer, responseBufferLen))
		processResponse(responseBuffer, responseBufferLen);

	commandHandler.process(console);

	// console << F("I2C state: ") << (sensorShield.getI2CState()) << endl;
	if (1
#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
		&& (sensorShieldPresent == false || sensorShield.isFinished())
#endif
#ifdef FEATURE_MLX90614
		&& (mlx90614Present == false || mlx90614.isFinished())
#endif
#ifdef FEATURE_HIH61XX
		&& (hih61xxPresent == false || hih61xx.isFinished())
#endif
#ifdef FEATURE_HOUSEKEEPING
		&& houseKeeping.isFinished()
#endif
		) {
		// Process SD card when normal sampling is not running; SD card
		// access can be slow and block.

		if (resultsProcessed == false) {
			resultsProcessed = true;
			// for (uint8_t i = 0; i < FLC100::maxNumAdcs; ++i)
			// 	console << '\t' << (sensorShield.getData()[i]);
			// console << endl;

			if (verbosity)
				console << F("Timestamp: ") << sampleStartTime.getSeconds()
						<< sep << sampleStartTime.getFraction() << endl;
#ifdef FEATURE_HOUSEKEEPING
                console << F("System temp.: ") << houseKeeping.getSystemTemperature();
#endif
#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
			if (verbosity && sensorShieldPresent)
				console << F("\n" SENSOR_FLASH_STRING " temp.: ") << sensorShield.getSensorTemperature() << endl;
#endif

#ifdef FEATURE_HOUSEKEEPING
			if (verbosity && houseKeeping.getVinDivider())
				console << F("Supply voltage: ") << houseKeeping.getVin() << endl;
#endif

#ifdef FEATURE_MLX90614
			if (mlx90614Present) {
				console << F("MLX temp: ") << mlx90614.getAmbient()
						<< F("\nObject 1: ") << mlx90614.getObject1();
				if (mlx90614.isDualSensor())
					console << F("\nObject 2: ") << mlx90614.getObject2();
				console.println();
			}
#endif

#ifdef FEATURE_HIH61XX
			if (verbosity && hih61xxPresent)
				console << F("Humidity: ") << hih61xx.getRelHumidity()
						<< F("\nAmbient: ") << hih61xx.getAmbientTemp() << endl;
#endif

#ifdef FEATURE_FLC100
			if (sensorShieldPresent) {
			    if (verbosity > 0) {
			        // Print data values
                    for (uint8_t i = 0; i < SensorShield_t::maxNumAdcs; ++i)
                        if (sensorShield.getAdcPresent(i))
                            console << F(SENSOR_FLASH_STRING " data[") << i << F("]: ")
                                    << (sensorShield.getData()[i]) << endl;
                }

                if (verbosity == 11) {
                    // Print the raw data values used to obtain the average values
                    for (uint8_t i = 0; i < SensorShield_t::maxNumAdcs; ++i) {
                        if (sensorShield.getAdcPresent(i)) {
                            console << char('X' + i) << ':';
                            for (uint8_t j = 0; j < SensorShield_t::maxSamples; ++j)
                                console << ' ' << sensorShield.getDataSamples(i, j);
                            console << '\n';
                        }
                    }
                }
			}
#endif

#ifdef FEATURE_RIOMETER
            // Too many samples to print all during normal output
			if (sensorShieldPresent && verbosity == 11) {
				for (uint8_t i = 0; i < sensorShield.getNumBeams(); ++i)
                    console << F(SENSOR_FLASH_STRING " data[") << i << F("]: ")
                            << (sensorShield.getData()[i]) << endl;
            }
#endif

#ifdef FEATURE_GNSS
			if (verbosity) {
				console << F("GNSS valid: ") << (gnssFixValid ? 'Y' : 'N') << endl;
				if (gnssFixValid) {
					console << F("Fix time: ") << gnssFixTime
							<< F("\nPosition: ") << gnssLocation[0] << sep
							<< gnssLocation[1];
					if (altitudeValid)
						console << sep << gnssLocation[2];
					console << F("\nStatus: ") << navSystem << sep << int(numSat)
							<< sep << int(hdop) << endl;
				}
			}
#endif

			// Buffer for storing the binary AW packet. Will also be used
			// when writing to SD card.
			const uint16_t bufferLength = commsMessageBufferLen;
			uint8_t buffer[bufferLength];

#ifdef FEATURE_HOUSEKEEPING
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
#endif


#ifdef FEATURE_SD_CARD
            // Check that the buffer can store an entire SD sector (512 bytes)
            static_assert(bufferLength >= SD_SECTOR_SIZE, "Buffer must be larger than SD sector size");
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
						console << F("Wrote to ") << bytesRead
								<< F(" to ") << sdFilename << endl;
					}
				}

				if (strcmp(sdFilename, newFilename) != 0) {
					if (sdFile) {
						console << F("Closing ") << sdFilename << endl;
						sdFile.close();
					}
					strncpy(sdFilename, newFilename, sizeof(sdFilename));
					// Make directory
					char *ptr = strrchr(newFilename, '/');
					if (ptr) {
						*ptr = '\0'; // Remove filename part
						if (SD.mkdir(newFilename))
							console << F("Created directory ") << newFilename << endl;
					}
					if ((sdFile = SD.open(sdFilename, FILE_WRITE)) == true)
						console << F("Opened ") << sdFilename << endl;
					else
						console << F("Failed to open ") << sdFilename << endl;
				}
			}
#endif


			AWPacket packet;
			packet.setKey(hmacKey, sizeof(hmacKey));
			packet.setFlagBit(AWPacket::flagsSampleTimingErrorBit, callbackWasLate);
#ifdef FEATURE_DATA_QUALITY
			packet.setFlagBit(AWPacket::flagsDataQualityWarningBit,
							  dataQualityWarning);
#endif
			packet.setTimestamp(sampleStartTime.getSeconds(),
								sampleStartTime.getFraction());

			packet.putHeader(buffer, sizeof(buffer));
#ifdef PRINT_BINARY_BUFFER
			// printBinaryBuffer(console, buffer, 20);
			// console << endl;
#endif

			if (verbosity)
				console << F("Header length: ") << AWPacket::getPacketLength(buffer)
						<< endl;

#if defined (FEATURE_FLC100) || defined (FEATURE_RIOMETER)
			if (sensorShieldPresent) {
				uint8_t numSamples;
				bool median;
				bool trimmed;
				sensorShield.getNumSamples(numSamples, median, trimmed);

#if defined (FEATURE_FLC100)
				for (uint8_t i = 0; i < SensorShield_t::maxNumAdcs; ++i)
					if (sensorShield.getAdcPresent(i)) {
						packet.putMagData(buffer, sizeof(buffer),
										  AWPacket::tagMagDataX + i,
										  sensorShield.getResGain(i),
										  sensorShield.getData()[i]);
						// Put all samples only if requested, and only when no
						// messages are waiting for retransmission.
						if (allSamples && commsHandler.isBufferEmpty())
							packet.putDataArray(buffer, sizeof(buffer),
												AWPacket::tagMagDataAllX + i, 4,
												numSamples, sensorShield.getDataSamples(i));
					}
#elif defined (FEATURE_RIOMETER)
                packet.putGenData(buffer, sizeof(buffer), 8, sensorShield.getNumBeams(), sensorShield.getData());
                for (uint8_t rn = 0; rn < sensorShield.maxRows; ++rn) {
                    int32_t hkData[sensorShield.maxNumAdcs];
                    uint8_t numHkSamples = sensorShield.copyHousekeepingData(rn, hkData, sensorShield.maxNumAdcs);
                    if (numHkSamples)
                        packet.putGenData(buffer, sizeof(buffer), rn, numHkSamples, hkData);
                }
#else
#error Bad logic
#endif

				packet.putDataInt16(buffer, sizeof(buffer),
									AWPacket::tagSensorTemperature,
									sensorShield.getSensorTemperature());
				packet.putDataUint16(buffer, sizeof(buffer),
									 AWPacket::tagNumSamples,
									 (uint16_t(numSamples) << 8) |
									 (uint16_t(trimmed) << 1) |
									 median);

			}
#endif

#ifdef FEATURE_HOUSEKEEPING
			packet.putDataInt16(buffer, sizeof(buffer),
								AWPacket::tagMCUTemperature,
								houseKeeping.getSystemTemperature());
			if (houseKeeping.getVinDivider())
				packet.putDataUint16(buffer, sizeof(buffer),
									 AWPacket::tagSupplyVoltage,
									 houseKeeping.getVin());
			// Upper 3 nibbles is seconds, lowest nibble is 16ths of second
			packet.putDataUint16(buffer, sizeof(buffer),
								 AWPacket::tagSamplingInterval,
								 (uint16_t(samplingInterval.getSeconds() << 4) |
								  samplingInterval.getFraction() >>
								  (CounterRTC::fractionsPerSecondLog2 - 4)));
#endif

#ifdef FEATURE_MLX90614
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
#endif

#ifdef FEATURE_HIH61XX
			if (hih61xxPresent) {
				packet.putDataInt16(buffer, sizeof(buffer),
									AWPacket::tagAmbientTemp,
									hih61xx.getAmbientTemp());
				packet.putDataUint16(buffer, sizeof(buffer),
									 AWPacket::tagRelHumidity,
									 hih61xx.getRelHumidity());
			}
#endif
			if (firstMessage) {
				// Cancelled when first response is received. This information might seem
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
				console << F("EEPROM contents length: ") << eepromContentsLength
						<< endl;
				packet.putEepromContents(buffer, sizeof(buffer),
										 eepromContentsAddress, eepromContentsLength);
			}
#ifdef FEATURE_GNSS
			packet.putGnssStatus(buffer, sizeof(buffer),
								 gnssFixTime, gnssFixValid, navSystem,
								 numSat, hdop);
			if (gnssFixValid && commsHandler.isBufferEmpty())
				packet.putDataArray(buffer, sizeof(buffer),
									AWPacket::tagGnssLocation, 4,
									(altitudeValid ? 3 : 2), gnssLocation);

#endif

			// Add the signature
			packet.putSignature(buffer, sizeof(buffer), commsBlockSize);

#ifdef FEATURE_SD_CARD
			// Log to a file (if desired)
			if (useSd)
				sdCircularBuffer.write(buffer, AWPacket::getPacketLength(buffer));
#endif

			// Send the message
			commsHandler.addMessage(buffer, AWPacket::getPacketLength(buffer));
			++messageCount;

			// Message queued, turn on LED
			if (useLed) {
				if (maxMessagesLed && messageCount >= maxMessagesLed)
					useLed = false;
				digitalWrite(ledPin, useLed);
			}

			// Set RTC only if necessary. It will slightly upset the timing
			// as it stops the hardware clock briefly.
			struct RTCx::tm tm;
			rtc.readClock(tm);
			RTCx::time_t hwcTime = RTCx::mktime(tm);
			CounterRTC::Time now;
			cRTC.getTime(now);
			if (labs(hwcTime - now.getSeconds()) > maxHardwareClockTimeError) {
				RTCx::time_t t = now.getSeconds();
				RTCx::gmtime_r(&t, &tm);
				rtc.setClock(tm);
				console.println(F("Set HW clock"));
			}

			// Check how long since last acknowledgement was received
			int32_t ackAge = now.getSeconds() - lastAcknowledgement.getSeconds();
			if (ackAge > maxTimeNoAck) {
				console << F("Gone ") << maxTimeNoAck;
				console.println(F("s without mesg ack, rebooting\n"));
				console.flush();
				reboot();
			}
			else if (ackAge < 0)
				// Guard against large time jumps
				lastAcknowledgement = now;

#if defined(COMMS_W5100) || defined(COMMS_W5500)
			maintainDhcpLease();
#endif

#ifdef FEATURE_MEM_USAGE
			if (verbosity)
				console << F("Free mem: ") << freeMemory() << endl;
#endif

#ifdef FEATURE_BUSY_TIME_PIN
            digitalWrite(FEATURE_BUSY_TIME_PIN, LOW);
#endif

			static uint8_t verbosityCharState = 0;
			if (verbosity == 0) {
				verbosityCharState = ((verbosityCharState + 1) % 8);
				console.println(char('!' + verbosityCharState));
			}

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

			// Increment the sequence number since the timestamp will not
			// change until the next sampling action.
			AWPacket::incrementDefaultSequenceId();

			// Buffer for assembling the binary AW packet
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
				if (maxMessagesLed && messageCount >= maxMessagesLed)
					useLed = false;
				digitalWrite(ledPin, useLed);
			}

		}

		// Test if can go to sleep
		if (startSampling == false &&
			commsHandler.isFinished() &&
			commsHandler.getCommsInterface()->powerOff()) {

			if (enableSleep && samplingInterval >= minSleepInterval) {
				console << F("SLEEP!\n");
				console.flush();
				doSleep(SLEEP_MODE_PWR_SAVE);
				console << F("AWAKE!\n");
				console.flush();
			}
		}
	}

}


Stream& printEepromContents(Stream &s, uint16_t address, uint16_t size)
{
	s << F("EEPROM values:\n");
	while (address <= E2END && size--) {
		s << F("0x") << _HEX(address) << F(": 0x") << _HEX(eeprom_read_byte((uint8_t*)address)) << endl;
		//s << F("0x") << _HEX(address) << F(": 0x") << "[some value]" << endl;
		++address;
	}
	return s;
}


// Commands
void cmdEepromRead(const char *s)
{
    const char *ep = s;
    char *ep2;
    long address = strtol(ep, &ep2, 0);
    long size;

    if (address >= 0 && address <= E2END && ep2 != ep && *ep2 == ',') {
		ep = ++ep2;
		size = strtol(ep, &ep2, 0);
		if (size > 0 && (address + size) <= E2END && ep2 != ep && *ep2 == '\0') {
			printEepromContents(console, (uint16_t)address, (uint16_t)size);
			return;
		}
	}

	console.println(F("ERROR: bad values for eepromRead"));
}


void cmdEepromWrite(const char *s)
{
    const char *ep = s;
    char *ep2;
    long address = strtol(ep, &ep2, 0);
    long size = 0;
    if (address >= 0 && address <= E2END && ep2 != ep && *ep2 == ',') {
		ep = ++ep2;
		if (*ep == '\'') {
			// A string, take the value of each byte
			++ep;
			while (*ep != '\0') {
			    eeprom_update_byte((uint8_t*)address, *ep++);
				++address;
				++size;
			}
		}
        else {
            // Assume numeric values for each byte
            while(address >= 0 && address <= E2END) {
                long val = strtol(ep, &ep2, 0);
                if (val >= 0 && val <= 255 && ep2 != ep && (*ep2 == ',' || *ep2 == '\0')) {
                    eeprom_update_byte((uint8_t*)address, val);
                    ++address;
                    ++size;
                    if (*ep2 == '\0')
                        break;
                    ep = ++ep2;
                }
                else
                    break;
            }
		}
        printEepromContents(console, (uint16_t)(address-size), (uint16_t)size);

		return;
	}

	console.println(F("ERROR: bad values for eepromWrite"));
}


void cmdVerbosity(const char *s)
{
    if (*s++ == '=') {
        char *ep;
        long v = strtol(s, &ep, 0);
        if (v >= 0 && v <= 255 && ep != s && *ep == '\0')
            verbosity = v;
    }
    console << F("verbosity: ") << verbosity << endl;
}


void cmdReboot(const char *s)
{
    if (*s == '\0') {
		console << F("Reboot command received from console\n");
		console.flush();
		reboot();
    }
    else {
        unknownCommand(commandBuffer);
    }
}

void reboot(void) {
	console << F("Rebooting ...\n");
	console.flush();
	wdt_enable(WDTO_15MS);
	while (1)
		;
}

void cmdSamplingInterval(const char *s)
{
    if (*s++ == '=') {
        char *ep;
        long si = strtol(s, &ep, 0);
        if (si > 0 && ep != s && *ep == '\0') {
            CounterRTC::Time tmp =
                CounterRTC::Time((si & 0xFFF0) >> 4,
                                 (si & 0x000F) <<
                                 (CounterRTC::fractionsPerSecondLog2 - 4));
            if (tmp >= minSamplingInterval && tmp <= maxSamplingInterval)
                samplingInterval = tmp;

        }
    }
    console << F("samplingInterval_16th_s: ")
            << ((samplingInterval.getSeconds() * 16) +
                (samplingInterval.getFraction() >> (CounterRTC::fractionsPerSecondLog2 - 4))) << endl;
}


#if USE_SD_CARD
void cmdUseSd(const char *s)
{
    if (*s++ == '=') {
        char *ep;
        long n = strtol(s, &ep, 0);
        if (n >= 0 && n <= 1 && ep != s && *ep == '\0') {
            // Need to update both EEPROM and RAM values since the RAM
            // value might differ (eg card couldn't be initialized).
            useSd = n;
            eeprom_update_byte((uint8_t*)EEPROM_USE_SD, n);
            // TODO: call SD.begin(sdSelect) if necessary
        }
    }
    console << F("useSd: ")
            <<  useSd << F(" (current), ")
            << eeprom_read_byte((const uint8_t*)EEPROM_USE_SD)
            << F(" (EEPROM)\n");
}
#endif


void unknownCommand(const char *s)
{
    console << F("Unknown command: ") << s << endl;
}


void commandTooLong(int)
{
    console << F("Previous command was too long for buffer\n");
}
