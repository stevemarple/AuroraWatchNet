#ifndef COMMAND_HANDLER_H
#define COMMAND_HANDLER_H

#include <RTCx.h>

#include <stdint.h>

#include "xbootapi.h"

class CommandHandler {
public:
  // Return clock error
  static bool checkTime(RTCx::time_t t, RTCx::time_t &err);
  static bool setTime(RTCx::time_t t);
  
  inline CommandHandler(void);
  
  void process(Stream &console);
  
private:
  static const uint8_t bufferLen = 80;
  char buffer[bufferLen];
  char *ptr;
};

CommandHandler::CommandHandler(void) : ptr(buffer)
{
  ;
}


#endif
