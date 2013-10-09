#
# This file defines custom jobs for AuroraWatchNet plotting.
from __future__ import print_function

import os.path

import numpy as np

import auroraplot as ap
import auroraplot.dt64tools as dt64
import auroraplot.data


'''
Be very careful when running jobs to avoid them being run more often
than intended. Use the modification time on an empty file to mark the
last time it was run. If the disk is full the file can still be touch
to indicate successful completion (unlike the case of writing the time
to a file). If the file is missing create the empty file first before
running the job - the ensures that the file will be present to update
after successful completion.


'''

def site_job(network, site, now, summary_dir,
             mag_data=None, 
             temp_data=None, 
             voltage_data=None, 
             test_mode=False, 
             verbose=False):

    if voltage_data is not None and \
            'Battery voltage' in voltage_data.channels:
        lowbatt = 2.2
        # Warn if battery nearly exhausted
        check_limits(voltage_data.extract(channels=['Battery voltage']),
                     [lowbatt, None], 
                     print, np.timedelta64(12, 'h'),
                     now, summary_dir, 
                     func_args=['Low Battery (<' + str(lowbatt) + 'V)'], 
                     func_kwargs={},
                     name='battery_voltage')


def activity_job(mag_data_list, activity_data_list, test_mode, verbose, 
                 summary_dir):
    pass


def touch(filename, amtime=None):
    basedir = os.path.dirname(filename)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    with open(filename, 'a'):
        os.utime(filename, None)


def check_limits(data, limits, func, timeout, now, summary_dir, 
                 func_args=[], func_kwargs={}, name=None):
    if data is None:
        return
    # Find latest value which is outside of limits
    if limits[0] is not None and np.isfinite(limits[0]):
        outside_limits = data.data < limits[0]
    else:
        outside_limits = np.zeros_like(data.data, dtype=bool)

    if limits[1] is not None and np.isfinite(limits[1]):
        outside_limits = np.logical_or(outside_limits,
                                       data.data > limits[1])
    
    if np.any(outside_limits):
        # Find the latest time data was outside of the limits
        tidx = np.where(outside_limits)[1][-1]
        t = data.sample_start_time[tidx]
        run_if_timeout_reached(func, timeout, t, now, summary_dir,
                               func_args=func_args, 
                               func_kwargs=func_kwargs, 
                               name=name)
        


def run_if_timeout_reached(func, timeout, detection_time, now, summary_dir, 
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
    force_jobs = False
    force_jobs = True

    if name is None:
        name=func.func_name

    # When considering the timeout use the time of the last data which
    # triggered the alert.
    rerun_time_s = dt64.dt64_to(detection_time - timeout, 's')
    
    filename = os.path.join(summary_dir, name)
    if not os.path.exists(filename):
        # Create the file, with an old time
        touch(filename, (0, 0))
    elif rerun_time_s < os.path.getmtime(filename) and not force_jobs:
        # Too recent
        return
    
    # Call the function
    r = func(*func_args, **func_kwargs)

    # Must have completed, touch the file with the 'current'
    # time. This must honour the now value to enable testing with
    # archive data.
    now_s = dt64.dt64_to(now, 's')
    touch(filename, (now_s, now_s))
    return r


