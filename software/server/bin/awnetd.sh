#!/bin/sh

### BEGIN INIT INFO
# Provides:          awnetd
# Required-Start:
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Description:       AuroraWatchNet data collection
### END INIT INFO


USER="pi"
DESC="AuroraWatchNet data collection"


get_pid() {
    su -c "screen -list" - $USER | grep awnetd | cut -d. -f1 | tr -d '[:blank:]'
}


start_stop_server() {
    pid=`get_pid`
    case "$1" in
        start)
	    echo -n "Starting $DESC: awnetd"
	    if [ -z "$pid" ]; then
		su -c "screen -d -m -S awnetd ~${USER}/bin/awnetd.py -v -v -v -v" - $USER
	    fi
	    echo "."
            ;;

        stop)
	    echo -n "Stopping $DESC: awnetd"
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
