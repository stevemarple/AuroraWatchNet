# This file defines custom jobs for AuroraWatchNet plotting.

'''
This module defines custom jobs for AuroraWatchNet plotting. It can be
used to send emails, tweets or Facebook posts in response to importants
events.

The events which can cause actions are:
    * low battery
    * missing data (to be implemented)
    * geomagnetic activity (to be implemented)
    
Each event can trigger one or more jobs to run. These jobs include
sending emails or social media messages. Some events make sense only
for a specific site, and are only supported by the site_jobs
function. Detection of geomagnetic activity however makes most sense
when performed on the combined activity dataset, and thus is supported
by the activity_job function.

The behaviour of this module can be conveniently modified by
configparser .ini files. In the absence of any files no jobs are
run. The .ini files are stored in the $HOME/.aurorawatch_jobs
directory. A common.ini file can be used to define commonly used
settings (such as SMTP server settings) whilst site-specific settings
can be stored in the site config files, named <network>_<site>.ini
where <network> is the site's network name in lower case and <site> is
the site name, also in lower case.

Alerts can be disabled by setting the "enabled" item in the
"[all_alerts]" section to be false. It is suggested not to override
this in the site configuration files (except to disable alerts)
otherwise the global "kill-switch" behaviour is lost; instead comment
out the enabled line so the common.inin version is used.

This module supports a test mode, whose purpose is to allow the
plotting and jobs to be tested on historic data. As it is not
desirable to alert users of historical events a separate set of .ini
files are used. They have the same names as previously but are located
in the $HOME/.aurorawatch_jobs/test directory.

'''
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

    if not config.getboolean('all_alerts', 'enabled'):
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
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[username, mesg],
                                       name='battery_voltage_tweet')

            if config.has_option('battery_voltage', 'facebook_cmd'):
                fbcmd_opts = config.get('battery_voltage', 
                                        'facebook_cmd').split()
                run_if_timeout_reached(fbcmd, low_batt_timeout, 
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[fbcmd_opts, mesg],
                                       name='battery_voltage_facebook')
            if config.has_option('battery_voltage', 'email_to'):
                subject = network + '/' + site + ' battery voltage low'
                mesg2 = mesg + \
                    '\n\nThis is an automatically generated message.\n' 
                run_if_timeout_reached(send_email, low_batt_timeout, 
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[config, 
                                                  'battery_voltage',
                                                  subject, mesg2],
                                       name='battery_voltage_email')


def activity_job(combined_activity, activity_data_list, now, status_dir, 
                 test_mode, ignore_timeout=False):
    global _ignore_timeout
    _ignore_timeout = ignore_timeout

    config = read_config(test_mode, combined=True)
    # Non-alert jobs should go here...
    
    if not config.getboolean('all_alerts', 'enabled'):
        logging.debug('alerts disabled')
        return

    aurora_alert(combined_activity, now, status_dir, ignore_timeout, config)


