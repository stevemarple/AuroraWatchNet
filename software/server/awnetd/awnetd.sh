#!/bin/sh

USER="pi"

get_pid() {
    su -c "screen -list" - $USER | grep awnetd | cut -d. -f1
}


start_stop_server() {
    pid=`get_pid`
    case "$1" in
        start)
	    if [ -n "$pid" ]; then
		echo "awnetd is already running"
	    else
		su -c "screen -d -m -S awnetd ~pi/bin/awnetd.py -v -v -v -v" - $USER
		echo "awnetd started"
	    fi
            ;;

        stop)
	    if [ -n "$pid" ]; then
		kill $pid
		echo "awnetd stopped"
	    else
		echo "awnetd was not running"
	    fi
            ;;

        restart)
            start_stop_server stop
            start_stop_server start
            ;;

        status)
	    if [ -n "$pid" ]; then
		echo "awnetd is running ($pid)"
	    else
		echo "awnetd is stopped"
	    fi
            ;;

        zap)
	    if [ -n "$pid" ]; then
		echo "Stopping awnetd"
		kill -9 $pid
		su -c "screen -wipe" - $USER > /dev/null 2>&1
	    else
		echo "awnetd was not running"
	    fi
	    ;;
        *)
	    echo "Unknown action: $1"
	    return 1
            ;;
    esac
}

action="$1"

if [ -z "$action" ]; then
    echo "$0 start|stop|restart|status"
    exit 1
fi

start_stop_server "$action"
exit $?
