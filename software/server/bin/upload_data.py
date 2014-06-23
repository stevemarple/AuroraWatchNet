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
# transfer using HTTP (also HTTPS although the server does not
# currently support it). Authentication in this case uses the HTTP
# digest method. The awnet.ini config file must contain a plaintext
# password and realm to use; the username is derived from the site
# name. Files to be uploaded can be selected on the basis of date
# range, and also archive type. Before a file is transferred to the
# AuroraWatch server a HEAD request is made. If the file is missing it
# is transferred immediately, otherwise the content length and MD5 sum
# for the file on the server are compared to the local copy. If both
# are the same then no upload for that file is required. If the local
# file is larger but the corresponding part on the server matches
# (based on the MD5 sum) then only the additional data is uploaded,
# otherwise the entire file is uploaded. This approach greatly reduces
# the data transferred when an updating daily file is transferred at
# regular intervals (10 minutes or less).

import argparse
import copy
import hashlib
import logging
import os
import sys
if sys.version_info[0] >= 3:
    import configparser
    from configparser import SafeConfigParser
else:
    import ConfigParser
    from ConfigParser import SafeConfigParser

import subprocess
import urlparse
import urllib
import urllib2

import datetime
now = datetime.datetime.utcnow()
today = now.replace(hour=0,minute=0,second=0,microsecond=0)
yesterday = today - datetime.timedelta(days=1)
tomorrow = today + datetime.timedelta(days=1)


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
        return datetime.datetime.strptime(s, '%Y-%m-%d')

    
def make_remote_rsync_directory(remote_host, remote_dir):
    logging.debug('Calling rsync to make remote directory, ' 
                  + remote_host + ':' + remote_dir)
    cmd = ['rsync', '/dev/null', remote_host + ':' + remote_dir + '/']
    if args.verbose:
        print(' '.join(cmd))
    subprocess.call(cmd)


def head_request(file_name, url):
    request = urllib2.Request(url + file_name)
    request.get_method = lambda : 'HEAD'
    try:
        response = urllib2.urlopen(request)
        return response
    except:
        return None
    

def http_upload(file_name, url):
    logging.debug('Uploading ' + file_name)
    values = {'file_name': file_name}
    fh = open(file_name, 'r')

    head_req = head_request(file_name, url)
    if head_req:
        # File is on server, check if the file is complete, or if only
        # some of the file can be sent
        h = hashlib.md5(fh.read(int(head_req.headers['Content-Length'])))

        if h.hexdigest().lower() == head_req.headers['X-MD5-Sum'].lower():
            # First portion matches
            if os.path.getsize(file_name) == \
                    int(head_req.headers['Content-Length']):
                # Same size so complete
                fh.close()
                logging.info(file_name + ' already uploaded')
                return True
            else:
                logging.info(file_name + ' already partially uploaded')
                values['file_offset'] = head_req.headers['Content-Length']
        else:
            # Portion on server differs, upload everything
            logging.info(file_name + ' is different')
            values['file_offset'] = 0
    else:
        # Missing, send all of file
        values['file_offset'] = 0

    logging.debug('File offset: ' + str(values['file_offset']))
    fh.seek(int(values['file_offset']))
    values['file_data'] = fh.read()
    fh.close()

    post_data = urllib.urlencode(values)

    try:
        request = urllib2.Request(url, post_data)
        response = urllib2.urlopen(request)
        if response.code == 200:
            logging.info('Uploaded ' + file_name)
        else:
            logging.error('Failed to upload ' + file_name)
            
        return response
    except:
        logging.error('Failed to upload ' + file_name)

    

def get_file_type_data():
    file_type_data = {}
    for ft in args.file_types.split():
        if not config.has_option(ft, 'filename') or \
                not config.get(ft, 'filename'):
            # This type not defined in config file
            continue
        file_type_data[ft] = {'fstr': config.get(ft, 'filename'),
                              'interval': datetime.timedelta(days=1)}
        today_file = today.strftime(file_type_data[ft]['fstr'])
        for i in (datetime.timedelta(minutes=1), 
                  datetime.timedelta(hours=1)):
            if today_file != (today+i).strftime(file_type_data[ft]['fstr']):
                file_type_data[ft]['interval'] = i
                break
    return file_type_data


parser = argparse.ArgumentParser(description=\
                                     'Upload AuroraWatch magnetometer data.')

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
                    default='awnettextdata awpacket aurorawatchrealtime ' \
                        + 'cloud logfile',
                    help='List of file types to upload',
                    metavar='TYPE1, TYPE2, ...')

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
logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                    format=args.log_format)


if args.start_time is None:
    start_time = today
else:
    start_time = parse_datetime(args.start_time)

if args.end_time is None:
    end_time = start_time + datetime.timedelta(days=1)
else:
    end_time = parse_datetime(args.end_time)

logging.debug('Now: ' + str(now))
logging.debug('Start time: ' + str(start_time))
logging.debug('End time: ' + str(end_time))


if not os.path.exists(args.config_file):
    logging.error('Missing config file ' + args.config_file)
    exit(1)

