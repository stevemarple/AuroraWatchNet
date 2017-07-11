#!/usr/bin/env python

import argparse
import auroraplot as ap
import auroraplot.datasets.aurorawatchnet
import auroraplot.datasets.bgs_schools
import auroraplot.dt64tools as dt64
import auroraplot.tools
from importlib import import_module
import logging
import numpy as np
import requests
import sys


logger = logging.getLogger(__name__)


def main():
    # For each project set the archive from which data is loaded.
    default_archive_selection = [['AWN', 'realtime'],
                                 ]

    # Define command line arguments
    parser = argparse.ArgumentParser(description='Plot magnetometer data',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--aggregate',
                        default='scipy.average',
                        help='Aggregate function used for setting cadence',
                        metavar='MODULE.NAME')
    parser.add_argument('-a', '--archive',
                        action='append',
                        nargs=2,
                        help='Select data archive used for project or site',
                        metavar=('PROJECT[/SITE]', 'ARCHIVE'))
    parser.add_argument('--cadence',
                        default='1m',
                        help='Set cadence')
    parser.add_argument('-e', '--end-time',
                        help='End time for data transfer (exclusive)',
                        metavar='DATETIME')
    parser.add_argument('--log-level',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        default='warning',
                        help='Control how much detail is printed',
                        metavar='LEVEL')
    parser.add_argument('-s', '--start-time',
                        default='yesterday',
                        help='Start time for data transfer (inclusive)',
                        metavar='DATETIME')
    parser.add_argument('--site-id',
                        help='WOW site ID',
                        metavar='ID')
    parser.add_argument('--site-auth',
                        help='WOW site authentication key (6 digit)',
                        metavar='AUTH')
    parser.add_argument('--url',
                        default='',  # TODO: set production URL
                        help='Set upload URL')

    parser.add_argument('project_site',
                        nargs='*',
                        metavar="PROJECT/SITE")

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    st = dt64.parse_datetime64(args.start_time, 's')
    if args.end_time is None:
        et = st + np.timedelta64(86400, 's')
    else:
        try:
            # Parse as date
            et = dt64.parse_datetime64(args.end_time, 's')
        except ValueError:
            try:
                # Parse as a set of duration values
                et = st + np.timedelta64(0, 's')
                et_words = args.end_time.split()
                assert len(et_words) % 2 == 0, 'Need even number of words'
                for n in range(0, len(et_words), 2):
                    et += np.timedelta64(float(et_words[n]), et_words[n + 1])
            except:
                raise
        except:
            raise

    project_list, site_list = ap.parse_project_site_list(args.project_site)
    if len(site_list) == 0:
        sys.stderr.write('No sites specified\n')
        sys.exit(1)
    elif len(site_list) > 1 and args.site_id:
        raise Exception('Only a single site can be processed when WOW site ID given on command line')

    if args.cadence:
        cadence = dt64.parse_timedelta64(args.cadence, 's')
        agg_mname, agg_fname = ap.tools.lookup_module_name(args.aggregate)
        agg_module = import_module(agg_mname)
        agg_func = getattr(agg_module, agg_fname)
    else:
        cadence = None

    # Get the default archives
    archive = ap.parse_archive_selection(default_archive_selection)

    # Process --archive options
    if args.archive:
        archive = ap.parse_archive_selection(args.archive, defaults=archive)

    for n in range(len(project_list)):
        project = project_list[n]
        site = site_list[n]
        if args.site_id:
            wow_site_id = args.site_id
        else:
            wow_site_id = ap.get_site_info(project, site, 'wow_site_id')
            
        kwargs = {}
        if project in archive and site in archive[project]:
            kwargs['archive'] = archive[project][site]
        if cadence:
            kwargs['cadence'] = cadence
            kwargs['aggregate'] = agg_func

        if ap.is_operational(project, site, st, et):
            md = ap.load_data(project, site, 'MagData', st, et, **kwargs)
        else:
            logger.info('%s/%s not operational at this time', project, site)
            md = None
        # If result is None then no data available so ignore those
        # results.
        if md is not None and md.data.size and np.any(np.isfinite(md.data)):
            md = md.mark_missing_data(cadence=3 * md.nominal_cadence)
            if cadence:
                md.set_cadence(cadence, aggregate=agg_func, inplace=True)

            temp_channels = ['System temperature', 'Sensor temperature']
            td = ap.load_data(project, site, 'TemperatureData', st, et,
                              channels=temp_channels)
            if td is not None and td.data.size and np.any(np.isfinite(td.data)):
                td = td.mark_missing_data(cadence=3 * td.nominal_cadence)
                if cadence:
                    td.set_cadence(cadence, aggregate=agg_func, inplace=True)

            payload = []
            for tidx in range(md.data.shape[1]):
                t = md.sample_start_time[tidx].astype('datetime64[s]').astype(int)
                cols = [t]
                if md.units == 'T':
                    cols.extend(md.data[:, tidx] * 1e9)  # convert to nT
                else:
                    raise Exception('Unexpected units')
                
                if td is not None and td.data.size:
                    cols.extend(td.data[:, tidx])
                else:
                    cols.extend([np.NaN] * len(temp_channels))

                # Ignore timestamp if no valid magnetometer data
                if np.any(np.isfinite(md.data[:, tidx])):
                    payload.append('\t'.join(map(str, cols)))

            if len(payload) == 0:
                logger.debug('No data to upload for %s - %s', md.start_time, md.end_time)
                continue
            
            payload = '\n'.join(payload) + '\n'
            print(payload)

            # Upload to WOW
            params = (('qqFile', 'test123.txt'),
                      ('siteId', wow_site_id),
                      ('siteAuthenticationKey', args.site_auth))
            logger.debug('Uploading to %s', args.url)

            req = requests.post(args.url, params=params, data=payload)
            logger.debug(req)
            if req.status_code != 200:
                logger.error('Failed to upload data to WOW')


if __name__ == '__main__':
    main()
