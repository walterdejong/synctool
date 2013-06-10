#! /usr/bin/env python
#
#	synctool_aggr.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- aggregate: group together output that is the same
#

from synctool_lib import popen

import os
import sys
import string
import getopt

import synctool.aggr


def usage():
	print 'Typical use of synctool-aggr is:'
	print
	print '  command | synctool-aggr'
	print
	print 'synctool-aggr is built in to synctool-master and synctool-ssh'
	print "and activated by the '-a' option"
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2009-2013'


def get_options():
	if len(sys.argv) <= 1:
		return

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'h', ['help'])
	except getopt.error, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)

	except getopt.GetoptError, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)

	except:
		usage()
		sys.exit(1)

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)


if __name__ == '__main__':
	get_options()

	synctool.aggr.aggregate(sys.stdin)


# EOB
