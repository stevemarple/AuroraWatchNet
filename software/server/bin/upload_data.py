#!/usr/bin/env python

# Upload data to AuroraWatch UK. For the rsync method this is just a
# simple wrapper to rsync which figures out the directory structure to
# use based on the site name, which is extracted from the awnet.ini
# config file. Authentication is granted based on the presence on an
# SSH public key on the server, and the corresponding private key on
# the uploading computer. For more security the rrsync script provided
# with rsync can be used. This requires the authorized_keys file to
# restrict the command which runs for a given SSH public key. It is
# recommended to modify the rrsync script to disable the -L and
# --copy-links options.
#
# For cases when SSH access is not available provide an option to
# transfer using HTTP. Authentication in this case uses the HTTP
# digest method. The awnet.ini config file must contain a plaintext
# password and realm to use; the username is derived from the site
# name. Files to be uploaded can be selected on the basis of date
# range, and also archive type. Before a file is transferred to the
# AuroraWatch server a GET request is made which indicates if the file
# is present on the server, and if so its size and MD5 sum are also
# returned. If the file is missing it is transferred immediately,
# otherwise the content length and MD5 sum for the file on the server
# are compared to the local copy. If both are the same then no upload
# for that file is required. If the local file is larger but the
# corresponding part on the server matches (based on the MD5 sum) then
# only the additional data is uploaded, otherwise the entire file is
# uploaded. This approach greatly reduces the data transferred when an
# updating daily file is transferred at regular intervals (10 minutes
# or less).

import argparse
import copy
import datetime
import hashlib
import logging
import os
import random
import sys
import subprocess
import time
import urlparse
import urllib
import urllib2
import aurorawatchnet as awn

if sys.version_info[0] >= 3:
    from configparser import SafeConfigParser
else:
    from ConfigParser import SafeConfigParser

logger = logging.getLogger(__name__)


