#!/usr/bin/env python
import argparse    
import copy
import io
import logging
logger = logging.getLogger(__name__)

import os
import sys
import time
import traceback
import pyexiv2
# import Image

import numpy as np
import matplotlib as mpl

from numpy.f2py.auxfuncs import throw_error
from logging import exception
if os.environ.get('DISPLAY', '') == '':
    mpl.use('Agg')
import matplotlib.pyplot as plt

import auroraplot as ap
import auroraplot.dt64tools as dt64
import auroraplot.magdata 
import auroraplot.tools
import auroraplot.auroralactivity 
import auroraplot.datasets.aurorawatchnet
import auroraplot.datasets.samnet

# Set timezone appropriately to get intended np.datetime64 behaviour.
os.environ['TZ'] = 'UTC'
time.tzset()

mpl.rcParams['legend.fontsize'] = 'medium'


def parse_datetime(s):
    # Parse datetime relative to 'now' variable, which in test mode
    # may not be the current time.
    if s == 'tomorrow':
        return tomorrow
    elif s == 'now':
        return now
    elif s == 'today':
        return today
    elif s == 'yesterday':
        return yesterday
    else:
        return np.datetime64(s).astype('M8[us]')


def my_load_data(project, site, data_type, start_time, end_time, **kwargs):
    r = ap.load_data(project, site, data_type, start_time, end_time, **kwargs)
    if r is not None and args.test_mode:
        # Remove any data after 'now' to emulate the correct behaviour
        # when using historical data.
        r.data[:,r.sample_end_time > now] = np.nan
    return r


def mysavefig(fig, filename, exif_tags=None):
    global args
    path = os.path.dirname(filename)
    if not os.path.exists(path):
        os.makedirs(path)

    fig.axes[-1].set_xlabel('Time (UT)')

    # Override labelling format
    for ax in fig.axes:
        ax.grid(True)
        ax.xaxis.set_major_formatter(dt64.Datetime64Formatter(fmt='%H'))
        if np.diff(ax.get_xlim()).astype('m8[' + dt64.get_plot_units(ax.xaxis) \
                                             + ']') == np.timedelta64(24, 'h'):
            ax.xaxis.set_major_locator(\
                dt64.Datetime64Locator(interval=np.timedelta64(3, 'h'),
                                       maxticks=10))
            
        
    # TO DO: Update all site information with correct copyright,
    # license and attribution data. Temporarily set here as currently
    # all are CC4 BY-NC-SA.
    if exif_tags is None:
        exif_tags = {
            'Exif.Image.Copyright':  \
                'This work is licensed under the Creative Commons ' + \
                'Attribution-NonCommercial-ShareAlike 4.0 Unported ' + \
                'License. To view a copy of this license, visit ' + \
                'http://creativecommons.org/licenses/by-nc-sa/4.0/'
            }
        
    
    if exif_tags is None or len(exif_tags) == 0:
        # Can save directly to a file
        fig.savefig(buf, dpi=80)
    else:
        # Save the figure to a buffer which is used to create a
        # pyexiv2 object.
        image_format = filename[(filename.rindex('.') + 1):]
        buf = io.BytesIO()
        fig.savefig(buf, dpi=80, format=image_format)
        buf.seek(0)
        metadata = pyexiv2.ImageMetadata.from_buffer(buf.getvalue())
        metadata.read()
    
        # Add the metadata. pyexiv2 only supports a few tags
        for k in exif_tags:
            metadata[k] = exif_tags[k]
        metadata.write()

        f = open(filename, 'wb') # Open the file originally specified
        f.write(metadata.buffer) # Finally write to disk
        f.close()
        buf.close()

    logger.info('saved to ' + filename)
        
    # if not args.show:
    #     plt.close(fig) # Close to save memory

def has_data_of_type(project, site, data_type):
    return ap.projects.has_key(project) \
        and ap.projects[project].has_key(site) \
        and ap.projects[project][site]['data_types'].has_key(data_type)

