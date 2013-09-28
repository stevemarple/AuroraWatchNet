#!/usr/bin/env python
import argparse    
import copy
import os
import sys
import time

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
import auroraplot.auroralactivity 
import auroraplot.datasets.aurorawatchnet
import auroraplot.datasets.samnet

# Set timezone appropriately to get intended np.datetime64 behaviour.
os.environ['TZ'] = 'UTC'
time.tzset()


def mysavefig(fig, filename):
    global args
    path = os.path.dirname(filename)
    if not os.path.exists(path):
        os.makedirs(path)
    fig.axes[-1].set_xlabel('Time (UT)')

    # Override labelling format
    for ax in fig.axes:
        ax.xaxis.set_major_formatter(dt64.Datetime64Formatter(fmt='%H'))

    fig.savefig(filename, dpi=80)
    if args.verbose:
        print('saved to ' + filename)
        
    if not args.show:
        plt.close(fig)

def has_data_of_type(network, site, data_type):
    return ap.networks.has_key(network) \
        and ap.networks[network].has_key(site) \
        and ap.networks[network][site]['data_types'].has_key(data_type)

def round_to(a, b, func=np.round):
    return func(a / b) * b

def activity_plot(mag_data, mag_qdc, filename):
    assert np.all(mag_data.channels == mag_qdc.channels) \
        and len(mag_data.channels) == 1 \
        and len(mag_qdc.channels) == 1, \
        'Bad value for channels'

    channel = mag_data.channels[0]
    activity = ap.auroralactivity.AuroraWatchActivity(magdata=mag_data, 
                                                      magqdc=mag_qdc,
                                                      lsq_fit=False)

    pos = [0.15, 0.1, 0.775, 0.75]

    # To get another axes the position must be different. It is made
    # the same position later.
    pos2 = copy.copy(pos)
    pos2[0] += 0.1 
    fig = plt.figure(facecolor='w')
    ax = plt.axes(pos)

    activity.plot(axes=ax, label='Activity (' + channel + ')')
    ax2 = plt.axes(pos2)

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

    ax2.set_axis_bgcolor('none')
    ax2.set_position(pos)
    ax2.set_title(activity.make_title())

    min_ylim_range = 800
    ax2_ylim = ax2.get_ylim()
    if np.diff(ax2_ylim) < min_ylim_range:
        ax2.set_ylim(round_to(np.mean(ax2_ylim), 50) 
                     + min_ylim_range * np.array([-0.5, 0.5]))

    fig.set_figwidth(6.4)
    fig.set_figheight(4.8)
    mysavefig(fig, filename)
        
def make_aurorawatch_plot(network, site, st, et, rolling):
    '''
    Load data and make the AuroraWatch activity plot. Plots always
    cover 24 hours, but may begin at midnight for day plots, or at any
    other hour for rolling plots. This function uses the previous 72
    hours to help fit the quiet-day curve.

    network: name of network
    
    site: name of site
    
    st: start time. For day plots this is the start of the day. For
        rolling plots this is the start of the rolling 24 hour period.
    
    et: end time. For day plots this is the start of the following
        day. For rolling plots it is the end of the 24 hour period.
    
    rolling: flag to indicate if rolling plot should also be made. It
        is not otherwise possible to idicentify rolling pltos which
        start at midnight.

    '''

    global mag_fstr

    # Debug
    global mag_data
    global mag_qdc
    global activity

    day = np.timedelta64(24, 'h')

    archive, archive_details = ap.get_archive_details(network, site, 'MagData')
    channel = archive_details['channels'][0]

    # Load the data to plot. For rolling plots load upto midnight so
    # that both the rolling plot and the current day plot can be
    # generated efficiently.
    mag_data = ap.load_data(network, site, 'MagData', st, dt64.ceil(et, day),
                            channels=[channel])
    if mag_data is None:
        if args.verbose:
            print('No magnetic field data')
        return

    # Load up some data from previous days to and apply a
    # least-squares fit to remove baseline drifts. Data from the
    # current day is not used. This ensures that results do not change
    # over the current day when new data becomes available.
    qdc_fit_interval = 3 * day
    fit_et = dt64.ceil(st, day) # Could be doing a rolling plot
    fit_st = fit_et - qdc_fit_interval
    fit_data = ap.load_data(network, site, 'MagData', fit_st, fit_et, 
                            channels=[channel])

    # Load the latest QDC that is available.
    mag_qdc = ap.magdata.load_qdc(network, site, et, 
                                  channels=[channel], tries=6)
    if mag_qdc is None:
        if args.verbose:
            print('No QDC')
        return

    if fit_data is None:
        # Cannot fit, so assume not errors in QDC
        errors = [0.0]
    else:
        # Fit the QDC to the previous data
        qdc_aligned, errors, fi = mag_qdc.align(fit_data, lsq_fit=True, 
                                                full_output=True)

    # Adjust the quiet day curve with the error obtained by fitting to
    # previous days.
    mag_qdc_adj = copy.deepcopy(mag_qdc)
    mag_qdc_adj.data -= errors[0]

    # Ensure data gaps are marked as such in the plots. Straight lines
    # across large gaps look bad!
    mag_data = mag_data.mark_missing_data(cadence=2*mag_data.nominal_cadence)

   
    # Do day plot. Trim start time for occasions when making a day
    # plot simultaneously with a rolling plot.
    st2 = dt64.ceil(st, day)
    md_day = mag_data.extract(start_time=st2)
    activity_plot(md_day, mag_qdc_adj,
                  dt64.strftime(st2, mag_fstr))
    r = [md_day]

    if rolling:
        # Trim end time
        md_rolling = mag_data.extract(end_time=et)
        activity_plot(md_rolling, mag_qdc_adj,
                      rolling_magdata_filename)
        r.append(md_rolling)
    return r


