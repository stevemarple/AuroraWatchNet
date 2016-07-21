#!/bin/sh

### BEGIN INIT INFO
# Provides:          ftdi_monitor
# Required-Start:
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       Monitor state of data quality switch
### END INIT INFO




USER="pi"
DESC="AuroraWatchNet data quality monitoring"
PID_FILE="/var/aurorawatchnet/ftdi_monitor.pid.lock"
PORT="/dev/ttyUSB0"
QUAL_FILE="/var/aurorawatchnet/data_quality_warning"

get_pid() {
    if [ -f "$PID_FILE" ]; then
	cat $PID_FILE
    fi
}


start_stop_server() {
    pid=`get_pid`
    case "$1" in
        start)
	    echo -n "Starting $DESC: ftdi_monitor"
	    if [ -z "$pid" ]; then
		su -c "~${USER}/bin/ftdi_monitor.py -d --port ${PORT} --filename ${QUAL_FILE}" - $USER
	    fi
	    echo "."
            ;;

        stop)
	    echo -n "Stopping $DESC: ftdi_monitor"
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
	    echo -n "Status for $DESC: "
	    if [ -n "$pid" ]; then
		echo -n "running (PID = $pid)"
	    else
		echo -n "stopped"
	    fi
	    echo "."
            ;;

        zap)
	    echo -n "Zapping $DESC: ftdi_monitor"
	    if [ -n "$pid" ]; then
		kill -9 $pid
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
