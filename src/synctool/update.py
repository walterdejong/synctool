#
#   synctool.update.py    WJ110
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''download the latest synctool.tar.gz'''

import os
import sys
import urllib2
import hashlib

from synctool.lib import verbose, error, stdout
import synctool.param


VERSION_CHECKING_URL = 'http://www.heiho.net/synctool/LATEST.txt'
DOWNLOAD_URL = 'http://www.heiho.net/synctool/'


def get_latest_version():
    '''get latest version by downloading the LATEST.txt versioning file'''

    tup = get_latest_version_and_checksum()
    if not tup:
        return None

    return tup[0]


def get_latest_version_and_checksum():
    '''get latest version and checksum by downloading
    the LATEST.txt versioning file
    '''

    verbose('accessing URL %s' % VERSION_CHECKING_URL)

    try:
        # can not use 'with' statement with urlopen()..?
        web = urllib2.urlopen(VERSION_CHECKING_URL)
    except urllib2.HTTPError as err:
        error('webserver at %s: %s' % (VERSION_CHECKING_URL, err.reason))
        return None

    except urllib2.URLError as err:
        error('failed to access %s: %s' % (VERSION_CHECKING_URL, err.reason))
        return None

    except IOError as err:
        error('failed to access %s: %s' % (VERSION_CHECKING_URL,
                                           err.strerror))
        return None

    data = web.read(1024)
    web.close()

    if not data or len(data) < 10:
        error('failed to access %s' % VERSION_CHECKING_URL)
        return None

    data = data.strip()

    # format of the data in LATEST.txt is:
    # <version> <MD5 checksum>
    arr = data.split()
    if len(arr) < 2:
        return None

    return (arr[0], arr[1])


def check():
    '''check for newer version on the website
    It does this by downloading the LATEST.txt versioning file
    Returns True if newer available, else False
    '''

    latest_version = get_latest_version()

    if latest_version == synctool.param.VERSION:
        stdout('You are running the latest version of synctool')
        return False
    else:
        stdout('A newer version of synctool is available: '
            'version %s' % latest_version)

    return True


def make_local_filename_for_version(version):
    '''make filename for the downloaded synctool-x.y.tar.gz'''

    filename = 'synctool-%s.tar.gz' % version

    if not os.path.isfile(filename):
        return filename

    # file already exists, add sequence number
    n = 2
    while True:
        filename = 'synctool-%s(%d).tar.gz' % (version, n)

        if not os.path.isfile(filename):
            return filename

        n += 1


def print_progress(filename, totalsize, current_size):
    '''print the download progress'''

    percent = 100 * current_size / totalsize
    if percent > 100:
        percent = 100

    print '\rdownloading %s ... %d%% ' % (filename, percent),
    sys.stdout.flush()


def download():
    '''download latest version
    Returns True on success, False on error
    '''

    tup = get_latest_version_and_checksum()
    if not tup:
        return False

    (version, checksum) = tup

    filename = 'synctool-%s.tar.gz' % version
    download_url = DOWNLOAD_URL + filename

    download_filename = make_local_filename_for_version(version)
    download_bytes = 0

    try:
        web = urllib2.urlopen(download_url)
    except urllib2.HTTPError as err:
        error('webserver at %s: %s' % (download_url, err.reason))
        return False

    except urllib2.URLError as err:
        error('failed to access %s: %s' % (download_url, err.reason))
        return False

    except IOError as err:
        error('failed to access %s: %s' % (download_url, err.strerror))
        return False

    # get file size: Content-Length
    try:
        totalsize = int(web.info().getheaders("Content-Length")[0])
    except (ValueError, KeyError):
        error('invalid response from webserver at %s' % download_url)
        web.close()
        return False

    # create download_filename
    try:
        f = open(download_filename, 'w+b')
    except IOError as err:
        error('failed to create file %s: %s' % (download_filename,
                                                err.strerror))
        web.close()
        return False

    with f:
        print_progress(download_filename, totalsize, 0)
        download_bytes = 0

        # compute checksum of downloaded file data
        sum1 = hashlib.md5()

        while True:
            data = web.read(4096)
            if not data:
                break

            download_bytes += len(data)
            print_progress(download_filename, totalsize, download_bytes)

            f.write(data)
            sum1.update(data)

    web.close()

    if download_bytes < totalsize:
        print
        error('failed to download file %s' % download_url)
        return False

    download_bytes += 100    # force 100% in the progress counter
    print_progress(download_filename, totalsize, download_bytes)

    if sum1.hexdigest() != checksum:
        error('checksum failed for %s' % download_filename)
        return False

    return True

# EOB