def round_to(a, b, func=np.round):
    return func(a / b) * b

def activity_plot(mag_data, mag_qdc, filename, exif_tags, 
                  k_index_filename=None):
    global activity
    channel = mag_data.channels[0]
    pos = [0.15, 0.1, 0.775, 0.75]

    if mag_qdc is None:
        activity = None
        mag_data.plot(label=channel, color='black')
        fig = plt.gcf()
        ax2 = plt.gca()
    else:
        # assert np.all(mag_data.channels == mag_qdc.channels) \
        #     and len(mag_data.channels) == 1 \
        #     and len(mag_qdc.channels) == 1, \
        #     'Bad value for channels'
    
        channel = mag_data.channels[0]
        activity = ap.auroralactivity.AuroraWatchActivity(magdata=mag_data, 
                                                          magqdc=mag_qdc,
                                                          fit=None)

        # To get another axes the position must be different. It is made
        # the same position later.
        pos2 = copy.copy(pos)
        pos2[0] += 0.1 
        fig = plt.figure(facecolor='w')
        ax = plt.axes(pos)

        activity.plot(axes=ax, units_prefix='n', 
                      label='Activity (' + channel + ')')
        ax2 = plt.axes(pos2)

        # Set Y limit to be 1.5 times highest threshold. Units are
        # nanotesla since that was set when plotting.
        ax.set_ylim(0, activity.thresholds[-1] * 1.5 * 1e9)
    
        mag_data.plot(label=channel, color='black',axes=ax2)

        # Align the QDC to regular intervals between start and end times
        qdc_cadence = np.timedelta64(1, 'm')
        num = ((mag_data.end_time - mag_data.start_time)/ qdc_cadence) + 1
        qdc_sample_times = np.linspace(mag_data.start_time.astype('M8[m]'),
                                       mag_data.end_time.astype('M8[m]'),
                                       num)
        qdc_aligned = mag_qdc.align(qdc_sample_times)
        qdc_aligned.plot(label=channel + ' QDC', color='cyan', axes=ax2)

        ax.set_axis_bgcolor('w')
        ax.axison = False
        ax2.set_title(activity.make_title())

    ax2.set_axis_bgcolor('none')
    ax2.set_position(pos)

    min_ylim_range = 400
    ax2_ylim = ax2.get_ylim()
    if np.diff(ax2_ylim) < min_ylim_range:
        ax2.set_ylim(round_to(np.mean(ax2_ylim), 50) 
                     + min_ylim_range * np.array([-0.5, 0.5]))
    fig.set_figwidth(6.4)
    fig.set_figheight(4.8)

    mysavefig(fig, filename, exif_tags)

    r = [activity]
    if k_index_filename is not None:
        md_filt = mag_data
        if ap.has_site_info(mag_data.project, mag_data.site, 
                            'k_index_filter'):
            kfilt = ap.get_site_info(mag_data.project, mag_data.site, 
                                      'k_index_filter')
            if kfilt is not None:
                md_filt = kfilt(mag_data)

        k_index = ap.auroralactivity.KIndex(magdata=md_filt, magqdc=mag_qdc)
        # Fix the start/end times to the data, not the 3h K index samples
        k_index.start_time = md_filt.start_time
        k_index.end_time = md_filt.end_time

        k_index.plot()
        fig = plt.gcf()
        fig.set_figwidth(6.4)
        fig.set_figheight(4.8)
        fig.subplots_adjust(bottom=0.1, top=0.85, 
                            left=0.15, right=0.925)
        mysavefig(fig, k_index_filename, exif_tags)

        r.append(k_index)

    return r
 
