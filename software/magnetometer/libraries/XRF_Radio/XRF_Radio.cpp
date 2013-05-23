#include <avr/eeprom.h>

#include <Streaming.h>
#include <XRF_Radio.h>
#include <AwEeprom.h>

extern Stream& console;

XRF_Radio::XRF_Radio(Stream &s) :
  stream(s),
  sleepPin(255),
  onPin(255),
  resetPin(255),
  poweringUp(false),
  resetting(false)
{
  ;
}

int XRF_Radio::available(void)
{
  return stream.available();
}

int XRF_Radio::peek(void)
{
  return stream.peek();
}

int XRF_Radio::read(void)
{
  return stream.read();
}

void XRF_Radio::flush(void)
{
  return stream.flush();
}

size_t XRF_Radio::write(uint8_t c)
{
  return stream.write(c);
}

bool XRF_Radio::powerOn(void)
{
  if (poweringUp && digitalRead(onPin))
    return true;

  if (poweringUp == false) {
    digitalWrite(sleepPin, LOW);
    // powerUpTimer.start(powerUpDelay_ms, AsyncDelay::MILLIS);
    poweringUp = true;
  }
  return false;

}

bool XRF_Radio::powerOff(void)
{
  digitalWrite(sleepPin, HIGH);
  poweringUp = false;
  return true;
}

bool XRF_Radio::reset(void)
{
  if (resetPin == 255)
    return true; // Reset pin not set, report reset done
  
  if (resetting && resetTimer.isExpired()) {
    // Timer expired, make reset pin inactive and check that XRF
    // indicates it is ready.
    digitalWrite(resetPin, HIGH);
    if (digitalRead(onPin) == HIGH) {
      resetting = false;
      return true;
    }
  }
  
  if (resetting == false) {
    // Begin reset cycle. Make reset pin active for a short while.
    digitalWrite(resetPin, LOW);
    resetTimer.start(resetDelay_us, AsyncDelay::MICROS);
    resetting = true;
    poweringUp = false;
  }
  return false;
}


bool XRF_Radio::begin(uint8_t xrfSleepPin, uint8_t xrfOnPin, uint8_t xrfResetPin)
{
  AsyncDelay timeout;
  bool found = true;
  sleepPin = xrfSleepPin;
  onPin = xrfOnPin;
  resetPin = xrfResetPin;
  
  if (sleepPin != 255) {
    pinMode(sleepPin, OUTPUT);
    //digitalWrite(sleepPin, HIGH); // active low, in sleep mode 2
    digitalWrite(sleepPin, LOW); // low = on, in sleep mode 2
  }

  if (resetPin != 255) {
    pinMode(resetPin, OUTPUT);
    digitalWrite(resetPin, HIGH); // active low

    timeout.start(3000, AsyncDelay::MILLIS);
    while (1) {
      if (reset())
	break;
      if (timeout.isExpired()) {
	found = false;
	console.println("Timeout waiting for XRF to reset");
	break;
      }
    }
    // do {
    //   ;
    // } while (reset() != true);
  }

  if (onPin != 255) { 
    pinMode(onPin, INPUT);
    timeout.start(3000, AsyncDelay::MILLIS);
    while (1) {
      if (powerOn() == true)
	break;
      if (timeout.isExpired()) {
	found = false;
	console.println("Timeout waiting for XRF to power on\n");
	break;
      }
    }
    // do {
    //   ;
    // } while (powerOn() != true);
  }
  
  while (stream.available())
    stream.read();
  
  delay(1050);
  stream.print("+++");
  //stream.flush();
  delay(1050);
  stream << "ATRE\r";
  stream << "ATSM 2\r"; // Sleep mode
  uint8_t channelNum
    = eeprom_read_byte((const uint8_t*)EEPROM_RADIO_XRF_CHANNEL);
  if (channelNum != 0xFF) {
    stream << "ATCN " << int(channelNum) << '\r';
    console << "Channel number: " << channelNum << endl;
  }
  stream << "ATAC\r"    // Apply changes
	<< "ATDN\r";   // Done
  delay(300);
  while (stream.available()) {
    stream.read();
  }
  
  return found;
}

void XRF_Radio::poll(void)
{
  ; // No polling needed
}