def make_temperature_plot(temperature_data, filename):
    temperature_data.plot()
    fig = plt.gcf()
    ax = plt.gca()
    fig.set_figwidth(6.4)
    fig.set_figheight(3)
    fig.subplots_adjust(bottom=0.175, top=0.75, 
                        left=0.15, right=0.925)
    mysavefig(fig, filename)


def make_voltage_plot(voltage_data, filename):
    voltage_data.plot()
    fig = plt.gcf()
    ax = plt.gca()
    ax.set_ylim([0, 3.5])
    fig.set_figwidth(6.4)
    fig.set_figheight(3)
    fig.subplots_adjust(bottom=0.175, top=0.75, 
                        left=0.15, right=0.925)
    mysavefig(fig, filename)


def make_stack_plot(mdl, filename):
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
    mysavefig(fig, filename)

def make_links(link_dir, link_data):
    for link in link_data:
        link_name = os.path.join(link_dir, link['name'])

        # Make the target a relative path
        target = os.path.relpath(dt64.strftime(link['date'], link['fstr']),
                                 os.path.dirname(link_name))
        if os.path.islink(link_name) and \
                os.readlink(link_name) == target:
            # Exists and is correct
            continue
        if os.path.lexists(link_name):
            os.unlink(link_name)
        os.symlink(target, link_name)

        
# ==========================================================================

# Parse command line options
parser = argparse.ArgumentParser(description\
                                     ='Plot AuroraWatch magnetometer data.')
parser.add_argument('-s', '--start-time',
                    help='Start time',
                    metavar='DATETIME');
parser.add_argument('-e', '--end-time',
                    help='End time',
                    metavar='DATETIME');
parser.add_argument('-v', '--verbose', action='store_true', 
                    default=0, help='Increase verbosity')
parser.add_argument('-m', '--make-links', 
                    action='store_true',
                    help='Make symbolic links')
parser.add_argument('--rolling', 
                    action='store_true',
                    help='Make rolling plots for today')
parser.add_argument('--sites', 
                    required=True,
                    help='Whitespace-separated list of sites (prefixed with network)',
                    metavar='"NETWORK1/SITE1 NETWORK2/SITE2 ..."')
parser.add_argument('-S', '--summary-dir', 
                    default=None,
                    help='Base directory for summary plots',
                    metavar='PATH')
parser.add_argument('--show', 
                    action='store_true',
                    help='Show plots for final day')
parser.add_argument('--stack-plot',
                    action='store_true',
                    help='Generate stack plot(s)')

args = parser.parse_args()
ap.verbose = args.verbose
    

# Use a consistent value for current time
day = np.timedelta64(24, 'h')
now = np.datetime64('now', 'us')
today = dt64.floor(now, day)
yesterday = today - day
tomorrow = today + day



# Get names of all networks and sites to be processed. Dictionary used
# to avoid duplicates.
network_site = {}
for s in args.sites.upper().split():
    n_s = s.split('/')
    if len(n_s) == 1:
        # Only network given, use all sites
        for k in ap.networks[n_s[0]].keys():
            network_site[n_s[0] + '/' + k] = (n_s[0], k)

    elif len(n_s) == 2:
        # Network and site given
        network_site[s] = tuple(n_s)
    else:
        raise Exception('bad value for network/site (' + network_site)


if args.rolling:
    if args.start_time or args.end_time:
        raise Exception('Cannot set start or end time for rolling plots')
    end_time = dt64.ceil(now, np.timedelta64(1, 'h'))
    start_time = end_time - day
else:
    if args.start_time is None or args.start_time == 'today': 
        start_time = today
    elif args.start_time == 'yesterday':
        start_time = yesterday
    else:
        start_time = np.datetime64(args.start_time).astype('M8[h]')

    if args.end_time is None:
        end_time = start_time + day
    elif args.end_time == 'today':
        end_time = today
    elif args.end_time == 'yesterday':
        end_time = yesterday
    elif args.end_time == 'tomorrow':
        end_time = tomorrow
    else:
        end_time = np.datetime64(args.end_time).astype('M8[h]')