def make_aurorawatch_plot(project, site, st, et, rolling, exif_tags):
    '''
    Load data and make the AuroraWatch activity plot. Plots always
    cover 24 hours, but may begin at midnight for day plots, or at any
    other hour for rolling plots. This function uses the previous 72
    hours to help fit the quiet-day curve.

    project: name of project
    
    site: name of site
    
    st: start time. For day plots this is the start of the day. For
        rolling plots this is the start of the rolling 24 hour period.
    
    et: end time. For day plots this is the start of the following
        day. For rolling plots it is the end of the 24 hour period.
    
    rolling: flag to indicate if rolling plot should also be made. It
        is not otherwise possible to identify rolling plots which
        start at midnight.

    '''

    # global mag_fstr
    global args

    # Export to global names for debugging
    global mag_data
    global mag_qdc
    global activity

    day = np.timedelta64(24, 'h')

    archive, archive_details = ap.get_archive_info(project, site, 'MagData')
    channel = archive_details['channels'][0]

    # Load the data to plot. For rolling plots load upto midnight so
    # that both the rolling plot and the current day plot can be
    # generated efficiently.
    mag_data = my_load_data(project, site, 'MagData', st, dt64.ceil(et, day),
                            channels=[channel])

    if mag_data is None or \
            not np.any(np.logical_not(np.isnan(mag_data.data))): 
        # not .np.any(etc) eliminates empty array or array of just nans
        logger.info('No magnetic field data')
        return

    # Load up some data from previous days to and apply a
    # least-squares fit to remove baseline drifts. Data from the
    # current day is not used. This ensures that results do not change
    # over the current day when new data becomes available.
    qdc_fit_interval = args.qdc_fit_interval * day
    fit_et = dt64.ceil(st, day) # Could be doing a rolling plot
    fit_st = fit_et - qdc_fit_interval
    fit_data = my_load_data(project, site, 'MagData', fit_st, fit_et, 
                            channels=[channel])

    # Load a QDC. For the 4th or later in the month load the previous
    # month, otherwise go back two months. This gives a few days for
    # data to be transferred, and QDCs to be made and checked.
    qdc_t = dt64.get_start_of_previous_month(st)
    if dt64.get_day_of_month(st) < 4:
        qdc_t = dt64.get_start_of_previous_month(qdc_t)
    mag_qdc = ap.magdata.load_qdc(project, site, qdc_t, 
                                  channels=[channel], tries=6)
    if mag_qdc is None:
        logger.info('No QDC')
    elif fit_data is None:
        # Cannot fit, so assume no errors in QDC
        errors = [0.0]
    else:
        try:
            # Fit the QDC to the previous data
            qdc_aligned, errors, fi = mag_qdc.align(\
                fit_data, 
                fit=ap.data.Data.minimise_sign_error_fit,
                plot_fit=args.plot_fit,
                full_output=True)
        except Exception as e:
            logger.warn('Could not fit QDC')
            logger.info(str(e))
            errors = [0.0]
        else:
            # Fitted ok, plot if necessary
            if args.plot_fit:
                fig = plt.gcf()
                fig.set_figwidth(6.4)
                fig.set_figheight(4.8)
                fig.subplots_adjust(bottom=0.1, top=0.85, 
                                    left=0.15, right=0.925)
                fit_fstr = mag_fstr[:(mag_fstr.rindex('.'))] + '_fit.png'
                mysavefig(fig, dt64.strftime(dt64.ceil(st, day), fit_fstr),
                          exif_tags)

    # Adjust the quiet day curve with the error obtained by fitting to
    # previous days.
    if mag_qdc is None:
        mag_qdc_adj = None
    else:
        mag_qdc_adj = copy.deepcopy(mag_qdc)
        mag_qdc_adj.data -= errors[0]

    # Ensure data gaps are marked as such in the plots. Straight lines
    # across large gaps look bad!
    mag_data = mag_data.mark_missing_data(cadence=2*mag_data.nominal_cadence)
   
    # Do day plot. Trim start time for occasions when making a day
    # plot simultaneously with a rolling plot.
    st2 = dt64.ceil(st, day)
    md_day = mag_data.extract(start_time=st2)
    act_ki = activity_plot(md_day, mag_qdc_adj,
                           dt64.strftime(st2, mag_fstr), exif_tags,
                           k_index_filename=dt64.strftime(st2, k_fstr))
    r = [md_day]
    r.extend(act_ki)

    if rolling:
        # Trim end time
        md_rolling = mag_data.extract(end_time=et)
        act_ki_rolling = activity_plot(md_rolling, mag_qdc_adj,
                                       rolling_magdata_filename, exif_tags,
                                       k_index_filename=rolling_k_filename)
        r.append(md_rolling)
        r.extend(act_ki_rolling)
    return r