class NoRedirection(urllib2.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


def make_remote_rsync_directory(remote_host, remote_dir):
    logger.debug('Calling rsync to make remote directory, ' + remote_host + ':' + remote_dir)
    cmd = ['rsync', '/dev/null', remote_host + ':' + remote_dir + '/']
    if args.verbose:
        print(' '.join(cmd))
    subprocess.call(cmd)


def get_redirected_url(url, authhandler):
    """
    Test if accessing the URL requires a redirect.

    Make  a HEAD request. Return the final URL used after any
    Future requests should use the redirected URL.
    """

    # Disable redirection and handle manually with limit on number of
    # redirects.
    opener = urllib2.build_opener(NoRedirection)
    max_redirects = 5
    for n in range(max_redirects + 1):
        response = opener.open(url)
        if response.code in (301, 302, 307, 308):
            url = response.headers['Location']
            authhandler.add_password(realm, url, username, password)
        else:
            return url

    raise Exception('Too many HTTP redirects')


def http_upload(file_name, url, remove_source=False):
    logger.debug('Uploading ' + file_name)
    values = {'file_name': file_name}
    fh = open(file_name, 'r')

    url_for_get = url + '?' + urllib.urlencode({'file_name': file_name})
    logger.debug('GET ' + url_for_get)
    get_req = urllib2.urlopen(url_for_get)
    file_details = SafeConfigParser()
    file_details.readfp(get_req)
    section_name = os.path.basename(file_name)
    if int(file_details.get(section_name, 'found')):
        # File is on server, check if the file is complete, or if only
        # some of the file can be sent
        content_length = file_details.get(section_name, 'content_length')
        md5_sum = file_details.get(section_name, 'md5_sum')
        logger.debug('file exists on server, content_length=%s, md5_sum=%s',
                     str(content_length), md5_sum)

        h = hashlib.md5(fh.read(int(content_length)))

        if h.hexdigest().lower() == md5_sum.lower():
            # First portion matches
            if os.path.getsize(file_name) == int(content_length):
                # Same size so complete
                fh.close()
                logger.info(file_name + ' already uploaded')
                if remove_source:
                    logger.info('removing source file ' + file_name)
                    try:
                        os.remove(file_name)
                    except:
                        logger.exception('could not remove ' + file_name)

                return True
            else:
                logger.info(file_name + ' partially uploaded')
                values['file_offset'] = content_length
        else:
            # Portion on server differs, upload everything
            logger.info(file_name + ' is different')
            values['file_offset'] = 0
    else:
        # Missing, send all of file
        values['file_offset'] = 0

    get_req.close()

    logger.debug('File offset: ' + str(values['file_offset']))
    fh.seek(int(values['file_offset']))
    values['file_data'] = fh.read()
    fh.close()

    post_data = urllib.urlencode(values)

    try:
        logger.debug('POST ' + url)
        request = urllib2.Request(url, post_data)
        response = urllib2.urlopen(request)
        if response.code == 200:
            logger.info('Uploaded ' + file_name)
        else:
            logger.error('Failed to upload ' + file_name)

        return response
    except:
        logger.error('Failed to upload ' + file_name)


def get_file_type_data():
    file_type_data = {}
    if args.file_types and args.file_types.strip():
        file_types = args.file_types.split()
    elif config.has_option(args.section, 'file_types'):
        file_types = config.get(args.section, 'file_types').split()
    else:
        file_types = ['awnettextdata', 'awpacket', 'aurorawatchrealtime', 'cloud', 'logfile', 'raspitextdata', 'gnss']
        for sec in config.sections():
            if sec.startswith('genericdata:'):
                file_types.append(sec)

    for ft in file_types:
        if not config.has_option(ft, 'filename') or \
                not config.get(ft, 'filename'):
            # This type not defined in config file
            continue
        file_type_data[ft] = {'fstr': config.get(ft, 'filename'),
                              'interval': datetime.timedelta(days=1)}
        today_file = today.strftime(file_type_data[ft]['fstr'])
        for i in (datetime.timedelta(minutes=1),
                  datetime.timedelta(hours=1)):
            if today_file != (today + i).strftime(file_type_data[ft]['fstr']):
                file_type_data[ft]['interval'] = i
                break
    return file_type_data


def report_no_data(url, t, file_type):
    """
    Report to the server that no data was available for upload.
    """
    logger.debug('Reporting no ' + file_type + ' file for ' + str(t))
    no_data_url = url + '?' + urllib.urlencode(
        {'no_data': '1',
         'start_time': t.strftime('%Y-%m-%dT%H:%M:%SZ'),
         'file_type': file_type})
    logger.debug('GET ' + no_data_url)
    req = urllib2.urlopen(no_data_url)
    req.read()
    req.close()


now = datetime.datetime.utcnow()
today = now.replace(hour=0, minute=0, second=0, microsecond=0)
yesterday = today - datetime.timedelta(days=1)
tomorrow = today + datetime.timedelta(days=1)

parser = argparse.ArgumentParser(description='Upload AuroraWatch magnetometer data.')

parser.add_argument('-c', '--config-file',
                    default='/etc/awnet.ini',
                    help='Configuration file')
parser.add_argument('--log-level',
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    default='warning',
                    help='Control how much detail is printed',
                    metavar='LEVEL')
parser.add_argument('--log-format',
                    default='%(levelname)s:%(message)s',
                    help='Set format of log messages',
                    metavar='FORMAT')
parser.add_argument('--method',
                    choices=['rsync', 'rrsync', 'http', 'https'],
                    help='Select upload method')

parser.add_argument('-s', '--start-time',
                    help='Start time for data transfer (inclusive)',
                    metavar='DATETIME')
parser.add_argument('-e', '--end-time',
                    help='End time for data transfer (exclusive)',
                    metavar='DATETIME')
parser.add_argument('--file-types',
                    # aurorawatchrealtime deprecated for new sites
                    help='List of file types to upload',
                    metavar='TYPE1, TYPE2, ...')
if hasattr(os, 'nice'):
    parser.add_argument('--nice',
                        type=int,
                        help='Modify scheduling priority')
parser.add_argument('--random-delay',
                    help='Add random delay (for use by cron)',
                    metavar='SECONDS')
parser.add_argument('--remove-source-files',
                    action='store_true',
                    help='Remove source file')
parser.add_argument('--section',
                    default='upload',
                    help='Name of upload section in configuration file')

# rsync options
rsync_grp = parser.add_argument_group('rsync', 'options for rsync uploads')

rsync_grp.add_argument('--all',
                       action='store_true',
                       default=False,
                       help='rsync all non-empty files in dataset')
rsync_grp.add_argument('-n', '--dry-run',
                       action='store_true',
                       default=False,
                       help='Test without uploading')
rsync_grp.add_argument('-v', '--verbose',
                       default=False,
                       action='store_true',
                       help='Be verbose')

args = parser.parse_args()
if __name__ == '__main__':
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format=args.log_format)

