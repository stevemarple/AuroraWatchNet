# This file defines custom jobs for AuroraWatchNet plotting.

'''
This module defines custom jobs for AuroraWatchNet plotting. It can be
used to send emails, tweets or Facebook posts in response to important
events.

The events which can cause actions are:
    * geomagnetic activity
    * low battery
    * missing data
    
Each event can trigger one or more jobs to run. These jobs include
sending emails or social media messages. Some events make sense only
for a specific site, and are only supported by the site_job()
function.

The behaviour of this module can be conveniently modified by
configparser .ini files. In the absence of any files no jobs are
run. The .ini files are stored in the directory ~/.aurorawatch_jobs. A
common.ini file can be used to define commonly used settings (such as
SMTP server settings) and is used for the site_job() and
activity_job() functions. Settings common to all sites (but not
activity_job() can be stored in the all_sites.ini file, whilst
site-specific settings can be stored in a site config file, named
<project>_<site>.ini where <project> is the site's project name in
lower case and <site> is the site name, also in lower case. Settings
specific to activity_job() should be placed in combined.ini. Ini files
for site_job() are read in the order common.ini, all_sites.ini and
finally <project>_<site>.ini. In case of conflict the last read
setting wins. For activity_job the ini files are read in the order
common.ini, combined.ini.

Alerts can be disabled by setting the "enabled" item in the
"[all_alerts]" section to be false. It is suggested not to override
this in the site configuration files (except to disable alerts)
otherwise the global "kill-switch" behaviour is lost.

All jobs have a timeout setting to prevent them being called
repeatedly. The job is only re-run if the timeout period has
passed. Auroral activity jobs are re-run if the alert level has
increased; corresponding jobs for the lower levels are then given the
same timeout period.

Timeouts are implemented by setting the modification time on an empty
file. This approach ensures that the timeouts can be updated even if
the disk is full. The files are automatically created if missing; if a
missing file cannot be created the job will not run. Timeouts can be
cleared by the clear_timeouts() function which sets the modfication
time to the unix epoch.

This module supports a test mode, whose purpose is to allow the jobs
to be tested on historic data. As it is not desirable to alert normal
users of historical events a separate set of .ini files are used. They
have the same names as previously but are located
~/.aurorawatch_jobs/test directory.

'''
from __future__ import print_function

import logging
import os.path
import pwd
import re
import sys
import subprocess
import traceback

import smtplib
from email.mime.text import MIMEText

try:
    from configparser import SafeConfigParser as ConfigParser
except ImportError:
    # SafeConfigParser removed from later versions
    from configparser import ConfigParser

import numpy as np


import auroraplot as ap
import auroraplot.dt64tools as dt64
import auroraplot.data

logger = logging.getLogger(__name__)


_ignore_timeout = False

def site_job(project, site, now, status_dir, test_mode, 
             ignore_timeout=False,
             mag_data=None, 
             act_data=None,
             temp_data=None, 
             voltage_data=None):

    global _ignore_timeout
    _ignore_timeout = ignore_timeout

    config = read_config(test_mode, project=project, site=site)
    # Non-alert jobs should go here...

    if not config.getboolean('all_alerts', 'enabled'):
        logger.debug('alerts disabled')
        return
    
    if act_data is not None:
        aurora_alert(act_data, False, now, status_dir, test_mode, 
                     ignore_timeout, config)
        
    warn_missing_data(mag_data, project, site, now, status_dir,
                      test_mode, config)

    # Warn if battery nearly exhausted
    if voltage_data is not None and \
            'Supply voltage' in voltage_data.channels:
        low_batt = float(config.get('supply_voltage', 'low_voltage'))
        low_batt_timeout = np.timedelta64(24, 'h')
        low_batt_time = limit_exceeded(\
            voltage_data.extract(channels=['Supply voltage']),
            lower_limit=low_batt)

        if low_batt_time:
            logger.debug('Low supply for ' + project + '/' + site)
            if config.has_option('supply_voltage', 'twitter_username'):
                username = config.get('supply_voltage', 'twitter_username')
                twitter_mesg = expand_string(config.get('supply_voltage', 
                                                      'twitter_message'),
                                     project, site, now, test_mode, 
                                     low_voltage=low_batt)

                run_if_timeout_reached(send_tweet, low_batt_timeout,
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[username, twitter_mesg],
                                       name='supply_voltage_tweet')
                
                logger.debug('Low battery message: ' + twitter_mesg)


            if config.has_option('supply_voltage', 'facebook_cmd'):
                fbcmd_opts = config.get('supply_voltage', 
                                        'facebook_cmd').split()
                facebook_mesg = expand_string(config.get('supply_voltage', 
                                                         'facebook_message'),
                                              project, site, now, test_mode, 
                                              low_voltage=low_batt)
                run_if_timeout_reached(fbcmd, low_batt_timeout, 
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[fbcmd_opts, facebook_mesg],
                                       name='supply_voltage_facebook')

            # Email. Leave to the send_email() function to determine
            # if it is configured since there are many possible
            # settings in the config file.  Run each email job
            # separately in case of failure to send.
            for ejob in get_email_jobs(config, 'supply_voltage'):
                run_if_timeout_reached(send_email, low_batt_timeout, 
                                       now, status_dir,
                                       detection_time=low_batt_time, 
                                       func_args=[config, 'supply_voltage',
                                                  ejob, project, site, 
                                                  now, test_mode],
                                       func_kwargs={'low_voltage': low_batt},
                                       name='supply_voltage_' + ejob)
                    