def make_temperature_plot(temperature_data, filename, exif_tags):
    temperature_data.plot()
    fig = plt.gcf()
    ax = plt.gca()
    fig.set_figwidth(6.4)
    fig.set_figheight(3)
    fig.subplots_adjust(bottom=0.175, top=0.75, 
                        left=0.15, right=0.925)
    leg = plt.legend()
    leg.get_frame().set_alpha(0.5)
    mysavefig(fig, filename, exif_tags)


def make_voltage_plot(voltage_data, filename, exif_tags):
    voltage_data.plot()
    fig = plt.gcf()
    ax = plt.gca()
    # ax.set_ylim([1.5, 3.5])
    fig.set_figwidth(6.4)
    fig.set_figheight(3)
    fig.subplots_adjust(bottom=0.175, top=0.75, 
                        left=0.15, right=0.925)
    mysavefig(fig, filename, exif_tags)


def make_stack_plot(mdl, filename, exif_tags):
    ap.magdata.stack_plot(mdl, offset=100e-9)
    fig = plt.gcf()
    ax = plt.gca()
    ax.grid(True)
    fig.subplots_adjust(left=0.15, right=0.925)

    # Shorten AuroraWatchNet
    tll = ax.yaxis.get_ticklabels() # tick label list
    labels = [ tl.get_text() for tl in tll]
    labels = map(lambda x: x.replace('AURORAWATCHNET', 'AWN'), labels)
    ax.yaxis.set_ticklabels(labels)
    mysavefig(fig, filename, exif_tags)

def combined_activity_plot(act, filename, exif_tags):
    '''
    act: list of AuroraWatchActivity objects
    filename: filename for plot
    exif_tags: dict of tags to add to image
    returns: None
    '''
    # Calculate activity as proportion of amber alert
    act_data = np.concatenate(map(lambda d: d.data / d.thresholds[2], act))
    act_data[np.isnan(act_data)] = 0
    
    if act_data.shape[0] == 2:
        # When only two sites use lowest activity values
        data = np.min(act_data, axis=0)
    else:
        data = np.median(act_data, axis=0)
        
    activity_data = copy.deepcopy(act[0])
    activity_data.project = 'AuroraWatch'
    activity_data.site = 'UK'
    # Set specific thresholds, and convert data from proportion of
    # amber threshold
    activity_data.data = np.array([data]) * 100e-9
    activity_data.thresholds = np.array([0.0, 50e-9, 100e-9, 200e-9])
    activity_data.units = 'T'

    activity_data.plot(units_prefix='n')
    fig = plt.gcf()
    ax = plt.gca()
    ax.set_ylabel('Activity (nT)')
    ax.set_title('AuroraWatch UK\nAverage geomagnetic activity\n' +
                 dt64.fmt_dt64_range(activity_data.start_time,
                                     activity_data.end_time))
    ax.grid(True)
    # Set Y limit to be 1.5 times highest threshold. Units are
    # nanotesla since that was set when plotting.
    ax.set_ylim(0, activity.thresholds[-1] * 1.5 * 1e9)
    fig.set_figwidth(6.4)
    fig.set_figheight(4.8)
    fig.subplots_adjust(bottom=0.1, top=0.85, 
                        left=0.15, right=0.925)
    mysavefig(fig, filename, exif_tags)
    return activity_data
    