try:
    config = SafeConfigParser()
    config.add_section('upload')
    config.set('upload', 'method', 'rsync')
    config.set('upload', 'rsync_host', 'awn-data')
    config.read(args.config_file)
    site = config.get('magnetometer', 'site').upper()
    site_lc = site.lower()
except Exception as e:
    logging.error('Bad config file ' + args.config_file + ': ' + str(e))
    raise


if args.method:
    method = args.method
else:
    method = config.get('upload', 'method')

if args.all and method not in ['rsync', 'rrsync']:
    logging.error('--all can only be used with rsync and rrsync methods')
    exit(1)

logging.debug('Upload method: ' + method)
if method in ['rsync', 'rrsync']:
    # Upload by rsync, use SSH tunnelling. Assume that the SSH config
    # file defines an entry for "awn-data". It should look similar
    # to:
    #
    # Host awn-data
    # Hostname machine.lancs.ac.uk
    # User monty
    # remote_host = 'awn-data'
    remote_host = config.get('upload', 'rsync_host')
    if method == 'rrsync':
        # rrsync script in use on remote host. Assume that the target
        # directory for this site is correctly enforced.
        remote_site_dir = ''
    else:
        remote_site_dir = '/data/aurorawatchnet/' + site_lc
    if args.start_time is None and args.end_time is None:
        end_time = tomorrow
        start_time = end_time - datetime.timedelta(days=3)
    
    cmd = ['rsync', 
           '--archive', # Preserve everything
           '--no-perms', # Use file mode permissions
           # Don't transfer empty files, important since filesystem
           # corruption can cause files to have zero size which would
           # then destroy data on the server.
           '--min-size=1']
    # Options
    if args.verbose:
        cmd.append('--verbose')

    if args.dry_run:
        cmd.append('--dry-run')
        
    if args.all:
        if args.start_time is not None:
            logging.error('--start-time cannot be specified with --all')
            exit(1)
        if args.end_time is not None:
            logging.error('--end-time cannot be specified with --all')
            exit(1)

        # Append src directory. Trailing slash is important, it means the
        # contents of the directory.
        src_dir = os.path.join(os.sep, 'data', 'aurorawatchnet', site_lc)
        cmd.append(src_dir + os.sep)
        cmd.append(remote_host + ':' + remote_site_dir)
        logging.info('cmd: ' + ' '.join(cmd))
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
                    logging.debug('time: ' + str(t2))
                    file_name = t2.strftime(fstr)
                    if os.path.exists(file_name):
                        logging.debug('Found ' + file_name)
                        file_list.append(file_name)
                    else:
                        logging.debug('Missing ' + file_name)
                    t2 += interval
            if len(file_list) == 0:
                logging.info('No files to transfer')
            else:
                target_dir = remote_site_dir + t.strftime('/%Y/%m')
                # Ensure yearly directory is made, unless we have
                # already made it. The monthly data will get made on demand.
                if last_year != t.year:
                    make_remote_rsync_directory(remote_host, 
                                                os.path.dirname(target_dir))
                    last_year = t.year

                cmd2 = copy.copy(cmd)
                cmd2.extend(file_list)
                # Use trailing slash to signal to the remote rsync
                # that the target is a directory (it can't work this
                # out if only one file is to be transferred and the
                # target directory is missing).
                cmd2.append(remote_host + ':' + target_dir + '/')
                logging.info('cmd: ' + ' '.join(cmd2))
                if args.verbose:
                    print(' '.join(cmd2))
                subprocess.call(cmd2)
            t = t_next_day

elif method in ('http', 'https'):
    # Upload using HTTP POST. Enable a HTTPS method although not
    # supported by the server at present.

    url = config.get('upload', 'url')

    # If method is https then URL ought to use that scheme, but using
    # https URL for http upload is ok.
    if method == 'https' and urlparse.urlparse(url).scheme == 'http':
        logging.error('https upload method specified but url scheme is http')
        exit(1)

    # Store details for each file type. Compute the interval between
    # consecutive files for each file type, assuming that only minute,
    # hourly or daily variations are allowed.

    file_type_data = get_file_type_data()
    username = 'awn-' + site_lc
    password = config.get('upload', 'password')
    realm = config.get('upload', 'realm')
    
    authhandler = urllib2.HTTPDigestAuthHandler()
    authhandler.add_password(realm, url, username, password)
    opener = urllib2.build_opener(authhandler)
    urllib2.install_opener(opener)

    all_ok = True
    for ft in file_type_data.keys():
        fstr = file_type_data[ft]['fstr']
        interval = file_type_data[ft]['interval']
        t = start_time
        while t < end_time:
            logging.debug('time: ' + str(t))
            file_name = t.strftime(fstr)
            if os.path.exists(file_name):
                response = http_upload(file_name, url)
                if not response:
                    all_ok = False
            else:
                logging.debug('Missing ' + file_name)
            t += interval
    
else:
    raise Exception('Unknown upload method (' +  method + ')')



