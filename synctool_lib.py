#! /usr/bin/env python
#
#	synctool_lib.py		WJ109
#
#	- common functions/variables for synctool suite programs
#

import time


DRY_RUN = 0
VERBOSE = 0
QUIET = 0
UNIX_CMD = 0
LOGFILE = None
LOGFD = None

MONTHS = ( 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec' )


def verbose(str):
	'''do conditional output based on the verbose command line parameter'''

	if VERBOSE:
		print str


def stdout(str):
	if not UNIX_CMD:
		print str

	log(str)


def stderr(str):
	print str
	log(str)


def unix_out(str):
	'''output as unix shell command'''

	if UNIX_CMD:
		print str


def openlog():
	global LOGFD

	if LOGFILE == None or LOGFILE == '' or DRY_RUN:
		return

	LOGFD = None
	try:
		LOGFD = open(LOGFILE, 'a')
	except IOError, (err, reason):
		print 'error: failed to open logfile %s : %s' % (filename, reason)
		sys.exit(-1)

#	log('start run')


def closelog():
	global LOGFD

	if LOGFD != None:
#		log('end run')
		log('--')

		LOGFD.close()
		LOGFD = None


def log(str):
	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' % (MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))


if __name__ == '__main__':
	print "synctool_lib doesn't do anything by itself, really"


# EOB