def activity_job(combined_activity, activity_data_list, now, status_dir, 
                 test_mode, ignore_timeout=False):
    global _ignore_timeout
    _ignore_timeout = ignore_timeout

    config = read_config(test_mode, combined=True)
    # Non-alert jobs should go here...
    
    if not config.getboolean('all_alerts', 'enabled'):
        logger.debug('alerts disabled')
        return

    if combined_activity is not None:
        aurora_alert(combined_activity, True, now, status_dir, test_mode,
                     ignore_timeout, config)


def aurora_alert(activity, combined, now, status_dir, test_mode, 
                 ignore_timeout, config):
    assert activity.thresholds.size == 4, \
        'Incorrect number of activity thresholds'
    assert activity.sample_start_time[-1] <= now \
        and activity.sample_end_time[-1] >= now, \
        'Last activity sample for wrong time'
    assert np.all(np.logical_or(activity.data >= 0, np.isnan(activity.data))), \
        'Activity data must be >= 0'
    
    if np.isnan(activity.data[0,-1]):
        return
    n = np.where(activity.data[0,-1] >= activity.thresholds)[0][-1]


    logger.debug('Activity level for ' + activity.project + '/' 
                 + activity.site + ': ' + str(n))
    
    
    section_name = 'aurora_alert_' + str(n) 
    if n == 0:
        # No significant activity
        return
    elif not config.has_section(section_name):
        logger.debug('No [' + section_name + '] section found')
        return

    nowstr = dt64.strftime(now, '%Y-%m-%d %H:%M:%SUT')
    tweet_timeout = facebook_timeout = email_timeout = np.timedelta64(12, 'h')

    # Compute filename to use for timeout, and the names of any other
    # files which must be updated.
    job_base_name = section_name
    if not combined:
        job_base_name += '_' + activity.project.lower() + '_' \
            + activity.site.lower()
    tweet_files = []
    facebook_files = []
    email_files = []
    for i in range(1, n+1):
        tweet_files.append(job_base_name + '_tweet')
        facebook_files.append(job_base_name + '_facebook')
        email_files.append(job_base_name + '_') # Must append the ejob later
        

    # Tweet
    if config.has_option(section_name, 'twitter_username'):
        twitter_username = config.get(section_name, 'twitter_username')
        twitter_mesg = expand_string(config.get(section_name, 
                                                'twitter_message'),
                                     activity.project, activity.site, now, 
                                     test_mode)
        run_if_timeout_reached(send_tweet, tweet_timeout, 
                               now, status_dir,
                               func_args=[twitter_username, twitter_mesg],
                               name=tweet_files[-1], 
                               also_update=tweet_files[:-1])
    else:
        logger.debug('Sending tweet not configured')

    # Post to facebook
    if config.has_option(section_name, 'facebook_cmd'):
        facebook_mesg = expand_string(config.get(section_name, 
                                                 'facebook_message'),
                                      activity.project, activity.site, now,
                                      test_mode)
        fbcmd_opts = config.get(section_name, 'facebook_cmd').split()
        run_if_timeout_reached(fbcmd, facebook_timeout, now, status_dir,
                               func_args=[fbcmd_opts, facebook_mesg],
                               name=facebook_files[-1],
                               also_update=facebook_files[:-1])
    else:
        logger.debug('Facebook posting not configured')


    # Email. Leave to the send_email() function to determine if it is
    # configured since there are many possible settings in the config
    # file.
    for ejob in get_email_jobs(config, section_name):
        run_if_timeout_reached(send_email, email_timeout, 
                               now, status_dir,
                               func_args=[config, section_name, ejob, 
                                          activity.project, activity.site, 
                                          now, test_mode],
                               name=email_files[-1] + ejob,
                               also_update=map(lambda x: x + ejob, 
                                               email_files[:-1]))

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