if args.start_time is None:
    start_time = today
else:
    start_time = awn.parse_datetime(args.start_time)

if args.end_time is None:
    end_time = start_time + datetime.timedelta(days=1)
else:
    end_time = awn.parse_datetime(args.end_time)

logger.debug('Now: ' + str(now))
logger.debug('Start time: ' + str(start_time))
logger.debug('End time: ' + str(end_time))

if not os.path.exists(args.config_file):
    logger.error('Missing config file ' + args.config_file)
    exit(1)

try:
    config = awn.read_config_file(args.config_file)
    site = config.get(args.section, 'site').upper()
    site_lc = site.lower()
except Exception as e:
    logger.error('Bad config file ' + args.config_file + ': ' + str(e))
    raise

if hasattr(os, 'nice'):
    nice = 0
    if args.nice is not None:
        nice = args.nice
    elif not sys.stdin.isatty():
        # Standard input is not a TTY, assume called from cron. Set
        # niceness to 10, taking into account that niceness may have been
        # set externally. Do not attmept to reduce niceness.
        nice = max(10 - os.nice(0), 0)
    if nice:
        os.nice(nice)
    if os.nice(0):
        logger.debug('niceness set to %d', os.nice(0))

delay = None
if args.random_delay:
    delay = random.random() * float(args.random_delay)
elif not sys.stdin.isatty():
    # Standard input is not a TTY, assume called from cron
    delay = random.random() * 50

if delay:
    logger.debug('sleeping for %.1fs', delay)
    time.sleep(delay)

if args.method:
    method = args.method
else:
    method = config.get(args.section, 'method')

if args.all and method not in ['rsync', 'rrsync']:
    logger.error('--all can only be used with rsync and rrsync methods')
    exit(1)

logger.debug('Upload method: ' + method)
if method in ['rsync', 'rrsync']:
    # Upload by rsync, use SSH tunnelling. Assume that the SSH config
    # file defines an entry for "awn-data". It should look similar
    # to:
    #
    # Host awn-data
    # Hostname machine.lancs.ac.uk
    # User monty
    # remote_host = 'awn-data'
    remote_host = config.get(args.section, 'rsync_host')
    if method == 'rrsync':
        # rrsync script in use on remote host. Assume that the target
        # directory for this site is correctly enforced.
        remote_site_dir = ''
    elif config.has_option(args.section, 'path'):
        remote_site_dir = config.get(args.section, 'path')
    else:
        remote_site_dir = '/data/aurorawatchnet/' + site_lc
    if args.start_time is None and args.end_time is None:
        end_time = tomorrow
        start_time = end_time - datetime.timedelta(days=3)

    cmd = ['rsync',
           '--archive',  # Preserve everything
           '--no-perms',  # Use file mode permissions
           # Don't transfer empty files, important since filesystem
           # corruption can cause files to have zero size which would
           # then destroy data on the server.
           '--min-size=1']

    if config.has_option(args.section, 'rsync_options'):
        # Space-separated list of options
        cmd.extend(config.get(args.section, 'rsync_options').split())

    # Options
    if args.verbose:
        cmd.append('--verbose')

    if args.dry_run:
        cmd.append('--dry-run')

    if args.all:
        if args.start_time is not None:
            logger.error('--start-time cannot be specified with --all')
            exit(1)
        if args.end_time is not None:
            logger.error('--end-time cannot be specified with --all')
            exit(1)

        # Append src directory. Trailing slash is important, it means the
        # contents of the directory.
        src_dir = os.path.join(os.sep, 'data', 'aurorawatchnet', site_lc)
        cmd.append(src_dir + os.sep)
        cmd.append(remote_host + ':' + remote_site_dir)
        logger.info('cmd: ' + ' '.join(cmd))
        if args.verbose:
            print(' '.join(cmd))

        subprocess.call(cmd)

    else:
        # Find list of files to upload
        file_type_data = get_file_type_data()

        # Upload to a daily directory
        last_year = None
        t = start_time
        while t < end_time:
            t_next_day = t + datetime.timedelta(days=1)
            file_list = []
            # Find matching files, at their intervals
            for ft in file_type_data.keys():
                fstr = file_type_data[ft]['fstr']
                interval = file_type_data[ft]['interval']
                t2 = t
                while t2 < t_next_day:
                    logger.debug('time: ' + str(t2))
                    file_base_name = t2.strftime(fstr)
                    # Try standard filenames as well as appending
                    # '.bad' or other extension signifying a data
                    # quality problem.
                    for ext in ['', config.get('dataqualitymonitor',
                                               'extension')]:
                        file_name = file_base_name + ext
                        if os.path.exists(file_name):
                            logger.debug('Found ' + file_name)
                            file_list.append(file_name)
                        else:
                            logger.debug('Missing ' + file_name)
                    t2 += interval
            if len(file_list) == 0:
                logger.info('No files to transfer')
            else:
                target_dir = remote_site_dir + t.strftime('/%Y/%m')
                # Ensure yearly directory is made, unless we have
                # already made it. The monthly data will get made on demand.
                if last_year != t.year:
                    make_remote_rsync_directory(remote_host,
                                                os.path.dirname(target_dir))
                    last_year = t.year

                cmd2 = copy.copy(cmd)
                if args.remove_source_files:
                    if t >= today:
                        logger.info('refusing to remove source files for today')
                    else:
                        cmd2.append('--remove-source-files')

                cmd2.extend(file_list)
                # Use trailing slash to signal to the remote rsync
                # that the target is a directory (it can't work this
                # out if only one file is to be transferred and the
                # target directory is missing).
                cmd2.append(remote_host + ':' + target_dir + '/')
                logger.info('cmd: ' + ' '.join(cmd2))
                if args.verbose:
                    print(' '.join(cmd2))
                subprocess.call(cmd2)
            t = t_next_day

