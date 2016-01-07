#include <AsyncDelay.h>
#include <HouseKeeping.h>

AsyncDelay samplingInterval;

void setup(void)
{
  Serial.begin(9600);
  houseKeeping.initialise(3300, true);
  samplingInterval.start(3000, AsyncDelay::MILLIS);
}


void loop(void)
{
  if (samplingInterval.isExpired() && !houseKeeping.isSampling()) {
    houseKeeping.start();
    samplingInterval.repeat();
    // Serial.println("Sampling started");
  }
  
  houseKeeping.process();

  if (houseKeeping.isFinished() && !houseKeeping.isPowerOff()) {
    houseKeeping.powerOff();
    // Print saved values
  
    Serial.print("System temp: ");
    Serial.print(float(houseKeeping.getSystemTemperature()) / 100);
    Serial.print(" deg C    Vin: ");
    Serial.print(float(houseKeeping.getVin()) / 1000);
    Serial.println(" V");
  }

}