def warn_missing_data(data, project, site, now, status_dir, test_mode, config):

    section_name = 'missing_data'
    missing_interval = np.timedelta64(1, 'h')
    timeout = np.timedelta64(1, 'D')
    
    if not missing_interval:
        return

    if data is None:
        t = None
    else:
        # Find last non-nan value
        idx = np.nonzero(np.any(np.logical_not(np.isnan(data.data)), 
                                 axis=0))[0]
        if len(idx):
            t = data.sample_start_time[idx[-1]]
        else:
            t = None
    
    if t is None:
        # Data is entirely missing. Was expecting 24 hours of data,
        # with a nominal end time of the end of the current hour.
        t = dt64.ceil(now, np.timedelta64(1, 'h')) - np.timedelta64(1, 'D')


    tstr = dt64.strftime(t, '%Y-%m-%d %H:%M:%SUT')
    if t < now - missing_interval:
        # Data is missing
        logger.info(project + '/' + site + ' missing data')
        if config.has_option(section_name, 'twitter_username'):
            username = config.get(section_name, 'twitter_username')
            mesg = expand_string(config.get(section_name, 'twitter_message'),
                                 project, site, now, test_mode, 
                                 missing_start_time=tstr,
                                 missing_interval=str(missing_interval))   
            run_if_timeout_reached(send_tweet, timeout,
                                   now, status_dir,
                                   func_args=[username, mesg],
                                   name=section_name + '_tweet')

        if config.has_option(section_name, 'facebook_cmd'):
            fbcmd_opts = config.get(section_name, 
                                    'facebook_cmd').split()
            mesg = expand_string(config.get(section_name, 'facebook_message'),
                                 project, site, now, test_mode, 
                                 missing_start_time=tstr,
                                 missing_interval=str(missing_interval)) 
            run_if_timeout_reached(fbcmd, timeout, 
                                   now, status_dir,
                                   func_args=[fbcmd_opts, facebook_mesg],
                                   name=section_name + '_facebook')



        # Email. Leave to the send_email() function to determine if it
        # is configured since there are many possible settings in the
        # config file.  Run each email job separately in case of
        # failure to send.
        func_kwargs = {'missing_start_time': tstr,
                       'missing_interval': str(missing_interval)}
        for ejob in get_email_jobs(config, section_name):
            run_if_timeout_reached(send_email, timeout, 
                                   now, status_dir,
                                   func_args=[config, section_name,
                                              ejob, project, site, 
                                              now, test_mode],
                                   func_kwargs=func_kwargs,
                                   name=section_name + '_' + ejob)

            
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

    logger.debug('Processing job ' + name)
    # When considering the timeout use the time of the last data which
    # triggered the alert.
    rerun_time_s = dt64.dt64_to(detection_time - timeout, 's')
    
    filename = os.path.join(status_dir, name)
    if not os.path.exists(filename):
        # Create the file, with an old time
        logger.debug('timeout file missing: ' + filename)
        touch_file(filename, (0, 0))
    elif rerun_time_s < os.path.getmtime(filename) and not _ignore_timeout:
        # Too recent
        logger.debug('job ' + name + ' ran too recently, skipping')
        return
    
    try:
        # Call the function
        if func(*func_args, **func_kwargs):
            logger.warning('Job ' + name + ' returned non-zero exit status')
            return # Want zero return status
    except Exception as e:
        logger.error('Job ' + name + ' failed with exception: ' + str(e))
        logger.error(traceback.format_exc())
        return

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


def get_email_jobs(config, section):
    '''
Return a list of the prefixes from the given section which are
associated with sending emails.
'''
    
    email_jobs  = {}
    for i in config.items(section):
        mo = re.match('(email\d*)_to', i[0])
        if mo:
            email_jobs[mo.group(1)] = True

    return sorted(email_jobs.keys())


