# Location where Arduino software installed
ARDUINO_DIR = /usr/local/arduino

# arduino-builder  location 
BUILDER = $(ARDUINO_DIR)/arduino-builder

# Absolute path of sketch. Assumes current working directory is the
# sketch directory.
# SKETCH_DIR := `readlink -f .`
SKETCH_DIR = $(shell readlink -f .)

SKETCH_NAME = $(shell basename $(SKETCH_DIR))
SKETCH_FILE = $(SKETCH_DIR)/$(SKETCH_NAME).ino

# Root directory of the AuroraWatchNet git repository
# AWN_DIR := `readlink -f $(SKETCH_DIR)/../../../..`
AWN_DIR = $(shell readlink -f $(SKETCH_DIR)/../../../..)

# Get the parent process of make
PPID = $(strip $(shell ps -o ppid= -p $$PPID))
BUILD_DIR = /tmp/build-$(SKETCH_NAME).$(PPID)/$(SKETCH_NAME)-$(SPEED)-$(COMMS_HW)

SPEED = 12MHz
COMMS_HW=COMMS_W5100
WARN_PERCENTAGE = 45
FIRMWARE_DIR = $(SKETCH_DIR)/firmware/ATmega1284P/$(SPEED)/$(COMMS_HW)
FIRMWARE_NAME = MagCloud-0.25a
COPY = cp
MKDIR = mkdir

default : compile

clean : 
	rm -rf /tmp/build-$(SKETCH_NAME).$(PPID)

clean-firmware :
	rm -rf $(SKETCH_DIR)/firmware

realclean : clean clean-firmware

make-build-dir : 
	$(MKDIR) -p $(BUILD_DIR)

dump-prefs : make-build-dir
	$(BUILDER) -dump-prefs -logger=machine -hardware "$(ARDUINO_DIR)/hardware" -hardware "$(AWN_DIR)/software/magnetometer/sketches/hardware" -tools "$(ARDUINO_DIR)/tools-builder" -tools "$(ARDUINO_DIR)/hardware/tools/avr" -built-in-libraries "$(ARDUINO_DIR)/libraries" -libraries "$(AWN_DIR)/software/magnetometer/sketches/libraries" -fqbn=calunium:avr:calunium_atmega1284p:speed=$(SPEED),variant=pcb,sketchinclude=none -ide-version=10608 -build-path "$(BUILD_DIR)" -warnings=all -prefs=build.warn_data_percentage=$(WARN_PERCENTAGE) -prefs="compiler.c.extra_flags=-DCOMMS_HW=$(COMMS_HW)" -prefs="compiler.cpp.extra_flags=-DCOMMS_HW=$(COMMS_HW)" -verbose "$(SKETCH_FILE)"

compile : dump-prefs
	$(BUILDER) -compile -logger=machine -hardware "$(ARDUINO_DIR)/hardware" -hardware "$(AWN_DIR)/software/magnetometer/sketches/hardware" -tools "$(ARDUINO_DIR)/tools-builder" -tools "$(ARDUINO_DIR)/hardware/tools/avr" -built-in-libraries "$(ARDUINO_DIR)/libraries" -libraries "$(AWN_DIR)/software/magnetometer/sketches/libraries" -fqbn=calunium:avr:calunium_atmega1284p:speed=$(SPEED),variant=pcb,sketchinclude=none -ide-version=10608 -build-path "$(BUILD_DIR)" -warnings=all -prefs=build.warn_data_percentage=$(WARN_PERCENTAGE) -prefs="compiler.c.extra_flags=-DCOMMS_HW=$(COMMS_HW)" -prefs="compiler.cpp.extra_flags=-DCOMMS_HW=$(COMMS_HW)" -verbose "$(SKETCH_FILE)"
	$(MKDIR) -p $(FIRMWARE_DIR)
	$(COPY) $(BUILD_DIR)/$(SKETCH_NAME).ino.hex $(FIRMWARE_DIR)/$(FIRMWARE_NAME).hex
	$(COPY) $(BUILD_DIR)/$(SKETCH_NAME).ino.with_bootloader.hex $(FIRMWARE_DIR)/$(FIRMWARE_NAME).with_bootloader.hex

all :
	$(MAKE) PPID=$(PPID) SPEED=8MHz_RC COMMS_HW=COMMS_W5100 compile
	$(MAKE) PPID=$(PPID) SPEED=12MHz COMMS_HW=COMMS_W5100 compile

