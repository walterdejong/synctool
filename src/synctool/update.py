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
import urllib2
import hashlib
import xml.parsers
import xml.dom.minidom

from synctool.lib import verbose, error, stdout
import synctool.param

LATEST_XML = 'https://walterdejong.github.io/synctool/latest.xml'
VERSION_CHECKING_URL = 'https://walterdejong.github.io/synctool/LATEST.txt'
DOWNLOAD_URL = 'https://github.com/walterdejong/synctool/archive/'


class ReleaseInfo(object):
    '''holds release info'''

    # put a limit on how much data we will read at the most
    DATA_LIMIT = 4096

    def __init__(self):
        '''initialize instance'''

        self.version = None
        self.datetime = None
        self.url = None
        self.md5sum = None
        self.sha512sum = None

    def load(self, url=LATEST_XML):
        '''load release info from URL
        Returns True on success
        '''

        verbose('loading URL %s' % url)
        try:
            # can not use 'with' statement with urlopen()..?
            web = urllib2.urlopen(url)
        except urllib2.HTTPError as err:
            error('webserver at %s: %u %s' % (url, err.code, err.msg))
            return False

        except urllib2.URLError as err:
            error('failed to access %s: %u %s' % (url, err.code, err.msg))
            return False

        except IOError as err:
            error('failed to access %s: %s' % (VERSION_CHECKING_URL,
                                               err.strerror))
            return False

        try:
            data = web.read(ReleaseInfo.DATA_LIMIT)
        finally:
            web.close()

        if not data or len(data) < 10:
            error('failed to access %s' % url)
            return False

        return self.parse(data)

    def parse(self, data):
        '''Parse XML data
        Returns True on success
        '''

        try:
            doc = xml.dom.minidom.parseString(data)
        except xml.parsers.expat.ExpatError:
            error('syntax error in XML data')
            return False

        self.version = xml_tagvalue(doc, 'version')
        self.datetime = xml_tagvalue(doc, 'datetime')
        self.url = xml_tagvalue(doc, 'url')
        self.md5sum = xml_tagvalue(doc, 'checksum', 'type=md5')
        self.sha512sum = xml_tagvalue(doc, 'checksum', 'type=sha512')

        # convert datetime object
        if self.datetime is not None:
            try:
                self.datetime = datetime.datetime.strptime(self.datetime,
                                                          '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                error('invalid datetime format in XML data')
                return False

        return True


def xml_tagvalue(doc, tagname, attrib=None):
    '''Return value for tag
    A specific attribute may also be given,
    in the form "attrib=value"
    '''

    if attrib is None:
        # return value of tag
        tags = doc.documentElement.getElementsByTagName(tagname)
        if len(tags) >= 1:
            return tags[0].childNodes[0].data

    else:
        # return value of tag where attrib is set
        attr, attr_value = attrib.split('=', 1)

        for tag in doc.documentElement.getElementsByTagName(tagname):
            if (tag.hasAttribute(attr) and
                tag.getAttribute(attr) == attr_value):
                return tag.childNodes[0].data

    # tag not found
    return None




def get_latest_version():
    '''get latest version by downloading the LATEST.txt versioning file'''

    tup = get_latest_version_and_checksum()
    if tup is None:
        return None

    return tup[0]


def get_latest_version_and_checksum():
    '''get latest version and checksum by downloading
    the LATEST.txt versioning file

    Returns tuple (version, md5)
    or None on error
    '''

    verbose('accessing URL %s' % VERSION_CHECKING_URL)

    try:
        # can not use 'with' statement with urlopen()..?
        web = urllib2.urlopen(VERSION_CHECKING_URL)
    except urllib2.HTTPError as err:
        error('webserver at %s: %u %s' % (VERSION_CHECKING_URL, err.code,
                                          err.msg))
        return None

    except urllib2.URLError as err:
        error('failed to access %s: %u %s' % (VERSION_CHECKING_URL, err.code,
                                              err.msg))
        return None

    except IOError as err:
        error('failed to access %s: %s' % (VERSION_CHECKING_URL,
                                           err.strerror))
        return None

    try:
        data = web.read(1024)
    finally:
        web.close()

    if not data or len(data) < 10:
        error('failed to access %s' % VERSION_CHECKING_URL)
        return None

    data = data.strip()

    # format of the data in LATEST.txt is:
    # <version> <MD5 checksum>
    arr = data.split()
    if len(arr) < 2:
        error('data format error in %s' % VERSION_CHECKING_URL)
        return None

    return arr


def check():
    '''check for newer version on the website
    It does this by downloading the LATEST.txt versioning file
    Returns True if newer available, else False
    '''

    latest_version = get_latest_version()
    if latest_version is None:
        # error message already printed
        return False

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

    arr = get_latest_version_and_checksum()
    if arr is None:
        return False

    version = arr[0]
    md5_checksum = arr[1]
    if len(arr) > 2:
        sha512_checksum = arr[2]
    else:
        sha512_checksum = None

    filename = 'synctool-%s.tar.gz' % version
    download_url = DOWNLOAD_URL + filename

    download_filename = make_local_filename_for_version(version)
    download_bytes = 0

    try:
        web = urllib2.urlopen(download_url)
    except urllib2.HTTPError as err:
        error('webserver at %s: %u %s' % (download_url, err.code, err.msg))
        return False

    except urllib2.URLError as err:
        error('failed to access %s: %u %s' % (download_url, err.code,
                                              err.msg))
        return False

    except IOError as err:
        error('failed to access %s: %s' % (download_url, err.strerror))
        return False

    # compute checksum of downloaded file data
    # if present, check the SHA-512 checksum
    # otherwise, check the MD5 checksum
    # (MD5 is for historical reasons)
    sum5 = hashlib.md5()
    if sha512_checksum is not None:
        sum512 = hashlib.sha512()

    try:
        # get file size: Content-Length
        try:
            totalsize = int(web.info().getheaders('Content-Length')[0])
        except (ValueError, KeyError):
            error('invalid response from webserver at %s' % download_url)
            return False

        # create download_filename
        try:
            f = open(download_filename, 'w+b')
        except IOError as err:
            error('failed to create file %s: %s' % (download_filename,
                                                    err.strerror))
            return False

        with f:
            print_progress(download_filename, totalsize, 0)
            download_bytes = 0

            while True:
                data = web.read(4096)
                if not data:
                    break

                download_bytes += len(data)
                print_progress(download_filename, totalsize, download_bytes)

                f.write(data)
                if sha512_checksum is not None:
                    sum512.update(data)
                else:
                    sum5.update(data)
    finally:
        web.close()

    if download_bytes < totalsize:
        print
        error('failed to download file %s' % download_url)
        return False

    download_bytes += 100    # force 100% in the progress counter
    print_progress(download_filename, totalsize, download_bytes)

    if sha512_checksum is not None:
        if sum512.hexdigest() != sha512_checksum:
            error('checksum failed for %s' % download_filename)
            return False

    elif sum5.hexdigest() != md5_checksum:
        error('checksum failed for %s' % download_filename)
        return False

    return True

# EOB
