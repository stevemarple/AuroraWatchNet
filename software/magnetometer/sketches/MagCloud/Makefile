# Location where Arduino software installed
ARDUINO_DIR = /usr/local/arduino

# arduino-builder name and location 
BUILDER = $(ARDUINO_DIR)/arduino-builder

# Extra compilation flags passed to arduino-builder, such as to
# indicate which communication hardware should be supported.
EXTRA_FLAGS = -DCOMMS_W5100 -DCOMMS_XRF -DETHERNET2_USE_WDT
C_EXTRA_FLAGS = $(EXTRA_FLAGS)
CPP_EXTRA_FLAGS = $(EXTRA_FLAGS)

# Hardware identifier
HW_IDENT=XRF_W5100

BUILDER_PREFS = -prefs=build.warn_data_percentage=$(WARN_PERCENTAGE) -prefs="compiler.c.extra_flags=$(C_EXTRA_FLAGS)" -prefs="compiler.cpp.extra_flags=$(CPP_EXTRA_FLAGS)"

# Absolute path of sketch. Assumes current working directory is the
# sketch directory.
# SKETCH_DIR := `readlink -f .`
SKETCH_DIR = $(shell readlink -f .)

SKETCH_NAME = $(shell basename $(SKETCH_DIR))
SKETCH_FILE = $(SKETCH_DIR)/$(SKETCH_NAME).ino

# Root directory of the AuroraWatchNet git repository
AWN_DIR = $(shell readlink -f $(SKETCH_DIR)/../../../..)

# Get the parent process of make.This is normally the shell which
# invokes make so that each terminal session compiles into a different
# set of build directories.
PPID = $(strip $(shell ps -o ppid= -p $$PPID))

# Use a sparate build directory for each firmware version (different
# clock speed, communication hardware etc)
BUILD_DIR = /tmp/build-$(SKETCH_NAME).$(PPID)/$(SKETCH_NAME)-$(SPEED)-$(HW_IDENT)

SPEED = 8MHz_RC
WARN_PERCENTAGE = 45
FIRMWARE_DIR = $(SKETCH_DIR)/firmware/ATmega1284P/$(SPEED)/$(HW_IDENT)
FIRMWARE_NAME := $(shell awk '(match($$0, /^\#define\s+FIRMWARE_VERSION\s+"(.*)"/,a)){print a[1]}' MagCloud.ino)
COPY = cp
MKDIR = mkdir

default : compile

clean : clean-build

clean-build : 
	rm -rf $(BUILD_DIR)/*

clean-all-builds : 
	rm -rf /tmp/build-$(SKETCH_NAME).$(PPID)/*/*

clean-firmware :
	rm -rf $(SKETCH_DIR)/firmware

realclean : clean clean-all-builds clean-firmware
	rm -rf /tmp/build-$(SKETCH_NAME).$(PPID)

make-build-dir : 
	$(MKDIR) -p $(BUILD_DIR)

dump-prefs : make-build-dir
	$(BUILDER) -dump-prefs -logger=machine -hardware "$(ARDUINO_DIR)/hardware" -hardware "$(AWN_DIR)/software/magnetometer/sketches/hardware" -tools "$(ARDUINO_DIR)/tools-builder" -tools "$(ARDUINO_DIR)/hardware/tools/avr" -built-in-libraries "$(ARDUINO_DIR)/libraries" -libraries "$(AWN_DIR)/software/magnetometer/sketches/libraries" -fqbn=calunium:avr:calunium_atmega1284p:speed=$(SPEED),variant=pcb,sketchinclude=none -ide-version=10608 -build-path "$(BUILD_DIR)" -warnings=all $(BUILDER_PREFS) -verbose "$(SKETCH_FILE)"

compile : dump-prefs
	$(BUILDER) -compile -logger=machine -hardware "$(ARDUINO_DIR)/hardware" -hardware "$(AWN_DIR)/software/magnetometer/sketches/hardware" -tools "$(ARDUINO_DIR)/tools-builder" -tools "$(ARDUINO_DIR)/hardware/tools/avr" -built-in-libraries "$(ARDUINO_DIR)/libraries" -libraries "$(AWN_DIR)/software/magnetometer/sketches/libraries" -fqbn=calunium:avr:calunium_atmega1284p:speed=$(SPEED),variant=pcb,sketchinclude=none -ide-version=10608 -build-path "$(BUILD_DIR)" -warnings=all $(BUILDER_PREFS) -verbose "$(SKETCH_FILE)"
	$(MKDIR) -p $(FIRMWARE_DIR)
	$(COPY) $(BUILD_DIR)/$(SKETCH_NAME).ino.hex $(FIRMWARE_DIR)/$(FIRMWARE_NAME).hex
	$(COPY) $(BUILD_DIR)/$(SKETCH_NAME).ino.with_bootloader.hex $(FIRMWARE_DIR)/$(FIRMWARE_NAME).with_bootloader.hex
	$(COPY) $(BUILD_DIR)/$(SKETCH_NAME).ino.elf $(FIRMWARE_DIR)/$(FIRMWARE_NAME).elf
	./mkfwimage.py -e $(FIRMWARE_DIR)/$(FIRMWARE_NAME).elf -f $(FIRMWARE_NAME)
	-echo Firmware copied to $(FIRMWARE_DIR)

all :
	$(MAKE) PPID=$(PPID) SPEED=8MHz_RC HW_IDENT=XRF_W5100 \
		EXTRA_FLAGS="-DCOMMS_XRF -DCOMMS_W5100 -DFEATURE_FLC100 -DFEATURE_HIH61XX -DFEATURE_MLX90614 -DETHERNET2_USE_WDT" \
		compile
	$(MAKE) PPID=$(PPID) SPEED=12MHz HW_IDENT=W5100_GNSS \
		EXTRA_FLAGS="-DCOMMS_W5100 -DFEATURE_FLC100 -DFEATURE_GNSS -DETHERNET2_USE_WDT" \
		compile
	$(MAKE) PPID=$(PPID) SPEED=12MHz HW_IDENT=W5500_GNSS \
		EXTRA_FLAGS="-DCOMMS_W5500 -DFEATURE_FLC100 -DFEATURE_GNSS -DETHERNET2_USE_WDT" \
		compile
	@echo Success