# def send_email(config, section, ejob, subject, mesg):
def send_email(config, section, ejob, project, site, now, test_mode, **kwargs):

    logger.debug('Sending email to ' + config.get(section, ejob + '_to'))

    smtp_kwargs = {}
    smtp_options = ['host', 'port', 'local_hostname', 'timeout']
    for k in smtp_options:
        if config.has_option('smtp', k):
            smtp_kwargs[k] = config.get('smtp', k)


    if config.has_option(section, ejob + '_message'):
        mesg = config.get(section, ejob + '_message')
    elif config.has_option(section, 'email_message'):
        mesg = config.get(section, 'email_message')
    else:
        # mesg = 'Email message not set in config file'
        raise Exception('Email message not set in config file for job [' + 
                        section + '] ' + ejob)

    m = MIMEText(expand_string(mesg, project, site, now, test_mode, **kwargs))

    if config.has_option(section, ejob + '_subject'):
        subject = config.get(section, ejob + '_subject')
    elif config.has_option(section, 'email_subject'):
        subject = config.get(section, 'email_subject')
    else:
        # subject = 'Subject not set in config file'
        raise Exception('Subject not set in config file for job [' + 
                        section + '] ' + ejob)

    m['Subject'] = expand_string(subject, project, site, now, test_mode, 
                                 **kwargs)
    m['From'] = config.get(section, ejob + '_from')
    m['To'] = config.get(section, ejob + '_to')

    # Find section items which start with 'email_header' (or similar)
    # and add its value to as a header line. Some email list servers
    # support an approval header.
    for i in config.items(section):
        if i[0].startswith(ejob + '_header'):
            a = i[1].split(':', 1)
            if len(a) > 1:
                m.add_header(a[0], a[1]) # name:value pair
            else:
                m.add_header(a[0], None) # name only

    logger.debug(m.as_string())

    s = smtplib.SMTP(**smtp_kwargs)
    s.sendmail(config.get(section, ejob + '_from'), 
               config.get(section, ejob + '_to').split(), m.as_string())
    s.quit()
    return 0
    

def fbcmd(cmd_options, mesg):
    a = ['fbcmd']
    a.extend(cmd_options)
    a.append(mesg)
    return subprocess.call(a)

            
