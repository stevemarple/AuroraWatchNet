#!/usr/bin/env python
import logging
logger = logging.getLogger(__name__)

import argparse    

import copy
import io
import os
import sys
import time
import traceback
import pyexiv2

import numpy as np
from numpy.f2py.auxfuncs import throw_error
import matplotlib as mpl

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
import auroraplot.datasets.dtu
import auroraplot.datasets.uit

# Set timezone appropriately to get intended np.datetime64 behaviour.
os.environ['TZ'] = 'UTC'
try:
    time.tzset()
except Exception as e:
    # Reminder that windows systems can't use tzset
    logging.warning('Could not set timezone')

mpl.rcParams['figure.facecolor'] = 'w'
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


def date_generator():
    t1 = start_time
    while t1 < end_time:
        t2 = t1 + day
        yield t1, t2, False
        t1 = t2

    if args.rolling:
        # Rolling ought to produce current day too
        if t1 != dt64.floor(now, day):
            t1 = dt64.floor(now, day)
            t2 = t1 + day
            yield t1, t2, False
        t2 = dt64.ceil(now, np.timedelta64(1, 'h'))
        t1 = t2 - day
        yield t1, t2, True

def my_load_data(project, site, data_type, start_time, end_time, **kwargs):
    if data_type not in ap.projects[project][site]['data_types']:
        return None

    r = ap.load_data(project, site, data_type, start_time, end_time, **kwargs)
    if r is not None and args.test_mode:
        # Remove any data after 'now' to emulate the correct behaviour
        # when using historical data.
        r.data[:,r.sample_end_time > now] = np.nan
    return r


load_data = ap.load_data
def load_mag_data(project, site, start_time, end_time, **kwargs):
    if 'MagData' not in ap.projects[project][site]['data_types']:
        return None

    # Load data day by day so that a memoize function can be used to
    # cache daily values
    mdl = []
    t1 = start_time
    while t1 < end_time:
        t2 = t1 + day
        md = load_data(project, site, 'MagData', t1, t2, **kwargs)
        if md is not None:
            # Ensure data gaps are marked as such in the plots. Straight lines
            # across large gaps look bad!
            mdl.append(md.mark_missing_data(
                    cadence=2*md.nominal_cadence))
        t1 = t2

    if len(mdl) == 0:
        return None

    r = ap.concatenate(mdl)
    r.start_time = start_time
    r.end_time = end_time
    if args.test_mode:
        # Remove any data after 'now' to emulate the correct behaviour
        # when using historical data.
        r.data[:,r.sample_end_time > now] = np.nan
    return r


def compute_mag_qdc_t(st):
    '''Compute QDC time. 

    For the 4th or later in the month load the previous
    month, otherwise go back two months. This gives a few days for
    data to be transferred and QDCs to be made and checked.'''
    qdc_t = dt64.get_start_of_previous_month(st)
    if dt64.get_day_of_month(st) < 4:
        qdc_t = dt64.get_start_of_previous_month(qdc_t)
    return qdc_t


def fit_qdc(mag_qdc, fit_data, mag_data, cadence=np.timedelta64(1,'m')):
    '''Fit QDC to data.
    
    mag_qdc: QDC to be fitted.
    fit_data: previous interval to which QDC should be fitted.
    mag_data: the magnetometer data of interest. 
    cadence: cadence of return value

    Fits QDC data by first fitting (DC shift) to fit_data. Then
    interpolates to produce a expected QDC values at given cadence.
    '''
    num = ((mag_data.end_time - mag_data.start_time)/ cadence) + 1
    # qdc_sample_times = np.linspace(fit_data.start_time.astype('M8[m]'),
    #                                fit_data.end_time.astype('M8[m]'),
    #                                num)
    #qdc_sample_times = (mag_data.start_time + 
    #                    (np.arange(num) * qdc_cadence))
    qdc_aligned = None
    errors = [0.0] * len(mag_data.channels)
    if mag_qdc is not None and fit_data is not None:
        try:
            # Fit to previous days to find adjustment
            qdc_aligned, errors, fi = \
                mag_qdc.align(fit_data,
                              fit=ap.data.Data.minimise_sign_error_fit,
                              plot_fit=args.plot_fit,
                              full_output=True)

            # Apply same error adjustment to the QDC    
            mag_qdc.data = (mag_qdc.data.T - errors).T
            return qdc_aligned, errors, fi
        except Exception as e:
            logger.error(traceback.format_exc())
    return None, None, None


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
        
    if not args.show:
        plt.close('all') # Close to save memory

