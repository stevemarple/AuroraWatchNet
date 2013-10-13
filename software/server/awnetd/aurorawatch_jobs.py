#
# This file defines custom jobs for AuroraWatchNet plotting.
from __future__ import print_function

import logging
import os.path
import pwd
import sys
import subprocess

import smtplib
from email.mime.text import MIMEText

if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import numpy as np


import auroraplot as ap
import auroraplot.dt64tools as dt64
import auroraplot.data


'''
Be very careful when running jobs to avoid them being run more often
than intended. Use the modification time on an empty file to mark the
last time it was run. If the disk is full the file can still be
touched to indicate successful completion (unlike the case of writing
the time to a file). If the file is missing create the empty file
first before running the job - this ensures that the file will be
present to update after successful completion.


'''

_ignore_timeout = False

def site_job(network, site, now, status_dir, test_mode, 
             ignore_timeout=False,
             mag_data=None, 
             temp_data=None, 
             voltage_data=None):

    global _ignore_timeout
    _ignore_timeout = ignore_timeout

    config = read_config(test_mode, network=network, site=site)
    # Non-alert jobs should go here...

    if not config.getboolean('alerts', 'enabled'):
        logging.debug('alerts disabled')
        return

    # Warn if battery nearly exhausted
    if voltage_data is not None and \
            'Battery voltage' in voltage_data.channels:
        low_batt = float(config.get('battery_voltage', 'low_voltage'))
        low_batt_timeout = np.timedelta64(24, 'h')
        low_batt_time = limit_exceeded(\
            voltage_data.extract(channels=['Battery voltage']),
            lower_limit=low_batt)

        if low_batt_time:
            mesg = 'Battery voltage low (<' + str(low_batt) + 'V) for ' \
                + network + '/' + site \
                + dt64.strftime(now, ' %Y-%m-%d %H:%M:%SUT')
            logging.debug(mesg)
            if config.has_option('battery_voltage', 'twitter_username'):
                username = config.get('battery_voltage', 'twitter_username')
                run_if_timeout_reached(send_tweet, low_batt_timeout, 
                                       low_batt_time, 
                                       now, status_dir,
                                       func_args=[username, mesg],
                                       name='battery_voltage_tweet')

            if config.has_option('battery_voltage', 'facebook_cmd'):
                fbcmd_opts = config.get('battery_voltage', 
                                        'facebook_cmd').split()
                run_if_timeout_reached(fbcmd, low_batt_timeout, 
                                       low_batt_time, 
                                       now, status_dir,
                                       func_args=[fbcmd_opts, mesg],
                                       name='battery_voltage_facebook')
            if config.has_option('battery_voltage', 'email_to'):
                subject = network + '/' + site + ' battery voltage low'
                mesg2 = mesg + \
                    '\n\nThis is an automatically generated message.\n' 
                run_if_timeout_reached(send_email, low_batt_timeout, 
                                       low_batt_time, 
                                       now, status_dir,
                                       func_args=[config, 
                                                  'battery_voltage',
                                                  subject, mesg2],
                                       name='battery_voltage_email')


def activity_job(mag_data_list, activity_data_list, now, status_dir, 
                 test_mode, ignore_timeout=False):
    global _ignore_timeout
    _ignore_timeout = ignore_timeout

    config = read_config(test_mode, combined=True)
    # Non-alert jobs should go here...
    
    if not config.getboolean('alerts', 'enabled'):
        logging.debug('alerts disabled')
        return
    

def touch(filename, amtime=None):
    basedir = os.path.dirname(filename)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    with open(filename, 'a'):
        os.utime(filename, amtime)


def limit_exceeded(data, lower_limit=None, upper_limit=None):
    if data is None:
        return None

    if lower_limit is not None:
        outside_limits = data.data < lower_limit
    else:
        outside_limits = np.zeros_like(data.data, dtype=bool)

    if upper_limit is not None:    
        outside_limits = np.logical_or(outside_limits,
                                       data.data > upper_limit)

    if np.any(outside_limits):
        # Find the latest time data was outside of the limits
        tidx = np.where(outside_limits)[1][-1]
        return data.sample_start_time[tidx]
    else:
        return None


