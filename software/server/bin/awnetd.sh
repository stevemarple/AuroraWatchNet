#!/bin/sh

### BEGIN INIT INFO
# Provides:          awnetd
# Required-Start:
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       AuroraWatchNet data collection
### END INIT INFO

# Get daemon name
PROG=`basename $0`

if [ "`id -u -n`" != "root" ]; then
    echo "This program must be run by root"
    exit
fi

# Check for any site-specific variation. If so expect the daemon to be
# called as awnetd_<SITE>
SITE=`/bin/echo $PROG | sed 's/^awnetd_//g;'`
if [ "$SITE" = "awnetd" ]; then
    SITE=""
    SITE_SUFFIX=""
    DESC="AuroraWatchNet data collection"
else
    SITE_SUFFIX="_${SITE}"
    DESC="AuroraWatchNet data collection for ${SITE}"
fi

# User to run the daemon as
USER="pi"

# Path to the daemon
DAEMON="/home/pi/bin/awnetd.py"
DAEMON_OPTIONS="-v -v -v -v"

# The name of the awnet.ini file.
INI_FILE="/etc/awnet${SITE_SUFFIX}.ini"

# Does a shell config file exist to alter these settings?
CONF_FILE="/etc/awnetd${SITE_SUFFIX}.conf"
if [ -f "$CONF_FILE" ]; then
    # Yes, source the file
    . "$CONF_FILE"
fi


get_pid() {
    su -c "screen -list" - $USER | grep awnetd${SITE_SUFFIX} | cut -d. -f1 | tr -d '[:blank:]'
}


start_stop_server() {
    pid=`get_pid`
    case "$1" in
        start)
	    echo -n "Starting ${DESC}: ${PROG}"
	    if [ -z "$pid" ]; then
		su -c "screen -d -m -S awnetd${SITE_SUFFIX} ${DAEMON} -c ${INI_FILE} ${DAEMON_OPTIONS}" - $USER
	    fi
	    echo "."
            ;;

        stop)
	    echo -n "Stopping ${DESC}: ${PROG}"
	    if [ -n "$pid" ]; then
		kill $pid
	    fi
	    echo "."
            ;;

        restart|force-reload)
            start_stop_server stop
            start_stop_server start
            ;;

	# status and zap are found in Gentoo runscripts but are useful
	# so included here.
	status)
	    echo -n "Status for ${DESC}: "
	    if [ -n "$pid" ]; then
		echo -n "running (PID = $pid)"
	    else
		echo -n "stopped"
	    fi
	    echo "."
            ;;

        zap)
	    echo -n "Zapping $DESC: awnetd"
	    if [ -n "$pid" ]; then
		kill -9 $pid
		su -c "screen -wipe" - $USER > /dev/null 2>&1
	    fi
	    echo "."
	    ;;
        *)
	    echo "Unknown action: $1"
	    return 1
            ;;
    esac
}

action="$1"

# DISPLAY is not needed and if set can cause su to emit unwanted warnings.
unset DISPLAY

if [ -z "$action" ]; then
    echo "$0 start|stop|restart|status"
    exit 1
fi

start_stop_server "$action"
exit $?