def make_links(link_dir, link_data):
    for link in link_data:
        link_name = os.path.join(link_dir, link['name'])

        # Make the target a relative path
        target = os.path.relpath(dt64.strftime(link['date'], link['fstr']),
                                 os.path.dirname(link_name))
        if os.path.islink(link_name) and \
                os.readlink(link_name) == target:
            # Exists and is correct
            logger.debug('link exists and is correct: ' + link_name +
                          ' -> ' + target)
            continue
        if os.path.lexists(link_name):
            logger.debug('link exists but is incorrect: ' + link_name)
            os.unlink(link_name)
        logger.debug('creating link ' + link_name + ' -> ' + target)
        os.symlink(target, link_name)


# TODO: put in a common location and merge with aurorawatch_jobs.touch_file
def touch_file(filename, amtime=None):
    basedir = os.path.dirname(filename)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    with open(filename, 'a'):
        os.utime(filename, amtime)


def clear_timeouts(status_dir):
    if os.path.exists(status_dir):
        for filename in os.listdir(status_dir):
            # Set times back to 1970
            touch_file(os.path.join(status_dir, filename), (0, 0))


cc4_by_nc_sa = 'This work is licensed under the Creative Commons ' + \
    'Attribution-NonCommercial-ShareAlike 4.0 Unported License. ' + \
    'To view a copy of this license, visit ' + \
    'http://creativecommons.org/licenses/by-nc-sa/4.0/'
        
# ==========================================================================

# Parse command line options
parser = argparse.ArgumentParser(description\
                                     ='Plot AuroraWatch magnetometer data.')
parser.add_argument('-s', '--start-time',
                    help='Start time for archive plot mode',
                    metavar='DATETIME')
parser.add_argument('-e', '--end-time',
                    help='End time for archive plot mode',
                    metavar='DATETIME')
parser.add_argument('--now',
                    help='Set current time for test mode',
                    metavar='DATETIME')
parser.add_argument('--log-level', 
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='warning',
                    help='Control how much details is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')
parser.add_argument('-m', '--make-links', 
                    action='store_true',
                    help='Make symbolic links')
parser.add_argument('--rolling', 
                    action='store_true',
                    help='Make rolling plots for today (live mode)')
parser.add_argument('--test-mode',
                    action='store_true',
                    help='Test mode for plots and jobs')
parser.add_argument('--clear-timeouts',
                    action='store_true',
                    help='Mark jobs as not having run for a very long time')
parser.add_argument('--ignore-timeout',
                    action='store_true',
                    help='Ignore timeout when running jobs')
parser.add_argument('--sites', 
                    required=True,
                    help='Whitespace-separated list of sites (prefixed with project)',
                    metavar='"PROJECT1/SITE1 PROJECT2/SITE2 ..."')
parser.add_argument('--plot-fit', 
                    action='store_true',
                    help='Plot and save QDC fit')
parser.add_argument('--qdc-fit-interval',
                    type=int,
                    default=3,
                    help='Number of days for fitting QDC',
                    metavar='DAYS')
parser.add_argument('--run-jobs',
                    action='store_true',
                    help='Run jobs')
parser.add_argument('--show', 
                    action='store_true',
                    help='Show plots for final day')
parser.add_argument('--stack-plot',
                    action='store_true',
                    help='Generate stack plot(s)')
parser.add_argument('--summary-dir', 
                    default='/tmp',
                    help='Base directory for summary plots',
                    metavar='PATH')

args = parser.parse_args()
logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                    format=args.log_format)
    
# Use a consistent value for current time, process any --now option
# first.
if args.now:
    now = parse_datetime(args.now)
else:
    now = np.datetime64('now', 'us')

day = np.timedelta64(24, 'h')
today = dt64.floor(now, day)
yesterday = today - day
tomorrow = today + day

