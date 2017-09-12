#!/usr/bin/env python

import argparse
import auroraplot as ap
import auroraplot.tools
import auroraplot.datasets.aurorawatchnet
import auroraplot.datasets.bgs_schools
import auroraplot.dt64tools as dt64
from importlib import import_module
import logging
import numpy as np
import os
import requests
import sys

if sys.version_info[0] >= 3:
    # noinspection PyCompatibility
    from configparser import SafeConfigParser
else:
    # noinspection PyCompatibility
    from ConfigParser import SafeConfigParser
logger = logging.getLogger(__name__)


def read_config_file(filename):
    """Read config file."""
    logger.info('Reading config file ' + filename)
    config = SafeConfigParser()
    config_files_read = config.read(filename)
    if filename not in config_files_read:
        raise UserWarning('Could not read ' + filename)
    logger.debug('Successfully read ' + ', '.join(config_files_read))
    return config


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
    parser.add_argument('-c', '--config-file',
                        help='Logger daemon configuration file')
    parser.add_argument('-n', '--dry-run',
                        action='store_true',
                        help='Dry run (do not upload data)')
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
                        help='Set upload URL')

    parser.add_argument('project_site',
                        nargs='*',
                        metavar="PROJECT/SITE")

    args = parser.parse_args()
    print(args.project_site)
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
    config = None
    config_section = 'wow'
    wow_url = 'https://apimgmt.www.wow.metoffice.gov.uk/api/bulkimportfiles/aurorawatchnet'
    if args.config_file:
        if len(site_list):
            raise Exception('Cannot specify sites and a config file')
        config = read_config_file(args.config_file)
        project = config.get(config_section, 'project').upper()
        site = config.get(config_section, 'site').upper()
        project_list = [project]
        site_list = [site]
        file_ext = os.path.splitext(ap.get_archive_info(project, site, 'MagData')[1]['path'])[1]
        if file_ext == '.txt':
            # Uses awnettextdata data format
            local_path = config.get('awnettextdata', 'filename')
        elif file_ext == '.csv':
            local_path = config.get('raspitextdata', 'filename')
        else:
            raise Exception('Unknown data type')
        if config.has_option(config_section, 'url'):
            wow_url = config.get(config_section, 'url')

        # Patch auroraplot to use local data from the path defined in the config file
        ap.tools.change_load_data_paths(project,
                                        lambda path, project, site, data_type, archive: local_path,
                                        site_list=site_list, data_type_list=['MagData', 'TemperatureData'])

    elif len(site_list) == 0:
        raise Exception('No sites specified')
    elif len(site_list) > 1 and args.site_id:
        raise Exception('Only a single site can be processed when WOW site ID given on command line')

    if args.cadence:
        cadence = dt64.parse_timedelta64(args.cadence, 's')
        agg_mname, agg_fname = ap.tools.lookup_module_name(args.aggregate)
        agg_module = import_module(agg_mname)
        agg_func = getattr(agg_module, agg_fname)
    else:
        cadence = None

    if args.url:
        wow_url = args.url

    # Get the default archives
    archive = ap.parse_archive_selection(default_archive_selection)

    # Process --archive options
    if args.archive:
        archive = ap.parse_archive_selection(args.archive, defaults=archive)

    for n in range(len(project_list)):
        project = project_list[n]
        site = site_list[n]
        # Get WOW site ID and authentication
        if args.site_id:
            wow_site_id = args.site_id
        elif config and config.has_option(config_section, 'site_id'):
            wow_site_id = config.get(config_section, 'site_id')
        else:
            wow_site_id = ap.get_site_info(project, site, 'wow_site_id')
        if args.site_auth:
            wow_site_auth = args.site_id
        elif config and config.has_option(config_section, 'site_auth'):
            wow_site_auth = config.get(config_section, 'site_auth')
        else:
            # Site authentication should not be stored in the public record but might have been inserted by
            # auroraplot_custom.py
            wow_site_auth = ap.get_site_info(project, site, 'wow_site_auth')

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

            temp_channels = ['Sensor temperature']
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

                # Ignore this time if no valid magnetometer data
                if np.any(np.isfinite(md.data[:, tidx])):
                    payload.append('\t'.join(map(str, cols)))

            if len(payload) == 0:
                logger.debug('No data to upload for %s - %s', md.start_time, md.end_time)
                continue

            payload = '\n'.join(payload) + '\n'

            # Upload to WOW
            params = (('qqFile', 'test123.txt'),  # TODO: set file name correctly
                      ('siteId', wow_site_id),
                      ('siteAuthenticationKey', wow_site_auth))
            if args.dry_run:
                logger.debug('Dry run, not uploading to %s', wow_url)
            else:
                logger.debug('Uploading to %s', wow_url)

                req = requests.post(wow_url, params=params, data=payload)
                logger.debug(req)
                if req.status_code != 200:
                    logger.error('Failed to upload data to WOW')


if __name__ == '__main__':
    main()