def read_config(test_mode, combined=False, project=None, site=None):
    config = ConfigParser()

    # Set some sensible defaults
    config.add_section('all_alerts')
    config.set('all_alerts', 'enabled', 'false')

    config.add_section('email')
    # config.set('server', 'localhost')
    

    if test_mode:
        path = os.path.join(os.path.expanduser('~'), '.' + __name__, 'test')
    else:
        path = os.path.join(os.path.expanduser('~'), '.' + __name__)
        
    if combined:
        # Data combined from multiple sites
        config.add_section('aurora_alert_0')
        config.set('aurora_alert_0', 'twitter_message', 
                   'No significant activity {datetime}')
        config.set('aurora_alert_0', 'facebook_message', 'No significant '  
                   + 'activity, aurora is unlikely to be seen {datetime}.')
        config.set('aurora_alert_0', 'email_subject', 
                   'No significant activity {datetime}')
        config.set('aurora_alert_0', 'email_message', 'No significant '  
                   + 'activity, aurora is unlikely to be seen {datetime}.')

        config.add_section('aurora_alert_1')
        config.set('aurora_alert_1', 'twitter_message', 
                   'Minor geomagnetic activity {datetime} #aurora')
        config.set('aurora_alert_1', 'facebook_message', 
                   'Minor geomagnetic activity {datetime} #aurora')
        config.set('aurora_alert_1', 'email_subject', 
                   'Minor geomagnetic activity {datetime}')
        config.set('aurora_alert_1', 'email_message', 
                   'Minor geomagnetic activity {datetime}')

        config.add_section('aurora_alert_2')
        config.set('aurora_alert_2', 'twitter_message', 
                   'Amber alert, possible aurora {datetime} #aurora')
        config.set('aurora_alert_2', 'facebook_message', 
                   'Amber alert, possible aurora {datetime} #aurora')
        config.set('aurora_alert_2', 'email_subject', 
                   'Amber alert {datetime}')
        config.set('aurora_alert_2', 'email_message', 
                   'Amber alert, possible aurora {datetime}')

        config.add_section('aurora_alert_3')
        config.set('aurora_alert_3', 'twitter_message', 
                   'Red alert, aurora likely {datetime} #aurora')
        config.set('aurora_alert_3', 'facebook_message', 
                   'Red alert, aurora likely {datetime} #aurora')
        config.set('aurora_alert_3', 'email_subject', 
                   'Red alert {datetime}')
        config.set('aurora_alert_3', 'email_message', 
                   'Red alert, aurora likely {datetime}')

        config_files = [os.path.join(path, 'common.ini'),
                        os.path.join(path, 'combined.ini')]
    else:
        # Data from a single site
        config.add_section('supply_voltage')
        config.set('supply_voltage', 'low_voltage', '2.35')
        # batt_low_mesg = 'Supply voltage low (< {low_voltage!s}V) for ' + 
        batt_low_mesg = 'Supply voltage low (< {low_voltage:.2f}V) for ' + \
            '{project}/{site} {datetime}.'
        config.set('supply_voltage', 'twitter_message', batt_low_mesg)
        config.set('supply_voltage', 'facebook_message', batt_low_mesg)
        config.set('supply_voltage', 'email_subject', 
                   '{project}/{site}: Supply low')
        config.set('supply_voltage', 'email_message', batt_low_mesg)

        # Single sites should only warn of disturbance, only issue
        # alerts for the combined data set where multiple sites are in
        # use.
        config.add_section('aurora_alert_0')
        config.set('aurora_alert_0', 'twitter_message', 
                   'No significant activity {datetime}')
        config.set('aurora_alert_0', 'facebook_message', 'No significant '  
                   + 'activity, aurora is unlikely to be seen {datetime}.')
        config.set('aurora_alert_0', 'email_subject', 
                   'No significant activity {datetime}')
        config.set('aurora_alert_0', 'email_message', 'No significant '  
                   + 'activity, aurora is unlikely to be seen {datetime}.')

        config.add_section('aurora_alert_1')
        config.set('aurora_alert_1', 'twitter_message', '{project}/{site} ' +
                   'detected minor geomagnetic activity {datetime}')
        config.set('aurora_alert_1', 'facebook_message', '{project}/{site} ' +
                   'detected minor geomagnetic activity {datetime}')
        config.set('aurora_alert_1', 'email_subject', '{project}/{site} ' + 
                   'detected minor geomagnetic activity {datetime}')
        config.set('aurora_alert_1', 'email_message', '{project}/{site} ' + 
                   'detected minor geomagnetic activity {datetime}')

        config.add_section('aurora_alert_2')
        config.set('aurora_alert_2', 'twitter_message', '{project}/{site} ' +
                   'detected large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_2', 'facebook_message', '{project}/{site} ' + 
                   'detected large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_2', 'email_subject', '{project}/{site} ' + 
                   'detected large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_2', 'email_message', '{project}/{site} ' +
                   'detected large geomagnetic disturbance {datetime}')

        config.add_section('aurora_alert_3')
        config.set('aurora_alert_3', 'twitter_message', '{project}/{site} ' +
                   'detected very large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_3', 'facebook_message', '{project}/{site} ' + 
                   'detected very large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_3', 'email_subject', '{project}/{site} ' + 
                   'detected very large geomagnetic disturbance {datetime}')
        config.set('aurora_alert_3', 'email_message', '{project}/{site} ' + 
                   'detected very large geomagnetic disturbance {datetime}')

        config.add_section('missing_data')
        # TODO: Add items for missing_interval and timeout
        config.set('missing_data', 'twitter_message', '{project}/{site} ' +
                   'missing data since {missing_start_time}.')
        config.set('missing_data', 'facebook_message', '{project}/{site} ' +
                   'missing data since {missing_start_time}.')
        config.set('missing_data', 'email_subject', 
                   '{project}/{site}: Missing data')
        config.set('missing_data', 'email_message', '{project}/{site} ' +
                   'missing data since {missing_start_time}.')

        config_files = [os.path.join(path, 'common.ini'),
                        os.path.join(path, 'all_sites.ini'),
                        os.path.join(path, project.lower() + '_' 
                                     + site.lower() + '.ini')]

    logger.debug('Config files: ' + ', '.join(config_files))
    files_read = config.read(config_files)
    logger.debug('Config files read: ' + ', '.join(files_read))
    return config


def expand_string(s, project, site, now, test_mode, **kwargs):
    d = kwargs.copy()
    d.update({'project': project or '',
              'site': site or '',
              'date': dt64.strftime(now, '%Y-%m-%d'),
              'datetime': dt64.strftime(now, '%Y-%m-%d %H:%M:%SUT'),
              'time': dt64.strftime(now, '%H:%M:%SUT'),
              'test_mode': ' (test mode) ' if test_mode else ''
              })
    
    return s.format(**d)
    

# def write_api_files_v0_1(mag_data):
#   pass