# This can be used in os.path.join() to include the test directory
# when needed.
if args.test_mode:
    test_mode_str = 'test'
else:
    test_mode_str = ''

if args.rolling:
    if args.start_time or args.end_time:
        raise Exception('Cannot set start or end time for rolling plots')
    end_time = dt64.ceil(now, np.timedelta64(1, 'h'))
    start_time = end_time - day
else:
    if args.start_time is None:
        start_time = today
    else:
        start_time = parse_datetime(args.start_time)

    if args.end_time is None:
        end_time = start_time + day
    else:
        end_time = parse_datetime(args.end_time)


if args.run_jobs:
    import aurorawatch_jobs
    # aurorawatch_jobs.init(args.test_mode, args.ignore_timeout)
else:
    aurorawatch_jobs = None


if args.clear_timeouts:
    clear_timeouts(os.path.join(args.summary_dir, test_mode_str, 
                                'job_status'))

# Get names of all projects and sites to be processed. Dictionary used
# to avoid duplicates.
project_site = {}
for s in args.sites.upper().split():
    n_s = s.split('/')
    if len(n_s) == 1:
        # Only project given, use all sites
        for k in ap.projects[n_s[0]].keys():
            project_site[n_s[0] + '/' + k] = (n_s[0], k)

    elif len(n_s) == 2:
        # Project and site given
        project_site[s] = tuple(n_s)
    else:
        raise Exception('bad value for project/site (' + project_site)



