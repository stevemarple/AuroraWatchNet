#!/bin/bash
# shellcheck disable=SC2034
#
# SC2034: X appears unused, see https://www.shellcheck.net/wiki/SC2034

set -e

DATA_DIR="/data"
INSTALL_USER=$(id -r -u -n)
INSTALL_GROUP=$(id -r -g -n)
INSTALL_HOME=$(getent passwd "$INSTALL_USER" | cut -d : -f 6)
TEMP_FILE="/tmp/$(basename "$0").$$"

# Uncomment to uninstall everything (best effort)
#UNINSTALL=1


# Intercept calls to sudo so that it can be printed.
sudo() {
	echo "sudo" "$@"
	/usr/bin/sudo "$@"
}


# List of Git repositories to install
GIT_REPOSITORIES=""
GIT_REPOSITORIES+=" https://github.com/stevemarple/AuroraWatchNet.git"
GIT_REPOSITORIES+=" https://github.com/stevemarple/auroraplot.git"
GIT_REPOSITORIES+=" https://github.com/stevemarple/Calunium.git"
GIT_REPOSITORIES+=" https://github.com/stevemarple/xboot.git"

# List of local Python packages to install 
PYTHON_LOCAL_PACKAGES=""
PYTHON_LOCAL_PACKAGES+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/aurorawatchnet"
PYTHON_LOCAL_PACKAGES+=" ${INSTALL_HOME}/auroraplot/auroraplot"

# shellcheck disable=SC1091
. /etc/os-release
if [ "$ID" != 'debian' ]; then
	echo "This installation assumes Debian OS"
	exit 1
fi

cd "$INSTALL_HOME"

########################################
#
# GET INSTALLATION TYPE
#
########################################
if [ -z "$EQUIPMENT_TYPE" ]; then
	read -r -e -p "Which type of equipment is in use? [calunium-mag-w5100, calunium-mag-w5500, calunium-mag-xrf, raspi-mag, bgs-mag, riometer] ? " EQUIPMENT_TYPE
fi

case "$EQUIPMENT_TYPE" in
	calunium-mag*)
		# A remote microcontroller acquires data which is then sent
		# via some communication method to the daemon, typically
		# running on a Raspberry Pi. The daemon stores the data
		# locally and may forward the data somehow to a data
		# processing server.
		IS_MAG=1
		IS_MAG_CALUNIUM=1
		# CALUNIUM_COMMS=$(echo "$EQUIPMENT_TYPE" | sed 's/^calunium-mag-//;')
		# calunium-mag-X => X
		CALUNIUM_COMMS="${EQUIPMENT_TYPE//calunium-mag-/}"
		
		SAMPLE_AWNET_INI_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/ini_files/calunium_${CALUNIUM_COMMS}_awnet.ini"
		DAEMON="${INSTALL_HOME}/AuroraWatchNet/software/server/bin/awnetd.py"
		# SYSTEMD_SERVICE_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/systemd/awnet.service"
		SYSTEMD_SERVICE_NAME="awnet.service"
		SYSTEMD_SERVICE_DESC="AuroraWatchNet service"
		;;
	raspi-mag)
		# The Raspberry Pi acquires data locally and records to a
		# local disk. The daemon stores the data locally and may
		# forward the data somehow to a data processing server.
		IS_MAG=1
		IS_MAG_RASPI=1
		GIT_REPOSITORIES+=" https://github.com/stevemarple/python-MCP342x"
		PYTHON_LOCAL_PACKAGES+=" ${INSTALL_HOME}/python-MCP342x/MCP342x"
		SAMPLE_AWNET_INI_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/ini_files/raspimagd_awnet.ini"
		DAEMON="${INSTALL_HOME}/AuroraWatchNet/software/server/bin/raspimagd.py"
		# SYSTEMD_SERVICE_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/systemd/raspimag.service"
		SYSTEMD_SERVICE_NAME="raspimag.service"
		SYSTEMD_SERVICE_DESC="AuroraWatchNet service"
		;;
	bgs-mag)
		# The Raspberry Pi acquires data locally and records to a
		# local disk. The daemon stores the data locally and may
		# forward the data somehow to a data processing server.
		IS_MAG=1
		IS_MAG_BGS=1
		GIT_REPOSITORIES+=" https://github.com/stevemarple/python-MCP342x"
		PYTHON_LOCAL_PACKAGES+=" ${INSTALL_HOME}/python-MCP342x/MCP342x"
		SAMPLE_AWNET_INI_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/ini_files/raspimagd_bgs_awnet.ini"
		DAEMON="${INSTALL_HOME}/AuroraWatchNet/software/server/bin/raspimagd.py"
		# SYSTEMD_SERVICE_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/systemd/raspimag.service"
		SYSTEMD_SERVICE_NAME="raspimag.service"
		SYSTEMD_SERVICE_DESC="BGS magnetometer service"
		;;
	riometer)
		# A remote microcontroller acquires data which is then sent
		# via Ethernet to the daemon, typically running on a Raspberry
		# Pi. The daemon stores the data locally and may forward the
		# data somehow to a data processing server.
		IS_RIOMETER=1
		SAMPLE_AWNET_INI_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/ini_files/riometer_awnet.ini"
		DAEMON="${INSTALL_HOME}/AuroraWatchNet/software/server/bin/awnetd.py"
		# SYSTEMD_SERVICE_FILE="${INSTALL_HOME}/AuroraWatchNet/software/server/systemd/awnet.service"
		SYSTEMD_SERVICE_NAME="awnet.service"
		SYSTEMD_SERVICE_DESC="Riometer data collection service"
		;;
	*)
		echo "Unknown INSTALL_TYPE: ${EQUIPMENT_TYPE}"
		exit 1
		;;
