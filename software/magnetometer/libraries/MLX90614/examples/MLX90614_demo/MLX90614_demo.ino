#include <AsyncDelay.h>
#include <SoftWire.h>
#include <MLX90614.h>
#include <DisableJTAG.h>

MLX90614 mlx90614;
AsyncDelay samplingInterval;

inline float convertToDegC(int16_t data)
{
  return (data / 100.0);
}

void setup(void)
{
  Serial.begin(9600);
  Serial.println("MLX90614_demo");
#ifdef JTD
  disableJTAG();
#endif
  mlx90614.initialise();
  samplingInterval.start(1000, AsyncDelay::MILLIS);
}

bool printed = true;
void loop(void)
{
  if (samplingInterval.isExpired() && !mlx90614.isSampling()) {
    mlx90614.start();
    printed = false;
    samplingInterval.repeat();
    Serial.println("Sampling started");
  }

  mlx90614.process();

  if (mlx90614.isFinished() && !printed) {
    printed = true;
    // Print saved values
    Serial.print("Ambient: ");
    Serial.print(convertToDegC(mlx90614.getAmbient()));
    Serial.print("    Object 1: ");
    Serial.print(convertToDegC(mlx90614.getObject1()));
    if (mlx90614.isDualSensor()) {
      Serial.print("Object 2: ");
      Serial.print(convertToDegC(mlx90614.getObject2()));
    }
    Serial.println();
  }
  
}