def has_data_of_type(project, site, data_type):
    return ap.projects.has_key(project) \
        and ap.projects[project].has_key(site) \
        and ap.projects[project][site]['data_types'].has_key(data_type)

def round_to(a, b, func=np.round):
    return func(a / b) * b

def activity_plot(mag_data, mag_qdc, filename, exif_tags, 
                  k_index_filename=None):
    channel = mag_data.channels[0]
    pos = [0.15, 0.1, 0.775, 0.75]

    if mag_qdc is None:
        activity = None
        mag_data.plot(label=channel, color='black')
        fig = plt.gcf()
        ax2 = plt.gca()
    else: 
        channel = mag_data.channels[0]
        activity = ap.auroralactivity.AuroraWatchActivity(magdata=mag_data, 
                                                          magqdc=mag_qdc,
                                                          fit=None)

        # To get another axes the position must be different. It is made
        # the same position later.
        pos2 = copy.copy(pos)
        pos2[0] += 0.1 
        fig = plt.figure()
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

    # min_ylim_range = 400
    min_ylim_range = activity.thresholds[-1] * 1.5 * 1e9
    ax2_ylim = ax2.get_ylim()
    if np.diff(ax2_ylim) < min_ylim_range:
        ax2.set_ylim(round_to(np.mean(ax2_ylim), 50) 
                     + min_ylim_range * np.array([-0.5, 0.5]))
    fig.set_figwidth(6.4)
    fig.set_figheight(4.8)

    mysavefig(fig, filename, exif_tags)
    return activity

def k_index_plot(mag_data, mag_qdc, filename, exif_tags):

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
    mysavefig(fig, filename, exif_tags)
 
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
parser.add_argument('--cache', 
                    nargs='?', # Option has optional value
                    type=int,
                    default=0, # No option provided
                    const=-1,  # Option provided but no value (-1=autocompute)
                    help='Cache loading of data',
                    metavar='DAYS_TO_CACHE')

parser.add_argument('-m', '--make-links', 
                    action='store_true',
                    help='Make symbolic links')
parser.add_argument('--qdc-tries',
                    default=6,
                    type=int,
                    help='Number of tries to load QDC',
                    metavar='NUM')
parser.add_argument('--qdc-fit-days',
                    default=3,
                    type=int,
                    help='Number of days used to fit QDC',
                    metavar='NUM')
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
parser.add_argument('project_site',
                    nargs='+',
                    metavar="PROJECT[/SITE]")
parser.add_argument('--summary-dir', 
                    default='/tmp',
                    help='Base directory for summary plots',
                    metavar='PATH')
parser.add_argument('--plot-fit', 
                    action='store_true',
                    help='Plot and save QDC fit')
parser.add_argument('--show', 
                    action='store_true',
                    help='Show plots for final day')
parser.add_argument('--stack-plot',
                    action='store_true',
                    help='Generate stack plot(s)')
parser.add_argument('--run-jobs',
                    action='store_true',
                    help='Run jobs')

args = parser.parse_args()
logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                    format=args.log_format)
    
# Use a consistent value for current time, process any --now option
# before other time-dependent options.
if args.now:
    now = parse_datetime(args.now)
else:
    now = np.datetime64('now', 'us')


day = np.timedelta64(24, 'h')
today = dt64.floor(now, day)
yesterday = today - day
tomorrow = today + day


if args.start_time is None:
    start_time = today
else:
    start_time = dt64.floor(parse_datetime(args.start_time), day)

if args.end_time is None:
    end_time = start_time + day
else:
    end_time = dt64.floor(parse_datetime(args.end_time), day)


aurorawatch_jobs = None
if args.run_jobs:
    try:
        import aurorawatch_jobs
    except ImportError as e:
        logger.error('Failed to import aurorawatch_jobs')
        logger.error(traceback.format_exc())
        args.run_jobs = False

if args.test_mode:
    summary_dir = os.path.join(args.summary_dir, test_mode_str)
else:
    summary_dir = args.summary_dir

if args.clear_timeouts:
    clear_timeouts(os.path.join(summary_dir, 'job_status'))


project_list, site_list = ap.parse_project_site_list(args.project_site)

if args.cache != 0:
    try: 
        import cachetools
        import auroraplot.utils
        
        if args.cache == -1:
            cache_size = ((1 + args.qdc_fit_days) * len(site_list)) + 1
        else:
            cache_size = args.cache

        logger.debug('Cache %d MagData items' % cache_size)
        load_data = ap.utils.CachedFunc(ap.load_data,
                                        cache_class=cachetools.LRUCache, 
                                        maxsize=cache_size)

    except ImportError:
        logger.error('Failed to configure cache')
        logger.error(traceback.format_exc())


