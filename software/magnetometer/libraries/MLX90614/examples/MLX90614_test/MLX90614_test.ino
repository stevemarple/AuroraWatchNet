#include <mysofti2cmaster.h>
#include <MLX90614.h>
#include <AsyncDelay.h>
#include <DisableJTAG.h>

MLX90614 mlx90614;
AsyncDelay samplingInterval;

inline float convertToDegC(uint16_t data)
{
  return (float(MLX90614::convertToCentiK(data)) / 100) - 273.15;
}

void setup(void)
{
  Serial.begin(9600);
#ifdef JTD
  disableJTAG();
#endif
  mlx90614.initialise();
  samplingInterval.start(3000, AsyncDelay::MILLIS);
}


void loop(void)
{
  if (samplingInterval.isExpired() && !mlx90614.isSampling()) {
    mlx90614.start();
    samplingInterval.repeat();
    Serial.println("Sampling started");
  }

  mlx90614.process();

  if (mlx90614.isFinished() && !mlx90614.isPowerOff()) {
    mlx90614.powerOff();
    // Print saved values
    Serial.print("Ambient: ");
    Serial.println(convertToDegC(mlx90614.getAmbient()));
    Serial.print("Object 1: ");
    Serial.println(convertToDegC(mlx90614.getObject1()));
    if (mlx90614.isDualSensor()) {
      Serial.print("Object 2: ");
      Serial.println(convertToDegC(mlx90614.getObject2()));
    }
  }
  
}