def aurora_alert(activity, now, status_dir, ignore_timeout, config):
    levels = {0: {'desc': 'No significant activity.',
                  'explanation': 
                  'Aurora is unlikey to be seen from anywhere in the UK.',
                  'color': 'green'},
              1: {'desc': 'AuroraWatch UK detected minor geomagnetic activity.',
                  'explanation': 'Aurora is unlikely to be visible from the ' \
                      + 'UK except perhaps the extreme north of Scotland.',
                  'color': 'yellow'},
              2: {'desc': 'AuroraWatch UK amber alert: possible aurora.',
                  'explanation': 'Aurora is likely to be visible from ' \
                      + 'Scotland, northern England and Northern Ireland.',
                  'color': 'amber'},
              3: {'desc': 'AuroraWatch UK red alert: aurora likely.',
                  'explanation': 'It is likely that aurora will be visible ' \
                      + 'from everywhere in the UK.',
                  'color': 'red'},
              }
    
    assert activity.thresholds.size == len(levels), \
        'Incorrect number of activity thresholds'
    assert activity.sample_start_time[-1] <= now \
        and activity.sample_end_time[-1] >= now, \
        'Last activity sample for wrong time'
    assert np.all(activity.data >= 0), 'Activity data must be >= 0'
    n = np.where(activity.data[0,-1] >= activity.thresholds)[0][-1]


    logging.debug(activity.network + '/' + activity.site + ': ' + \
                      levels[n]['desc'])
    
    
    section_name = 'aurora_alert'
    if n == 0:
        # No significant activity
        return

    nowstr = dt64.strftime(now, '%Y-%m-%d %H:%M:%SUT')
    tweet_timeout = facebook_timeout = email_timeout = np.timedelta64(12, 'h')

    # Compute filename to use for timeout, and the names of any other
    # files which must be updated.
    tweet_files = []
    facebook_files = []
    email_files = []
    for i in range(1, n+1):
        tweet_files.append(section_name + '_tweet_' + levels[i]['color'])
        facebook_files.append(section_name + '_facebook_' + levels[i]['color'])
        email_files.append(section_name + '_email_' + levels[i]['color'])
        

    # Tweet
    if config.has_option(section_name, 'twitter_username'):
        twitter_username = config.get(section_name, 'twitter_username')
        twitter_mesg = ' '.join([levels[n]['desc'], nowstr])
        if n > 1 and len(twitter_mesg) < 130:
            # Ensure enough room with some spare for followers to RT, MT etc.
            twitter_mesg += ' #aurora'
        run_if_timeout_reached(send_tweet, tweet_timeout, 
                               now, status_dir,
                               func_args=[twitter_username, twitter_mesg],
                               name=tweet_files[-1], 
                               also_update=tweet_files[:-1])
    else:
        logging.debug('Sending tweet not configured')

    # Post to facebook
    if config.has_option(section_name, 'facebook_cmd'):
        facebook_mesg = ' '.join([levels[n]['desc'], levels[n]['explanation'], 
                                  'Alert issued', nowstr + '.', 
                                  'For more information regarding',
                                  'alert levels please see',
                                  'http://aurorawatch.lancs.ac.uk/alerts',
                                  '\n#aurora'])
        fbcmd_opts = config.get(section_name, 'facebook_cmd').split()
        run_if_timeout_reached(fbcmd, facebook_timeout, now, status_dir,
                               func_args=[fbcmd_opts, facebook_mesg],
                               name=facebook_files[-1],
                               also_update=facebook_files[:-1])
    else:
        logging.debug('Facebook posting not configured')


    # Email
    if config.has_option(section_name, 'email_to'):
        email_mesg = ' '.join([levels[n]['desc'], levels[n]['explanation'], 
                               nowstr, '\n\nThis is an automatically',
                               'generated message.'])

        subject = levels[n]['desc'][:-1] # Omit trailing period
        run_if_timeout_reached(send_email, email_timeout, 
                               now, status_dir,
                               func_args=[config, section_name,
                                          subject, email_mesg],
                               name=email_files[-1],
                               also_update=email_files[:-1])
    else:
        logging.debug('Sending email not configured')

    # TODO: some handling for email lists, where there are separate
    # lists for red and amber subscribers, and to include approved
    # headers in a more generic way.


def touch_file(filename, amtime=None):
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


def run_if_timeout_reached(func, timeout, now, status_dir, detection_time=None, 
                           func_args=[], func_kwargs={}, name=None,
                           also_update=[]):
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

    if detection_time is None:
        detection_time = now

    logging.debug('Processing job ' + name)
    # When considering the timeout use the time of the last data which
    # triggered the alert.
    rerun_time_s = dt64.dt64_to(detection_time - timeout, 's')
    
    filename = os.path.join(status_dir, name)
    if not os.path.exists(filename):
        # Create the file, with an old time
        logging.debug('timeout file missing: ' + filename)
        touch_file(filename, (0, 0))
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
    touch_file(filename, (now_s, now_s))

    # Update any other files
    for f in also_update:
        touch_file(os.path.join(status_dir, f), (now_s, now_s))


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
    config.add_section('all_alerts')
    config.set('all_alerts', 'enabled', 'false')

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