elif method in ('http', 'https'):
    # Upload using HTTP POST. Enable a HTTPS method although not
    # supported by the server at present.

    url = config.get(args.section, 'url')

    # If method is https then URL ought to use that scheme, but using
    # https URL for http upload is ok.
    if method == 'https' and urlparse.urlparse(url).scheme == 'http':
        logger.error('https upload method specified but url scheme is http')
        exit(1)

    # Store details for each file type. Compute the interval between
    # consecutive files for each file type, assuming that only minute,
    # hourly or daily variations are allowed.

    file_type_data = get_file_type_data()
    if config.has_option(args.section, 'username'):
        username = config.get(args.section, 'username')
    else:
        username = 'awn-' + site_lc
    password = config.get(args.section, 'password')
    realm = config.get(args.section, 'realm')

    authhandler = urllib2.HTTPDigestAuthHandler()
    authhandler.add_password(realm, url, username, password)
    opener = urllib2.build_opener(authhandler)
    urllib2.install_opener(opener)

    # Check for HTTP redirects. Do this once and update the url used
    # here. Don't update the config file.
    new_url = get_redirected_url(url, authhandler)
    if new_url != url:
        url = new_url
        logger.info('HTTP redirection, using %s', url)

    all_ok = True
    for ft in file_type_data.keys():
        fstr = file_type_data[ft]['fstr']
        interval = file_type_data[ft]['interval']
        t = start_time
        while t < end_time:
            logger.debug('time: ' + str(t))
            file_base_name = t.strftime(fstr)
            data_missing = True
            # Try standard filenames as well as appending '.bad' or
            # other extension signifying a data quality problem.
            for ext in ['', config.get('dataqualitymonitor', 'extension')]:
                file_name = file_base_name + ext
                if os.path.exists(file_name):
                    if os.path.getsize(file_name):
                        data_missing = False
                        rem_source = args.remove_source_files
                        if rem_source and t >= today:
                            logger.info('refusing to remove source files for today')
                            rem_source = False

                        response = http_upload(file_name, url, rem_source)
                        if not response:
                            all_ok = False
                    else:
                        logger.info('Refusing to upload %s: empty file', file_name)

                elif ext == '':
                    # No .bad extension
                    if ft in ('logfile'):
                        # Log files etc might not be present even
                        # in normal operation
                        logger.debug('Missing ' + file_name)
                    else:
                        # These should normally be present
                        logger.info('Missing ' + file_name)

            if data_missing and not args.remove_source_files:
                report_no_data(url, t, ft)

            dname = os.path.dirname(file_name)
            if args.remove_source_files and os.path.isdir(dname) and len(os.listdir(dname)) == 0:
                try:
                    logger.info('removing directory ' + dname)
                    os.removedirs(dname)
                except:
                    logger.exception('could not remove directory ' + dname)

            t += interval

else:
    raise Exception('Unknown upload method (' + method + ')')