t1 = start_time
while t1 < end_time:
    plt.close('all')

    t2 = t1 + day
    t1_eod = dt64.ceil(t1, day) # t1 end of day
    t2_eod = dt64.ceil(t2, day) # t2 end of day

    # List of magdata objects for this day
    mdl_day = []
    act_day = []
    mdl_rolling = []
    act_rolling = []

    # Get copyright and attribution data for all sites. License had
    # better be CC4-BY-NC-SA for all since we are combining them.
    copyright_list = []
    attribution_list = []

    for project_uc, site_uc in project_site.values():
        project_lc = project_uc.lower()
        site_lc = site_uc.lower()

        if not ap.projects.has_key(project_uc):
            try:
                __import__('auroraplot.datasets.' + project_lc)
                logger.debug('imported auroraplot.datasets.' + project_lc)
            except:
                pass

        site_start_time = ap.get_site_info(project_uc, site_uc, 
                                           info='start_time')
        site_end_time = ap.get_site_info(project_uc, site_uc, 
                                         info='end_time')
        if site_start_time and t2 <= site_start_time:
            next
        if site_end_time and t1 >= site_end_time:
            next

        
        copyright_ = ap.get_site_info(project_uc, site_uc, 'copyright')
        attribution = ap.get_site_info(project_uc, site_uc, 'attribution')
        
        exif_tags = {'Exif.Image.Copyright': \
                         ' '.join(['Copyright: ' + copyright_,
                                    'License: ' + \
                                        ap.get_site_info(project_uc, 
                                                         site_uc, 
                                                         'license'),
                                    'Attribution: ' + attribution])}

        summary_dir = args.summary_dir
        site_summary_dir = os.path.join(summary_dir, test_mode_str,
                                        project_lc, site_lc)
        site_status_dir = os.path.join(site_summary_dir, 'job_status')

        mag_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                site_lc + '_%Y%m%d.png')
        rolling_magdata_filename = os.path.join(site_summary_dir, 
                                                'rolling.png')

        stackplot_fstr = os.path.join(summary_dir, test_mode_str,
                                      'stackplots', '%Y', '%m', '%Y%m%d.png')
        rolling_stackplot_filename = os.path.join(summary_dir, test_mode_str,
                                                  'stackplots', 'rolling.png')

        actplot_fstr = os.path.join(summary_dir, test_mode_str, 
                                    'activity_plots', 
                                    '%Y', '%m', '%Y%m%d.png')
        rolling_activity_filename = os.path.join(summary_dir, test_mode_str,
                                                 'activity_plots',
                                                 'rolling.png')

        temp_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                 site_lc + '_temp_%Y%m%d.png')
        rolling_tempdata_filename = os.path.join(site_summary_dir, 
                                                 'rolling_temp.png')
        voltage_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                    site_lc + '_voltage_%Y%m%d.png')
        rolling_voltdata_filename = os.path.join(site_summary_dir, 
                                                 'rolling_volt.png')

        k_fstr = os.path.join(site_summary_dir, '%Y', '%m', 
                              site_lc + '_k_%Y%m%d.png')
        rolling_k_filename = os.path.join(site_summary_dir,
                                          'rolling_k.png')

        if args.clear_timeouts and t1 == start_time:
            clear_timeouts(site_status_dir)

        md = None
        if has_data_of_type(project_uc, site_uc, 'MagData'):
            try:
                md = make_aurorawatch_plot(project_uc, site_uc, t1, t2, 
                                           args.rolling, exif_tags)
                # Store mag_data objects for daily and rolling
                # stack plots.
                if md is not None:
                    mdl_day.append(md[0])
                    act_day.append(md[1])
                    copyright_list.append(copyright_)
                    attribution_list.append(attribution)
                    if args.rolling:
                        mdl_rolling.append(md[3])
                        act_rolling.append(md[4])

            except Exception as e:
                logger.error(traceback.format_exc())

        temp_data = None
        if has_data_of_type(project_uc, site_uc, 'TemperatureData'):
            temp_data = my_load_data(project_uc, site_uc, 'TemperatureData', 
                                     t1, t2_eod)
            if temp_data is not None:
                temp_data.set_cadence(np.timedelta64(10, 'm'), 
                                      inplace=True)
                if args.rolling:
                    # Rolling plot
                    make_temperature_plot(temp_data.extract(end_time=t2),
                                          rolling_tempdata_filename, 
                                          exif_tags)

                # Make day plot. Trim data from start because when
                # --rolling option is given it can include data from
                # the previous day.
                make_temperature_plot(temp_data.extract(start_time=t1_eod),
                                      dt64.strftime(t1_eod, temp_fstr),
                                      exif_tags)

        voltage_data = None
        if has_data_of_type(project_uc, site_uc, 'VoltageData'):
            voltage_data = my_load_data(project_uc, site_uc, 'VoltageData', 
                                        t1, t2_eod)
            if voltage_data is not None:
                voltage_data.set_cadence(np.timedelta64(10, 'm'), 
                                         inplace=True)
                if args.rolling:
                    # Rolling plot
                    make_voltage_plot(voltage_data.extract(end_time=t2),
                                      rolling_voltdata_filename,
                                      exif_tags)

                # Make day plot. Trim data from start because when
                # --rolling option is given it can include data from
                # the previous day.
                make_voltage_plot(voltage_data.extract(start_time=t1_eod),
                                  dt64.strftime(t1_eod, voltage_fstr),
                                  exif_tags)
        
        if args.rolling and args.run_jobs:
            # Jobs are only run for rolling (live) mode.
            try:
                logger.info('Running site job for ' + project_uc + '/' \
                                 + site_uc)
                aurorawatch_jobs.site_job(project=project_uc,
                                          site=site_uc,
                                          now=now,
                                          status_dir=site_status_dir,
                                          test_mode=args.test_mode,
                                          ignore_timeout=args.ignore_timeout,
                                          mag_data=mag_data,
                                          act_data=None if md is None else md[4],
                                          temp_data=temp_data,
                                          voltage_data=voltage_data)
                                       
            except Exception as e:
                logger.error('Could not run job for ' + project_uc + '/' +
                              site_uc + ': ' + str(e))
                logger.error(traceback.format_exc())
                
                    
        
    if args.stack_plot and len(mdl_day):
        site_ca = [] # site copyright/attribution details
        for n in range(len(mdl_day)):
            site_ca.append(mdl_day[n].project + '/' + mdl_day[n].site + 
                           ' data: ' +
                           '    Copyright: ' + copyright_list[n] +
                           '    Attribution: ' + attribution_list[n] + 
                           '    ')
            
        exif_tags2 = {'Exif.Image.Copyright': \
                          ' '.join(site_ca) + '    License: ' + cc4_by_nc_sa}
        make_stack_plot(mdl_day, dt64.strftime(mdl_day[0].start_time, 
                                               stackplot_fstr),
                        exif_tags2)

        combined_activity_plot(act_day, dt64.strftime(act_day[0].start_time, 
                                                      actplot_fstr), 
                               exif_tags2)
        if args.rolling:
            make_stack_plot(mdl_rolling, rolling_stackplot_filename, 
                            exif_tags2)
            combined_activity = \
                combined_activity_plot(act_rolling, rolling_activity_filename,
                                       exif_tags2)

            if args.run_jobs:
                try:
                    logger.info('Running activity job')
                    status_dir = os.path.join(summary_dir, test_mode_str, 
                                              'job_status')
                    aurorawatch_jobs.activity_job(combined_activity=\
                                                      combined_activity,
                                                  activity_data_list=\
                                                      act_rolling,
                                                  now=now,
                                                  status_dir=status_dir,
                                                  test_mode=args.test_mode,
                                                  ignore_timeout=\
                                                      args.ignore_timeout,)
                except Exception as e:
                    logger.error('Could not run activity job: ' + str(e))
                    raise
            
    t1 = t2
    # End of time loop


