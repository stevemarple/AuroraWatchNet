#include <SoftWire.h>
#include <HIH61xx.h>
#include <AsyncDelay.h>

HIH61xx hih;
AsyncDelay samplingInterval;

void setup(void)
{
  Serial.begin(9600);
  hih.initialise(A4, A5);
  samplingInterval.start(3000, AsyncDelay::MILLIS);
}


bool printed = true;
void loop(void)
{
  if (samplingInterval.isExpired() && !hih.isSampling()) {
    hih.start();
    printed = false;
    samplingInterval.repeat();
    Serial.println("Sampling started");
  }

  hih.process();
  
  if (hih.isFinished() && !printed) {
    printed = true;
    // Print saved values
    Serial.print("RH: ");
    Serial.print(hih.getRelHumidity() / 100.0);
    Serial.println(" %");
    Serial.print("Ambient: ");
    Serial.print(hih.getAmbientTemp() / 100.0);
    Serial.println(" deg C");
    Serial.print("Status: ");
    Serial.println(hih.getStatus());
  }
  
}
