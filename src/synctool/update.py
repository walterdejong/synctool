#pylint: disable=consider-using-f-string
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
import datetime
import urllib.request
import urllib.error
import urllib.parse
import json

#try:
#    from typing import List, Dict, Union, Any
#except ImportError:
#    pass

from synctool.lib import verbose, error, stdout
import synctool.param


class ReleaseInfo:
#pylint: disable=too-few-public-methods
    '''holds release info'''

    TAGS_URL = 'https://api.github.com/repos/walterdejong/synctool/tags'

    def __init__(self):
        # type: () -> None
        '''initialize instance'''

        self.version = None     # type: str
        self.datetime = None    # type: datetime.datetime
        self.url = None         # type: str

    def load(self):
#pylint: disable=too-many-return-statements
        # type: () -> bool
        '''load release info from github
        Returns True on success
        '''

        tags = github_api(ReleaseInfo.TAGS_URL)
        if tags is None:
            # error message already printed
            return False

        try:
            self.version = tags[0]['name']
            self.url = tags[0]['tarball_url']
        except (IndexError, KeyError, TypeError):
            error('JSON data format error')
            return False

        # go find the date of the commit for this tag
        try:
            url = tags[0]['commit']['url']
        except (IndexError, KeyError, TypeError):
            error('JSON data format error')
            return False

        # get commit metadata via GitHub API
        commit = github_api(url)
        if commit is None:
            # error already printed
            return False

        try:
            date_str = commit['commit']['committer']['date']
        except (KeyError, TypeError):
            error('JSON data format error')
            return False

        # try parse the date string
        # unfortunately, the %Z format specifier is very badly
        # supported by Python (ie. it doesn't work right)
        # so I strip off the timezone as a workaround
        idx = date_str.find('Z')
        if idx > -1:
            date_str = date_str[:idx]

        try:
            self.datetime = datetime.datetime.strptime(date_str,
                                                       '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            error("datetime format error: '%s'" % date_str)
            return False

        verbose('info.version = %s' % self.version)
        verbose('info.datetime = %s' % str(self.datetime))
        verbose('info.url = %s' % self.url)
        return True


def github_api(url):
    #pylint: disable=consider-using-with
    # mypy-bug-type: (str) -> Union[List[Dict[str, Any]], Dict[str, Any]]
    '''Access GitHub API via URL
    Returns data (list or dict) depending on GitHub API function
    or None on error
    '''

    verbose('loading URL %s' % url)
    try:
        # can not use 'with' statement with urlopen()..?
        web = urllib.request.urlopen(url)
    except urllib.error.HTTPError as err:
        error('webserver at %s: %u %s' % (url, err.code, err.msg))
        return None

    except urllib.error.URLError as err:
        error('failed to access %s: %s' % (url, str(err.reason)))
        return None

    except IOError as err:
        error('failed to access %s: %s' % (url, err.strerror))
        return None

    try:
        # parse JSON data at URL
        data = json.load(web)
    finally:
        web.close()

    # this may be a list or a dict
    # don't know and don't care at this point
    return data


def check():
    # type: () -> bool
    '''check for newer version
    It does this by looking at releases at GitHub
    Returns True if a newer version is available
    '''

    info = ReleaseInfo()
    if not info.load():
        # error message already printed
        return False

    my_time = datetime.datetime.strptime(synctool.param.RELEASE_DATETIME,
                                         '%Y-%m-%dT%H:%M:%S')
    if info.datetime <= my_time:
        stdout('You are running the latest release of synctool')
        return False

    stdout('A newer version is available: %s' % info.version)
    stdout('released %s' % info.datetime)
    return True


def make_local_filename_for_version(version):
    # type: (str) -> str
    '''make filename for the downloaded synctool-x.y.tar.gz'''

    # strip tag naming scheme lead
    if version[:1] == 'v':
        version = version[1:]
    elif version[:9] == 'synctool-':
        version = version[9:]

    filename = 'synctool-%s.tar.gz' % version

    if not os.path.isfile(filename):
        return filename

    # file already exists, add sequence number
    nseq = 0
    while True:
        nseq += 1
        filename = 'synctool-%s(%d).tar.gz' % (version, nseq)
        if not os.path.isfile(filename):
            return filename


def print_progress(filename, totalsize, current_size):
    # type: (str, int, int) -> None
    '''print the download progress'''

    percent = 100 * current_size / totalsize
    percent = min(percent,100)

    print('\rdownloading %s ... %d%% ' % (filename, percent), end=' ')
    sys.stdout.flush()


def download():
    #pylint: disable=too-many-return-statements,consider-using-with
    # type: () -> bool
    '''download latest version
    Returns True on success, False on error
    '''

    info = ReleaseInfo()
    if not info.load():
        # error message already printed
        return False

    download_filename = make_local_filename_for_version(info.version)
    download_bytes = 0
    try:
        web = urllib.request.urlopen(info.url)
    except urllib.error.HTTPError as err:
        error('webserver at %s: %u %s' % (info.url, err.code, err.message))
        return False

    except urllib.error.URLError as err:
        error('failed to access %s: %s' % (info.url, str(err.reason)))
        return False

    except IOError as err:
        error('failed to access %s: %s' % (info.url, err.strerror))
        return False

    try:
        # get file size: Content-Length
        try:
            totalsize = int(web.info().getheaders('Content-Length')[0])
        except (ValueError, KeyError, IndexError):
            error('invalid response from webserver at %s' % info.url)
            return False

        # create download_filename
        try:
            fdownld = open(download_filename, 'w+b')
        except IOError as err:
            error('failed to create file %s: %s' % (download_filename,
                                                    err.strerror))
            return False

        with fdownld:
            print_progress(download_filename, totalsize, 0)
            download_bytes = 0

            while True:
                data = web.read(4096)
                if not data:
                    break

                download_bytes += len(data)
                print_progress(download_filename, totalsize, download_bytes)

                fdownld.write(data)
    finally:
        web.close()

    if download_bytes < totalsize:
        print()
        error('failed to download %s' % info.url)
        return False

    download_bytes += 100    # force 100% in the progress counter
    print_progress(download_filename, totalsize, download_bytes)
    return True

# EOB
