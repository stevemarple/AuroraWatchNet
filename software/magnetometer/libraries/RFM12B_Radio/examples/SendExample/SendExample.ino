#include <CommsInterface.h>
#include <CircBuffer.h>
#include <RF12.h>
#include <RF12_Stream.h>
#include <RFM12B_Radio.h>
#include <AsyncDelay.h>

uint8_t rfm12b_rxBuffer[60];
uint8_t rfm12b_txBuffer[60];
RF12_Stream rf12_stream(rfm12b_rxBuffer, sizeof(rfm12b_rxBuffer),
			rfm12b_txBuffer, sizeof(rfm12b_txBuffer));
RFM12B_Radio rfm12b(rf12_stream);

unsigned long sendInterval_ms = 2000UL;
AsyncDelay sendDelay;

void setup(void)
{
  Serial.begin(9600);
  if (rfm12b.begin(14, 6, 2, 1, RF12_433MHZ)) {
    Serial.println("Found RFM12B");
  }
  else {
    while (1)
      Serial.println("RFM12B not found");
  }
  sendDelay.expire();
}

void loop(void)
{
  rfm12b.poll();

  if (sendDelay.isExpired()) {
    rfm12b.print("*** Millis is ");
    rfm12b.println(millis());

    Serial.print("*** Millis is ");
    Serial.println(millis());

    sendDelay.start(sendInterval_ms, AsyncDelay::MILLIS);
  }
    
}