esac

########################################
#
# UPDATE AND INSTALL SYSTEM SOFTWARE
#
########################################
DEB_PACKAGES=""
DEB_PACKAGES+=" screen "
DEB_PACKAGES+=" git git-doc git-man "
DEB_PACKAGES+=" python3-pip python3-matplotlib python3-scipy python3-serial"
DEB_PACKAGES+=" python3-daemon python3-lockfile python3-smbus python3-six"
DEB_PACKAGES+=" ipython3"
DEB_PACKAGES+=" avahi-daemon dnsutils i2c-tools tcpdump"

if [ "$VERSION_ID" -gt 12 ]; then
	DEB_PACKAGES+=" ntpsec"
else
	DEB_PACKAGES+=" ntp"
fi
DEB_PACKAGES+=" ntpstat"

sudo apt update
sudo apt upgrade
# shellcheck disable=SC2086
sudo apt install $DEB_PACKAGES

########################################
#
# INSTALL GIT REPSOITORIES
#
########################################

for repo in $GIT_REPOSITORIES; do
	install_dir="${INSTALL_HOME}/"$(basename "$repo" .git)
	if [ "$UNINSTALL" ]; then
		read -r -e -p "Remove directory ${install_dir} ? [y/N] " choice
		choice=$(echo "$choice" | tr '[:upper:]' '[:lower:]')
		case "$choice"  in
			y|yes)
				echo "Removing directory ${install_dir}"
				rm -rf "$install_dir" || true
				;;
			*)
				echo "Leaving directory ${install_dir} intact"
				;;
		esac
	else
		if [ -d "$install_dir" ]; then
			echo "${repo} is already installed, updating"
			cd "$install_dir"
			git fetch
			git pull --ff-only
			git submodule update --init --recursive
			cd
		else
			echo "Clone repository ${repo}"
			git clone --recursive "$repo"
		fi
	fi
done

########################################
#
# ADD LINKS IN PYTHON SITE PACKAGES DIRECTORY TO
# INSTALL LOCAL PACKAGES
#
########################################
PYTHON_SITE_PACKAGES_DIR=$(python -m site --user-site)

mkdir -p "$PYTHON_SITE_PACKAGES_DIR"
cd "$PYTHON_SITE_PACKAGES_DIR"