t1 = start_time
while t1 < end_time:
    plt.close('all')

    t2 = t1 + day
    t1_eod = dt64.ceil(t1, day) # t1 end of day
    t2_eod = dt64.ceil(t2, day) # t2 end of day

    # List of magdata objects for this day
    mdl_day = []
    mdl_rolling = []

    for network_uc, site_uc in network_site.values():
        site_lc = site_uc.lower()
        network_lc = network_uc.lower()

        if args.summary_dir:
            summary_dir = args.summary_dir
        else:
            summary_dir = '/tmp'
        site_summary_dir = os.path.join(summary_dir, network_lc, site_lc)

        mag_fstr = os.path.join(site_summary_dir, 
                                '%Y/%m/' + site_lc + '_%Y%m%d.png')
        rolling_magdata_filename = os.path.join(site_summary_dir, 
                                                'rolling.png')
        
        stackplot_fstr = os.path.join(summary_dir, 'stackplots',
                                      '%Y/%m/%Y%m%d.png')

        rolling_stackplot_filename = os.path.join(summary_dir, 'stackplots',
                                                  'rolling.png')

        temp_fstr = os.path.join(site_summary_dir, 
                                 '%Y/%m/' + site_lc + '_temp_%Y%m%d.png')
        rolling_tempdata_filename = os.path.join(site_summary_dir, 
                                                 'rolling_temp.png')
        voltage_fstr = os.path.join(site_summary_dir, '%Y/%m/' + 
                                    site_lc + '_voltage_%Y%m%d.png')
        rolling_voltdata_filename = os.path.join(site_summary_dir, 
                                                 'rolling_volt.png')


        # t1 = start_time
        # while t1 < end_time:
        #     plt.close('all')
        #     t2 = t1 + day
        #     t1_eod = dt64.ceil(t1, day) # t1 end of day
        #     t2_eod = dt64.ceil(t2, day) # t2 end of day
        if has_data_of_type(network_uc, site_uc, 'MagData'):
            try:
                md = make_aurorawatch_plot(network_uc, site_uc, t1, t2, 
                                           args.rolling)
                # Store mag_data objects for daily and rolling
                # stack plots.
                if md is not None:
                    mdl_day.append(md[0])
                    if args.rolling:
                        mdl_rolling.append(md[1])

            except Exception as e:
                # except Warning as e:
                raise
                print(e.message)

        if has_data_of_type(network_uc, site_uc, 'TemperatureData'):
            temp_data = ap.load_data(network_uc, site_uc, 'TemperatureData', 
                                     t1, t2_eod)
            if temp_data is not None:
                temp_data.set_cadence(np.timedelta64(10, 'm'), 
                                      inplace=True)
                if args.rolling:
                    # Rolling plot
                    make_temperature_plot(temp_data.extract(end_time=t2),
                                          rolling_tempdata_filename)

                # Make day plot. Trim data from start because when
                # --rolling option is given it can include data from
                # the previous day.
                make_temperature_plot(temp_data.extract(start_time=t1_eod),
                                      dt64.strftime(t1_eod, temp_fstr))


        if has_data_of_type(network_uc, site_uc, 'VoltageData'):
            voltage_data = ap.load_data(network_uc, site_uc, 'VoltageData', 
                                        t1, t2_eod)
            if voltage_data is not None:
                voltage_data.set_cadence(np.timedelta64(10, 'm'), 
                                         inplace=True)
                if args.rolling:
                    # Rolling plot
                    make_voltage_plot(voltage_data.extract(end_time=t2),
                                      rolling_voltdata_filename)

                # Make day plot. Trim data from start because when
                # --rolling option is given it can include data from
                # the previous day.
                make_voltage_plot(voltage_data.extract(start_time=t1_eod),
                                  dt64.strftime(t1_eod, voltage_fstr))


    if args.stack_plot and len(mdl_day):
        make_stack_plot(mdl_day, dt64.strftime(mdl_day[0].start_time, 
                                               stackplot_fstr))
        if args.rolling:
            make_stack_plot(mdl_rolling, rolling_stackplot_filename)

    t1 = t2
    # End of time loop


if args.make_links:
    # Makes site links for each site listed
    for network_uc, site_uc in network_site.values():
        site_summary_dir = os.path.join(summary_dir, network_uc.lower(),
                                        site_uc.lower())
        link_data = [{'name': 'yesterday.png', 
                      'date': yesterday,
                      'fstr': mag_fstr}, 
                     {'name': 'yesterday_temp.png', 
                      'date': yesterday,
                      'fstr': temp_fstr}, 
                     {'name': 'yesterday_volt.png', 
                      'date': yesterday,
                      'fstr': voltage_fstr},               
                     {'name': 'today.png', 
                      'date': today,
                      'fstr': mag_fstr}, 
                     {'name': 'today_temp.png', 
                      'date': today,
                      'fstr': temp_fstr}, 
                     {'name': 'today_volt.png', 
                      'date': today,
                      'fstr': voltage_fstr},]
        make_links(site_summary_dir, link_data)
 
    # Stack plot links use a different base directory
    make_links(os.path.join(summary_dir, 'stackplots'),
               [{'name': 'yesterday.png', 
                 'date': yesterday,
                 'fstr': stackplot_fstr},               
                {'name': 'today.png', 
                 'date': today,
                 'fstr': stackplot_fstr}])

if args.show:    
    plt.show()