if args.make_links:
    logger.debug('making links')
    # Makes site links for each site listed
    for project_uc, site_uc in project_site.values():
        site_lc = site_uc.lower()
        site_summary_dir = os.path.join(summary_dir, test_mode_str, 
                                        project_uc.lower(), site_lc)

        mag_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                site_lc + '_%Y%m%d.png')
        temp_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                 site_lc + '_temp_%Y%m%d.png')
        voltage_fstr = os.path.join(site_summary_dir, '%Y', '%m',
                                    site_lc + '_voltage_%Y%m%d.png')
        k_fstr = os.path.join(site_summary_dir, '%Y', '%m', 
                              site_lc + '_k_%Y%m%d.png')
        link_data = [{'name': 'yesterday.png', 
                      'date': yesterday,
                      'fstr': mag_fstr}, 
                     {'name': 'yesterday_temp.png', 
                      'date': yesterday,
                      'fstr': temp_fstr}, 
                     {'name': 'yesterday_volt.png', 
                      'date': yesterday,
                      'fstr': voltage_fstr},               
                     {'name': 'yesterday_k.png', 
                      'date': yesterday,
                      'fstr': k_fstr},               
                     {'name': 'today.png', 
                      'date': today,
                      'fstr': mag_fstr}, 
                     {'name': 'today_temp.png', 
                      'date': today,
                      'fstr': temp_fstr}, 
                     {'name': 'today_volt.png', 
                      'date': today,
                      'fstr': voltage_fstr},
                     {'name': 'today_k.png', 
                      'date': today,
                      'fstr': k_fstr},               
                     ]
        make_links(site_summary_dir, link_data)
 
    # Stack plots and combined activity links use a different base
    # directories
    make_links(os.path.join(summary_dir, test_mode_str, 'stackplots'),
               [{'name': 'yesterday.png', 
                 'date': yesterday,
                 'fstr': stackplot_fstr},               
                {'name': 'today.png', 
                 'date': today,
                 'fstr': stackplot_fstr}])
    make_links(os.path.join(summary_dir, test_mode_str, 'activity_plots'),
               [{'name': 'yesterday.png', 
                 'date': yesterday,
                 'fstr': actplot_fstr},               
                {'name': 'today.png', 
                 'date': today,
                 'fstr': actplot_fstr}])


if args.show:    
    plt.show()
