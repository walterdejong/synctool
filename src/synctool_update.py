#! /usr/bin/env python
#
#	synctool_update.py	WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2010
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_config

from synctool_lib import verbose,stdout,stderr

import os
import sys
import string
import urllib

try:
	import hashlib
	use_hashlib = True
except ImportError:
	import md5
	use_hashlib = False


VERSION_CHECKING_URL = 'http://www.heiho.net/synctool/LATEST.txt'
DOWNLOAD_URL = 'http://www.heiho.net/synctool/'

# globals for callback function when downloading a release
DOWNLOAD_FILENAME = None
DOWNLOAD_BYTES = 0


def get_latest_version():
	'''get latest version by downloading the LATEST.txt versioning file'''

	tup = get_latest_version_and_checksum()
	if not tup:
		return None

	return tup[0]


def get_latest_version_and_checksum():
	'''get latest version and checksum by downloading the LATEST.txt versioning file'''

	verbose('accessing URL %s' % VERSION_CHECKING_URL)

	try:
		opener = urllib.FancyURLopener({})
		f = opener.open(VERSION_CHECKING_URL)
		data = f.read()	
		f.close()
	except:
		stderr('error accessing the file at %s' % VERSION_CHECKING_URL)
		return None

	if data[0] == '<':
		stderr('error accessing the file at %s' % VERSION_CHECKING_URL)
		return None

	data = string.strip(data)

# format of the data in LATEST.txt is:
# <version> <MD5 checksum>
	arr = string.split(data)
	if len(arr) != 2:
		return None
	
	return (arr[0], arr[1])


def check():
	'''check for newer version on the website'''
	'''it does this by downloading the LATEST.txt versioning file'''

	latest_version = get_latest_version()

	if latest_version == synctool_config.VERSION:
		stdout('You are running the latest version of synctool')
		return 0
	else:
		stdout('A newer version of synctool is available: version %s' % latest_version)

	return 1


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

		n = n + 1


def download_progress(seqnumber, blocksize, totalsize):
	'''print the download progress'''

	global DOWNLOAD_BYTES

	percent = 100 * DOWNLOAD_BYTES / totalsize
	if percent > 100:
		percent = 100

	print '\rdownloading %s ... %d%% ' % (DOWNLOAD_FILENAME, percent),
	sys.stdout.flush()

	DOWNLOAD_BYTES = DOWNLOAD_BYTES + blocksize


def download():
	'''download latest version'''

	global DOWNLOAD_FILENAME, DOWNLOAD_BYTES			# ugly globals because of callback function

	tup = get_latest_version_and_checksum()
	if not tup:
		return 1

	(version, checksum) = tup

	filename = 'synctool-%s.tar.gz' % version
	download_url = DOWNLOAD_URL + filename

	DOWNLOAD_FILENAME = make_local_filename_for_version(version)
	DOWNLOAD_BYTES = 0

	try:
		opener = urllib.FancyURLopener({})
		opener.retrieve(download_url, DOWNLOAD_FILENAME, download_progress)
	except:
		if DOWNLOAD_BYTES:
			print

		stderr('failed to download file %s' % download_url)
		return 1
	else:
		print
#
#	compute and compare MD5 checksums
#	sadly, there is no easy way to do this 'live' while downloading,
#	because the download callback does not see the downloaded data blocks
#
	downloaded_sum = checksum_file(DOWNLOAD_FILENAME)
	if downloaded_sum != checksum:
		stderr('ERROR: checksum failed for %s' % DOWNLOAD_FILENAME)
		return 1

	return 0


def checksum_file(filename):
	'''compute MD5 checksum of a file'''

	try:
		f = open(filename, 'r')
	except IOError(err, reason):
		stderr('error: failed to open %s : %s' % (filename, reason))
		raise

	if use_hashlib:
		sum1 = hashlib.md5()
	else:
		sum1 = md5.new()

	BLOCKSIZE = 16 * 1024

	while True:
		data = f.read(BLOCKSIZE)
		if not data:
			break

		sum1.update(data)

	f.close()
	return sum1.hexdigest()


if __name__ == '__main__':
	check()
#	download()


# EOB
