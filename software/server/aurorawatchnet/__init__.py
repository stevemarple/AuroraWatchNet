import datetime
import grp
import logging
import os
import pwd
import re
import socket
import sys
import time

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

logger = logging.getLogger(__name__)


def read_config_file(filename):
    """Read config file."""
    logger.info('Reading config file ' + filename)

    config = SafeConfigParser()
    
    config.add_section('daemon')
    # The configuration file is the same for the original
    # AuroraWatchNet magnetometer system (Calunium microcontroller,
    # Raspberry Pi or other data logger) or the Raspberry Pi
    # magnetometer system (sensors connected directly to Raspberry
    # Pi). These systems are supported by two different daemons,
    # awnetd and raspmagd.
    config.set('daemon', 'name', 'awnetd')

    config.set('daemon', 'user', 'pi')
    config.set('daemon', 'group', 'pi')
    config.set('daemon', 'connection', 'serial')
    config.set('daemon', 'close_after_write', 'false')
    config.set('daemon', 'sampling_interval', '5')
    config.set('daemon', 'oversampling', '5')
    config.set('daemon', 'sensor_temperature_oversampling', '1')

    config.add_section('controlsocket')
    # ord('A') = 65, ord('W') = 87 
    config.set('controlsocket', 'port', '6587')

    config.add_section('serial')
    config.set('serial', 'port', '/dev/ttyACM0')
    config.set('serial', 'baudrate', '9600')
    config.set('serial', 'blocksize', '12')
    config.set('serial', 'setup', '')
    
    # For ethernet
    config.add_section('ethernet')
    config.set('ethernet', 'local_port', '6588')
    config.set('ethernet', 'local_ip', '')

    config.add_section('firmware')
    config.set('firmware', 'path', '/tmp/firmware')
    
    config.add_section('upload')
    # User must add appropriate values

    # Monitor for the existence of a file to indicate possible adverse
    # data quality
    config.add_section('dataqualitymonitor')
    config.set('dataqualitymonitor', 'extension', '.bad')
    config.set('dataqualitymonitor', 'username', 'pi')
    config.set('dataqualitymonitor', 'group', 'dialout')

    if filename:
        config_files_read = config.read(filename)
        if filename not in config_files_read:
            raise UserWarning('Could not read ' + filename)
        logger.debug('Successfully read ' + ', '.join(config_files_read))

    return config


def get_rt_transfer_info(config):
    '''Read realtime transfer details.

    Return a list of hosts to transfer data to in real time. List
    items are dicts containing 'hostname', 'ip', 'port' and
    'key'. Each message is signed with the host's key.

    Messages, and daemon responses, are sent as UDP packets to each
    host on the list. Section names must start with
    'realtime_transfer'; for multiple hosts the preferred format is to
    use section names of the form '[realtime_transfer:a]',
    '[realtime_transfer:b]', etc with just one hostname, ip and port
    defined for each section.

    The previously supported method of transferring data to multiple
    hosts was to enable multiple hostname, ip and port items to be
    inserted into the '[realtime_transfer]' section, with item name
    having the a unique suffix appended.  Support for the older method
    has been retained for compatibility.

    Each section can contain an optional 'enabled' item to control if
    real-time data is transferred to the host(s). Only if present and
    set to a false value is data not transferred.

    '''

    sections = config.sections()
    r = []
    for sec in [s for s in sections if s.startswith('realtime_transfer')]:
        if not config.has_option(sec, 'enabled') \
                or config.getboolean(sec, 'enabled'):
            for i in config.items(sec):
                mo = re.match('^remote_host(.*)$', i[0])
                if mo:
                    suf = mo.group(1) # suffix
                    hmac_key = config.get(sec, 'remote_key' + suf).decode('hex')
                    # Hostnames may resolve to multiple IP addresses, add all
                    try:
                        ip_list = socket.gethostbyname_ex(i[1])[2]
                    except:
                        logger.error('Could not resolve %s for real-time transfer, ignoring', i[1])
                        ip_list = []
                    for ip in ip_list:
                        r.append({'hostname': i[1],
                                  'ip': ip,
                                  'port': int(config.get(sec, 'remote_port' 
                                                         + suf)),
                                  'key': hmac_key})
    return r