for f in $PYTHON_LOCAL_PACKAGES; do
	symlink="${PYTHON_SITE_PACKAGES_DIR}/"$(basename "$f")
	if [ "$UNINSTALL" ]; then
		echo "Removing symbolic link ${symlink}"
		rm -f "$symlink" || true
	else
		echo "Creating/updating symbolic link ${symlink}"
		# Create relative, symbolic links, replace if already exist
		ln -f -n -r -s "$f" "$symlink"
	fi
done
cd

########################################
#
# ADD LINKS IN ~/bin
#
########################################
BIN_LINKS=""
BIN_LINKS+=" ${DAEMON}"
BIN_LINKS+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/bin/send_cmd.py"
BIN_LINKS+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/bin/log_ip"
BIN_LINKS+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/bin/upload_data.py"
BIN_LINKS+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/bin/upload_data.py"
BIN_LINKS+=" ${INSTALL_HOME}/AuroraWatchNet/software/server/bin/check_ntp_status"

mkdir -p "${INSTALL_HOME}/bin"
for f in $BIN_LINKS; do
	symlink="${INSTALL_HOME}/bin/"$(basename "$f")
	if [ "$UNINSTALL" ]; then
		echo "Removing symbolic link ${symlink}"
		rm -f "${INSTALL_HOME}/bin/${symlink}" || true
	else
		echo "Creating/updating symbolic link ${symlink}"
		# Create relative, symbolic links, replace if already exist
		ln -f -n -r -s "$f" "$symlink"
	fi
done
cd


########################################
#
# CREATE DATA DIRECTORY
#
# The uninstall process will not remove this directory.
#
########################################
if [ "$UNINSTALL" ]; then
	if [ -d "$DATA_DIR" ]; then
		echo "Data directory ${DATA_DIR} exists, not removing"
	fi
else
	if [ -d "$DATA_DIR" ]; then
		echo "Data directory ${DATA_DIR} already exists"
	else
		sudo mkdir "$DATA_DIR"
		sudo chown "${INSTALL_USER}:${INSTALL_GROUP}" "$DATA_DIR"
	fi
fi


########################################
#
# COPY SAMPLE CONFIGURATION FILE
#
# The uninstall process will only remove the sample file.
#
########################################
AWNET_INI="/etc/awnet.ini"
SAMPLE_AWNET_INI_DEST_FILE="${AWNET_INI}.sample"
if [ "$UNINSTALL" ]; then
	if [ -f "$SAMPLE_AWNET_INI_DEST_FILE" ]; then
		echo "Removing ${SAMPLE_AWNET_INI_DEST_FILE}"
		sudo rm -f "$SAMPLE_AWNET_INI_DEST_FILE" || true
	fi
	if [ -f "$AWNET_INI" ]; then
		echo "Not removing ${$AWNET_INI}"
	fi
else
	sudo cp -f "$SAMPLE_AWNET_INI_FILE" "$SAMPLE_AWNET_INI_DEST_FILE"
fi


########################################
#
# CREATE CRONTAB
#
# The uninstall process will not remove the user crontab.
#
########################################
USER_CRONTAB=$(crontab -l || true)
if [ "$UNINSTALL" ]; then
	if [ -n "$USER_CRONTAB" ]; then
		echo "Not removing crontab for user ${INSTALL_USER}"
	fi
else
	if [ -n "$USER_CRONTAB" ]; then
		echo "Not overwriting crontab for ${INSTALL_USER}"
	else
		# shellcheck disable=SC2166
		if [ "$IS_MAG_RASPI" = 1 -o "$IS_MAG_BGS" = 1 ]; then
			SAMPLE_CRONTAB="${INSTALL_HOME}/AuroraWatchNet/software/server/crontabs/raspimagd.crontab"
		else
			SAMPLE_CRONTAB="${INSTALL_HOME}/AuroraWatchNet/software/server/crontabs/awnetd.crontab"
		fi

		echo "Testing crontab file"
		crontab -n "$SAMPLE_CRONTAB"
		echo "Installing crontab file"
		crontab "$SAMPLE_CRONTAB"
	fi
fi


