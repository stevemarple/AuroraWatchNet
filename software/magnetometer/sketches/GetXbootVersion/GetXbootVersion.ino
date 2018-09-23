/*
 * Get xboot version
 *
 * Make API calls to return the version of xboot, and its API level.
 *
 */

#include "xbootapi.h"

HardwareSerial &console = Serial;


Stream& printReturnStatus(Stream &s, uint8_t status)
{
	switch (status) {
	case XB_SUCCESS:
		s.print(F("XB_SUCCESS"));
		break;
	case XB_ERR_NO_API:
		s.print(F("XB_ERR_NO_API"));
		break;
	case XB_ERR_NOT_FOUND:
		s.print(F("XB_ERR_NOT_FOUND"));
		break;
	case XB_INVALID_ADDRESS:
		s.print(F("XB_INVALID_ADDRESS"));
		break;
	default:
		s.print(F("<Unknown return status>"));
		break;
	}
	return s;
}

void setup(void)
{
	uint8_t r;
	uint16_t majorMinor;
	uint8_t apiVersion;
#if (F_CPU > 8000000UL)
	console.begin(115200);
#else
	console.begin(9600);
#endif

	console.println();
	console.println(F("Get xboot version"));

	console.print(F("F_CPU "));
	console.print(F_CPU / 1000000UL);
	console.println(F(" MHz"));

	console.print(F("Xboot version: "));
	r = xboot_get_version(&majorMinor);
	if (r == 0) {
		console.print((int)((majorMinor & 0xFF00) >> 8));
		console.print('.');
		console.println((int)(majorMinor & 0xFF));
	}
	else {
		printReturnStatus(console, r);
		console.println();
	}

	console.print(F("Xboot API version: "));
	r = xboot_get_api_version(&apiVersion);
	if (r == 0) {
		console.println((int)apiVersion);
	}
	else {
		printReturnStatus(console, r);
		console.println();
	}


}


void loop(void)
{

}