def parse_datetime(s, now=None):
    """Parse datetime relative to now.

    In test mode now may not be the current time."""
    if now is None:
        now = datetime.datetime.utcnow()
    
    today = now.replace(hour=0,minute=0,second=0,microsecond=0)

    if s.startswith('overmorrow'):
        return (today + datetime.timedelta(days=2)
                + parse_timedelta(' '.join(s.split()[1:])))
    elif s.startswith('tomorrow'):
        return (today + datetime.timedelta(days=1)
                + parse_timedelta(' '.join(s.split()[1:])))
    elif s.startswith('now'):
        return now + parse_timedelta(' '.join(s.split()[1:]))
    elif s.startswith('today'):
        return today + parse_timedelta(' '.join(s.split()[1:]))
    elif s.startswith('yesterday'):
        return (today - datetime.timedelta(days=1) 
                + parse_timedelta(' '.join(s.split()[1:])))
    else:
        return datetime.datetime.strptime(s, '%Y-%m-%d')
    
def parse_timedelta(s):
    r = datetime.timedelta(seconds=0)
    value_next = True
    values = []
    units = []
    for w in s.split():
        m = re.match('^([+-]?[0-9]+)?(s|m|h|D|W)?$', w)
        if m is None:
            raise ValueError('unknown value/unit (%s)' % w)
        v, u = m.groups()
        if v is not None and u is not None:
            # Value and unit
            if not value_next:
                raise ValueError('unit expected but found %s' % repr(w))
            values.append(v)
            units.append(u)
        elif v is None and u is not None:
            # unit only
            if value_next:
                raise ValueError('value expected but found %s' % repr(w))
            units.append(u)
            value_next = True
        elif v is not None and u is None:
            # value only
            if not value_next:
                raise ValueError('unit expected but found %s' % repr(w))
            values.append(v)
            value_next = False

    if not value_next:
        raise ValueError('Last value missing unit: %s' % repr(s))

    units_to_datetimes = {
        's': datetime.timedelta(seconds=1),
        'm': datetime.timedelta(minutes=1),
        'h': datetime.timedelta(hours=1),
        'D': datetime.timedelta(days=1),
        'W': datetime.timedelta(weeks=1),
        }

    for n in range(len(values)):
        r += int(values[n]) * units_to_datetimes[units[n]]
    return r


def drop_root_privileges(username='nobody', group=None):
    if os.getuid() != 0:
        # Not root
        return

    # Get the UID and GID
    pwnam = pwd.getpwnam(username)

    # Remove group privileges
    os.setgroups([])

    # Set to new GID (whilst still have root privileges)
    if group is None:
        # No group specified, use user's default group
        os.setgid(pwnam.pw_gid)
    else:
        grnam = grp.getgrnam(group)
        os.setgid(grnam.gr_gid)

    # Change to new UID
    os.setuid(pwnam.pw_uid)

    # Set umask
    old_umask = os.umask(0o22)


def safe_eval(s):
    '''Like eval but prevent access to builtins and locals.

    Certain safe builtins are permitted, including True and False.
    This function cannot be guaranteed safe with untrusted input.'''
    return eval(s, {'__builtins__': {'True': True,
                                     'False': False}}, {})


def get_file_for_time(t, file_obj, fstr, mode='a+b', buffering=0, 
                      extension=None, header=None):
    '''
    t: seconds since unix epoch
    '''
    tmp_name = time.strftime(fstr, time.gmtime(t))
    if extension is not None:
        tmp_name += extension

    if file_obj is not None:
        if file_obj.closed:
            file_obj = None
        elif file_obj.name != tmp_name:
            # Filename has changed
            file_obj.close()
            file_obj = None
        
    if file_obj is None:
        # File wasn't open or filename changed
        p = os.path.dirname(tmp_name)
        if not os.path.isdir(p):
            os.makedirs(p)

        file_obj = open(tmp_name, mode, buffering)
        if header is not None and os.fstat(file_obj.fileno()).st_size == 0:
            # file_obj.tell() == 0:
            file_obj.write(header)

    return file_obj
