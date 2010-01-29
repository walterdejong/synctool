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

import string
import urllib

VERSION_CHECKING_URL = 'http://www.heiho.net/synctool/LATEST.txt'


def check():
	'''check for newer version on the website'''
	'''it does this by downloading the LATEST.txt versioning file'''

	verbose('accessing URL %s' % VERSION_CHECKING_URL)

	try:
		opener = urllib.FancyURLopener({})
		f = opener.open(VERSION_CHECKING_URL)
		data = f.read()	
		f.close()
	except:
		stderr('error accessing the file at %s' % VERSION_CHECKING_URL)
		return 2

	if data[0] == '<':
		stderr('error accessing the file at %s' % VERSION_CHECKING_URL)
		return 2

	data = string.strip(data)

	if data == synctool_config.VERSION:
		stdout('You are running the latest version of synctool')
		return 0
	else:
		stdout('A newer version of synctool is available: version %s' % data)

	return 1


if __name__ == '__main__':
	check()


# EOB
