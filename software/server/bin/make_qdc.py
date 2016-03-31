#!/usr/bin/env python
import argparse    
import logging
import os
import os.path
import sys
import time

import numpy as np
import matplotlib as mpl
# import matplotlib.pyplot as plt

from numpy.f2py.auxfuncs import throw_error
# from logging import exception
if os.environ.get("DISPLAY", "") == "":
    mpl.use('Agg')
import matplotlib.pyplot as plt


# Set timezone appropriately to get intended np.datetime64 behaviour.
os.environ['TZ'] = 'UTC'
time.tzset()

import auroraplot as ap
import auroraplot.dt64tools as dt64
import auroraplot.magdata
import auroraplot.datasets.aurorawatchnet
import auroraplot.datasets.samnet

logger = logging.getLogger(__name__)



assert os.environ.get('TZ') == 'UTC', \
    'TZ environment variable must be set to UTC'


# ==========================================================================

# Parse command line options
parser = argparse.ArgumentParser(description\
                                     ='Make AuroraWatch quiet-day curve(s).')
parser.add_argument('--archive',
                    help='Data archive name')
parser.add_argument('--dry-run',
                    action='store_true',
                    help='Test, do not save quiet day curves')
parser.add_argument('-e', '--end-time',
                    help='End time',
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
parser.add_argument('--plot',
                    action='count',
                    default=0,
                    help='Plot existing quiet day curves')
parser.add_argument('--single-qdc',
                    metavar='FILENAME',
                    help='Make single QDC for given interval')
parser.add_argument('--raise-all',
                    action='store_true',
                    help='No exception handling')
parser.add_argument('-s', '--start-time',
                    help='Start time',
                    metavar='DATETIME')
parser.add_argument('--smooth', 
                    action='store_true',
                    default=True,
                    help='Smooth QDC using truncated Fourier series')
parser.add_argument('--no-smooth', 
                    dest='smooth',
                    action='store_false',
                    help='Do not smooth QDC using truncated Fourier series')

parser.add_argument('project_site',
                    nargs='+',
                    metavar="PROJECT[/SITE]")

args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)



# Use a consistent value for current time
day = np.timedelta64(1, 'D').astype('m8[us]')
now = np.datetime64('now', 'us')
today = dt64.floor(now, day)
yesterday = today - day
tomorrow = today + day

if args.start_time is None:
    start_time = dt64.get_start_of_previous_month(today)
elif args.start_time == 'today': 
    start_time = today
elif args.start_time == 'yesterday':
    start_time = yesterday
else:
    start_time = dt64.floor(np.datetime64(args.start_time), day)

if args.end_time is None:
    end_time = start_time + day
elif args.end_time == 'today':
    end_time = today
elif args.end_time == 'yesterday':
    end_time = yesterday
elif args.end_time == 'tomorrow':
    end_time = tomorrow
else:
    end_time = dt64.floor(np.datetime64(args.end_time), day)
logger.debug('Start date: ' + str(start_time))
logger.debug('End date: ' + str(end_time))


# Get names of all projects and sites to be processed.
project_list, site_list = ap.parse_project_site_list(args.project_site)

if args.single_qdc and len(project_list) != 1:
    raise Exception('--single-qdc option requires one site')


for site_num in range(len(site_list)):
    project_uc = project_list[site_num]
    project_lc = project_uc.lower()
    site_uc = site_list[site_num]
    site_lc = site_uc.lower()
    logger.debug('Processing %s/%s' % (project_uc, site_uc))

    # Attempt to import missing projects
    if project_uc not in ap.projects:
        try:
            __import__('auroraplot.datasets.' + project_lc)
        except:
            pass
    
    ax = None
    if args.single_qdc:
        t1 = start_time
    else:
        t1 = dt64.get_start_of_month(start_time)

    while t1 < end_time:
        if args.single_qdc:
            t2 = end_time
        else:
            t2 = dt64.get_start_of_next_month(t1)

        if args.plot:
            mag_qdc = ap.magdata.load_qdc(project_uc, site_uc, t1)
            if mag_qdc is not None:
                lh = mag_qdc.plot(axes=ax)
                for h in lh:
                    h.set_label(dt64.strftime(t1, '%Y-%m-%d'))
                ax = plt.gca()

        else:
            archive, ad = ap.get_archive_info(project_uc, site_uc, 
                                              'MagData', 
                                              archive=getattr(args, 
                                                              'archive'))

            mag_data = ap.load_data(project_uc, site_uc, 'MagData', t1, t2,
                                    archive=archive,
                                    raise_all=args.raise_all)
            if mag_data is not None:
                mag_qdc = mag_data.make_qdc(smooth=args.smooth)
                qdc_archive, qdc_ad \
                    = ap.get_archive_info(project_uc, site_uc, 'MagQDC')

                if args.single_qdc:
                    filename = args.single_qdc
                else:
                    filename = dt64.strftime(t1, qdc_ad['path'])
                p = os.path.dirname(filename)
                if not os.path.isdir(p):
                    os.makedirs(p)
                if args.dry_run:
                    logger.info('Dry run, not saving QDC to ' + filename)
                else:
                    mag_qdc.savetxt(filename)

        t1 = t2

    if args.plot:
        if hasattr(ax, '__iter__'):
            for h in ax:
                legh = h.legend(fancybox=True, loc='best')
                legh.get_frame().set_alpha(0.7)
        else:
            legh = ax.legend(fancybox=True, loc='best')
            legh.get_frame().set_alpha(0.7)
        plt.show()

