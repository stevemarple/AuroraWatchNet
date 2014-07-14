import datetime
import logging

import sys
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
    config.set('daemon', 'user', 'nobody')
    config.set('daemon', 'group', 'nogroup')
    config.set('daemon', 'connection', 'serial')
    config.set('daemon', 'close_after_write', 'false')

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
    config.set('dataqualitymonitor', 'filename', 
               '/var/aurorawatchnet/data_quality_warning')
    config.set('dataqualitymonitor', 'extension', '.bad')

    if filename:
        config_files_read = config.read(filename)
        logger.debug('Successfully read ' + ', '.join(config_files_read))

    return config


def get_rt_tranfer_info(config):
    '''Read realtime transfer details.'''
    sec = 'realtime_transfer'
    r = []
    if config.has_section(sec):
        for i in config.items(sec):
            mo = re.match('^remote_host(.*)$', i[0])
            if mo:
                suf = mo.group(1) # suffix
                hmac_key = config.get(sec, 'remote_key' + suf).decode('hex')
                # Hostnames may resolve to multiple IP addresses, add all
                for ip in socket.gethostbyname_ex(i[1])[2]:
                    r.append({'hostname': i[1],
                              'ip': ip,
                              'port': int(config.get(sec, 'remote_port' 
                                                     + suf)),
                              'key': hmac_key})



def parse_datetime(s, now=None):
    """Parse datetime relative to now.

    In test mode now may not be the current time."""
    if now is None:
        now = datetime.datetime.utcnow()
    
    today = now.replace(hour=0,minute=0,second=0,microsecond=0)
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)

    if s == 'tomorrow':
        return tomorrow
    elif s == 'now':
        return now
    elif s == 'today':
        return today
    elif s == 'yesterday':
        return yesterday
    else:
        return datetime.datetime.strptime(s, '%Y-%m-%d')
    