# t1 = start_time
# while t1 < end_time:



# Iterate over the list of days to process. If rolling plots were
# specified the last item will be start/end times for the rolling
# plot.
for t1, t2, rolling in date_generator():
    t1_sod = dt64.floor(t1, day)
    plt.close('all')

    ### DEBUG: Phase these out
    t1_eod = dt64.ceil(t1, day) # t1 end of day
    t2_eod = dt64.ceil(t2, day) # t2 end of day

    


    # List of magdata objects for this 24 hour period
    mag_data_list = []
    activity_data_list = []

    # Get copyright and attribution data for all sites. Licenses had
    # better be compatible (or we have express permission) since we
    # are combining them.
    copyright_list = []
    attribution_list = []

    for site_num in range(len(site_list)):
        project_uc = project_list[site_num]
        project_lc = project_uc.lower()
        site_uc = site_list[site_num]
        site_lc = site_uc.lower()
        logger.debug('Processing %s/%s' % (project_uc, site_uc))

        # Ignore this 24 hour period if outside the site's listed
        # operational period
        site_start_time = ap.get_site_info(project_uc, site_uc, 
                                           info='start_time')
        site_end_time = ap.get_site_info(project_uc, site_uc, 
                                         info='end_time')
        if ((site_start_time and t2 <= site_start_time) or
            (site_end_time and t1 >= site_end_time)):
            continue
        
        copyright_ = ap.get_site_info(project_uc, site_uc, 'copyright')
        attribution = ap.get_site_info(project_uc, site_uc, 'attribution')
        
        exif_tags = {'Exif.Image.Copyright': \
                         ' '.join(['Copyright: ' + copyright_,
                                    'License: ' + \
                                        ap.get_site_info(project_uc, 
                                                         site_uc, 
                                                         'license'),
                                    'Attribution: ' + attribution])}

        site_summary_dir = os.path.join(summary_dir,
                                        project_lc, site_lc)
        site_status_dir = os.path.join(site_summary_dir, 'job_status')

        if rolling:
            # Rolling plots should have fixed (not time-dependent)
            # filenames
            mag_plot_filename = os.path.join(site_summary_dir, 'rolling.png')
            k_filename = os.path.join(site_summary_dir, 'rolling_k.png')
            temp_plot_filename = os.path.join(site_summary_dir, 
                                              'rolling_temp.png')
            volt_plot_filename = os.path.join(site_summary_dir, 
                                              'rolling_volt.png')

            stackplot_filename = os.path.join(summary_dir,
                                              'stackplots', 'rolling.png')
            activity_plot_filename = os.path.join(summary_dir, 
                                                  'activity_plots',
                                                  'rolling.png')

        else:
            mag_plot_filename = \
                dt64.strftime(t1, 
                              os.path.join(site_summary_dir, '%Y', '%m',
                                           site_lc + '_%Y%m%d.png'))
            qdc_fit_filename =  \
                dt64.strftime(t1, 
                              os.path.join(site_summary_dir, '%Y', '%m',
                                           site_lc + '_%Y%m%d_fit.png'))
            k_filename = \
                dt64.strftime(t1, 
                              os.path.join(site_summary_dir, '%Y', '%m', 
                                           site_lc + '_k_%Y%m%d.png'))

            stackplot_filename = \
                dt64.strftime(t1, 
                              os.path.join(summary_dir, 'stackplots', 
                                           '%Y', '%m', '%Y%m%d.png'))
                              
            activity_plot_filename = \
                dt64.strftime(t1, 
                              os.path.join(summary_dir, 'activity_plots', 
                                           '%Y', '%m', '%Y%m%d.png'))

            temp_plot_filename = \
                dt64.strftime(t1, 
                              os.path.join(site_summary_dir, '%Y', '%m',
                                           site_lc + '_temp_%Y%m%d.png'))

            volt_plot_filename = \
                dt64.strftime(t1, 
                              os.path.join(site_summary_dir, '%Y', '%m',
                                           site_lc + '_voltage_%Y%m%d.png'))


        

        if args.clear_timeouts and t1 == start_time:
            clear_timeouts(site_status_dir)


        # Load magnetometer data and QDC
        mag_data = None
        mag_qdc = None
        activity = None
        ### qdc_aligned = None
        try:
            mag_data = load_mag_data(project_uc, site_uc, t1, t2)
            logger.debug(mag_data)
            if mag_data is not None:
                # Store copyright and attribution. Used later in stackplots
                mag_data.copyright = copyright_
                mag_data.attribution = attribution

                mag_data_list.append(mag_data)
                mag_qdc = ap.magdata.load_qdc(project_uc, 
                                              site_uc, 
                                              compute_mag_qdc_t(t1), 
                                              tries=args.qdc_tries)
                if mag_qdc is not None:
                    # Try fitting QDC to previous 3 days of data
                    mag_data_prev = load_mag_data(project_uc, 
                                                  site_uc, 
                                                  t1_sod - (3*day), 
                                                  t1_sod)
                    if mag_data_prev is not None:
                        fitted_qdc, errors, fi \
                            = fit_qdc(mag_qdc, mag_data_prev, mag_data)

                        if args.plot_fit and not rolling:
                            fig = plt.gcf()
                            fig.set_figwidth(6.4)
                            fig.set_figheight(4.8)
                            fig.subplots_adjust(bottom=0.1, top=0.85, 
                                                left=0.15, right=0.925)
                            mysavefig(fig, qdc_fit_filename, exif_tags)
                     
                # Standard AuroraWatch UK activity plot
                activity = activity_plot(mag_data, mag_qdc, 
                                         mag_plot_filename,
                                         exif_tags)
                if activity is not None:
                    activity.copyright = copyright_
                    activity.attribution = attribution
                    activity_data_list.append(activity)

                # Local K-index plot
                k_index_plot(mag_data, mag_qdc, k_filename, exif_tags)
                             
        except Exception as e:
            logger.error(traceback.format_exc())


        temp_data = None
        try:
            if has_data_of_type(project_uc, site_uc, 'TemperatureData'):
                temp_data = my_load_data(project_uc, site_uc, 
                                         'TemperatureData', 
                                         t1, t2)
                if temp_data is not None:
                    temp_data.set_cadence(np.timedelta64(5, 'm'), 
                                          inplace=True)
                    make_temperature_plot(temp_data, temp_plot_filename,
                                          exif_tags)
        except Exception as e:
            logger.error(traceback.format_exc())


        voltage_data = None
        try:
            if has_data_of_type(project_uc, site_uc, 'VoltageData'):
                voltage_data = my_load_data(project_uc, site_uc, 
                                            'VoltageData', 
                                            t1, t2)
                if (voltage_data is not None 
                    and not np.all(np.isnan(voltage_data.data))):
                    voltage_data.set_cadence(np.timedelta64(5, 'm'), 
                                             inplace=True)
                    make_voltage_plot(voltage_data, volt_plot_filename,
                                      exif_tags)
        except Exception as e:
            logger.error(traceback.format_exc())

        
        if rolling and args.run_jobs:
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
                traceback.format_exc()
                
        
    if args.stack_plot and len(mag_data_list):
        try:
            site_ca = [] # site copyright/attribution details
            for m in mag_data_list:
                site_ca.append(m.project + '/' + m.site + 
                               ' data: ' +
                               ' Copyright: ' + m.copyright +
                               ' Attribution: ' + m.attribution)
            exif_tags2 = {'Exif.Image.Copyright': \
                              ' | '.join(site_ca) + ' | License: ' \
                              + cc4_by_nc_sa}
            make_stack_plot(mag_data_list, stackplot_filename, exif_tags2)
            combined_activity_plot(activity_data_list, activity_plot_filename,
                                   exif_tags2)

        except Exception as e:
            logger.error(traceback.format_exc())
        
    if rolling and args.run_jobs:
        try:
            logger.info('Running activity job')
            status_dir = os.path.join(summary_dir, 
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
            
    # End of time loop


if args.make_links:
    logger.debug('Making links')
    # Makes site links for each site listed
    for project_uc, site_uc in project_site.values():
        site_lc = site_uc.lower()
        site_summary_dir = os.path.join(summary_dir, 
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
    make_links(os.path.join(summary_dir, 'stackplots'),
               [{'name': 'yesterday.png', 
                 'date': yesterday,
                 'fstr': stackplot_fstr},               
                {'name': 'today.png', 
                 'date': today,
                 'fstr': stackplot_fstr}])
    make_links(os.path.join(summary_dir, 'activity_plots'),
               [{'name': 'yesterday.png', 
                 'date': yesterday,
                 'fstr': actplot_fstr},               
                {'name': 'today.png', 
                 'date': today,
                 'fstr': actplot_fstr}])


if args.show:    
    plt.show()