########################################
#
# INSTALL SYSTEMD SERVICE FILE
#
########################################
INSTALLED_SYSTEMD_SERVICE_FILE="/etc/systemd/system/${SYSTEMD_SERVICE_NAME}"
DEFAULTS_NAME=$(basename "$SYSTEMD_SERVICE_NAME" .service)
DEFAULTS_FILE="/etc/default/${DEFAULTS_NAME}"

if [ "$UNINSTALL" ]; then
	# Stop and disable service, then remove service file
	if [ -f "$INSTALLED_SYSTEMD_SERVICE_FILE" ]; then
		echo "Stopping ${SYSTEMD_SERVICE_NAME}"
		sudo systemctl stop "$SYSTEMD_SERVICE_NAME" || true
		
		echo "Stopping ${SYSTEMD_SERVICE_NAME}"
		sudo systemctl disable "$SYSTEMD_SERVICE_NAME" || true

		echo "Removing ${INSTALLED_SYSTEMD_SERVICE_FILE}"
		sudo rm -f "$SYSTEMD_SERVICE_FILE" || true

		echo "Reloading systemd daemon"
		sudo systemctl daemon-reload || true
	else
		echo "systemd service file ${INSTALLED_SYSTEMD_SERVICE_FILE} not found"
	fi

	# Defaults file should be removed after the service
	if [ -f "$DEFAULTS_NAME" ]; then
		echo "Removing ${DEFAULTS_FILE}"
		sudo rm -f "$DEFAULTS_FILE" || true
	else
		echo "Defaults file ${DEFAULTS_FILE} not found"
	fi
else
	# Construct customized defaults file
	echo "Making customized defaults file"
	cat - > "$TEMP_FILE" <<EOF
# This file can be used to alter the options used when starting
# ${SYSTEMD_SERVICE_NAME}.
#
DAEMON_ARGS=""
#
# Uncomment line below to set log-level
# DAEMON_ARGS+=" --log-level=warn"
EOF

	echo "Installing customized defaults file"
	sudo cp "$TEMP_FILE" "$DEFAULTS_FILE"
	
	# Construct customized service file
	SCREEN_NAME=$(basename "$DAEMON" .py)
	echo "Making customized service file"
	cat - > "$TEMP_FILE" <<EOF
[Unit]
Description=${SYSTEMD_SERVICE_DESC}
After=network-online.target
ConditionPathExists=${AWNET_INI}

[Service]
# Set DAEMON_ARGS in the environment file to adjust run-time options
EnvironmentFile=-/etc/default/%N
User=${INSTALL_USER}
WorkingDirectory=${INSTALL_HOME}

# For debugging and development run via a screen session.
# Type must be set to "forking".
# As user ${INSTALL_USER} use "screen -d -r ${SCREEN_NAME}" to connect and view
# Type=forking
# ExecStart=/usr/bin/screen -d -m -S ${SCREEN_NAME} ${DAEMON} -c ${AWNET_INI} \$DAEMON_ARGS

# For production use run the emulator as a normal process. Type must be set
# to "simple". Warnings and errors will be logged to systemd's journal.
Type=simple
ExecStart=${DAEMON} -c ${AWNET_INI} \$DAEMON_ARGS

StandardOutput=journal
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

	echo "Installing ${SYSTEMD_SERVICE_NAME} service file"
	sudo cp "$TEMP_FILE" "$INSTALLED_SYSTEMD_SERVICE_FILE"

	echo "Enabling ${SYSTEMD_SERVICE_NAME} service"
	sudo systemctl enable "$SYSTEMD_SERVICE_NAME"  || true

	echo "Reloading systemd daemon"
	sudo systemctl daemon-reload || true
fi


########################################
#
# OUTPUT COMPLETION MESSAGE
#
########################################
echo
if [ "$UNINSTALL" ]; then
	echo "Uninstall complete"
else
	echo "Installation complete"
	if [ ! -f "$AWNET_INI" ]; then
		echo
		echo "The ${SYSTEMD_SERVICE_NAME} will not run until the ${AWNET_INI}"
		echo "file has been created. A sample file has been installed at"
		echo "${SAMPLE_AWNET_INI_DEST_FILE}."
	fi
fi