def run_if_timeout_reached(func, timeout, detection_time, now, status_dir, 
                           func_args=[], func_kwargs={}, name=None):
    '''
    func: reference to function to call.

    timeout: numpy.timedelta64 defining the interval of the minimum
        time between alerts.
        
    detection_time: numpy.datetime64 defining the time the alert was detected.

    now: numpy.datetime64 defining the current time. If the system is
        being run in test mode on historical data this may be some
        time long ago. It must be honoured to enable test mode wto
        work correctly.

    '''

    if name is None:
        name=func.func_name

    # When considering the timeout use the time of the last data which
    # triggered the alert.
    rerun_time_s = dt64.dt64_to(detection_time - timeout, 's')
    
    filename = os.path.join(status_dir, name)
    if not os.path.exists(filename):
        # Create the file, with an old time
        logging.debug('timeout file missing: ' + filename)
        touch(filename, (0, 0))
    elif rerun_time_s < os.path.getmtime(filename) and not _ignore_timeout:
        # Too recent
        logging.debug('job ' + name + ' ran too recently, skipping')
        return
    
    # Call the function
    if func(*func_args, **func_kwargs):
        return # Want zero return status

    # Must have completed, touch the file with the 'current'
    # time. This must honour the now value to enable testing with
    # archive data.
    now_s = dt64.dt64_to(now, 's')
    touch(filename, (now_s, now_s))



def send_tweet(username, mesg):
    return os.system('echo "' + mesg + '" | tweepypost -u ' + username + ' -')

def send_email(config, section, subject, mesg):
    smtp_kwargs = {}
    smtp_options = ['host', 'port', 'local_hostname', 'timeout']
    for k in smtp_options:
        if config.has_option('smtp', k):
            smtp_kwargs[k] = config.get('smtp', k)

    logging.debug('Sending email to ' + config.get(section, 'email_to'))
    m = MIMEText(mesg)
    m['Subject'] = subject
    m['From'] = config.get(section, 'email_from')
    m['To'] = config.get(section, 'email_to')

    # Find section items which start with 'email_header' and add its
    # value to as a header line. Some email list servers support an
    # approval header.
    for i in config.items(section):
        if i[0].startswith('email_header'):
            a = i[1].split(':', 1)
            if len(a) > 1:
                m.add_header(a[0], a[1]) # name:value pair
            else:
                m.add_header(a[0], None) # name only
                
    logging.debug(m.as_string())

    s = smtplib.SMTP(**smtp_kwargs)
    s.sendmail(config.get(section, 'email_from'), 
               config.get(section, 'email_to').split(), m.as_string())
    s.quit()


def fbcmd(cmd_options, mesg):
    a = ['fbcmd']
    a.extend(cmd_options)
    a.append(mesg)
    return subprocess.call(a)



            
def read_config(test_mode, combined=False, network=None, site=None):
    config = SafeConfigParser()

    # Set some sensible defaults
    config.add_section('alerts')
    config.set('alerts', 'enabled', 'false')

    config.add_section('email')
    # config.set('server', 'localhost')
    

    path = [os.getenv('HOME'), '.' + __name__]
    if test_mode:
        path = os.path.join(os.getenv('HOME'), '.' + __name__, 'test')
    else:
        path = os.path.join(os.getenv('HOME'), '.' + __name__)
        
    if combined:
        # Data combined from multiple sites
        config_files = [os.path.join(path, 'common.ini'),
                        os.path.join(path, 'combined.ini')]
    else:
        # Data from a single site
        config.add_section('battery_voltage')
        config.set('battery_voltage', 'low_voltage', '2.35')

        config_files = [os.path.join(path, 'common.ini'),
                        os.path.join(path, network.lower() + '_' 
                                     + site.lower() + '.ini')]

    logging.debug('Config files: ' + ', '.join(config_files))
    files_read = config.read(config_files)
    logging.debug('Config files read: ' + ', '.join(files_read))
    return config
