#! /usr/bin/env python
#
#	synctool_lib.py		WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- common functions/variables for synctool suite programs
#

import synctool_param

import os
import sys
import string
import time


DRY_RUN = False
VERBOSE = False
QUIET = False
UNIX_CMD = False
MASTERLOG = False
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


def prettypath(path):
	'''print long paths as "$masterdir/path"'''
	
	if path[:synctool_param.MASTER_LEN] == synctool_param.MASTERDIR + '/':
		return '$masterdir/' + path[synctool_param.MASTER_LEN:]
	
	return path


def openlog():
	global LOGFD

	if synctool_param.LOGFILE == None or synctool_param.LOGFILE == '' or DRY_RUN:
		return

	LOGFD = None
	try:
		LOGFD = open(synctool_param.LOGFILE, 'a')
	except IOError, (err, reason):
		print 'error: failed to open logfile %s : %s' % (synctool_param.LOGFILE, reason)
		sys.exit(-1)

#	log('start run')


def closelog():
	global LOGFD

	if LOGFD != None:
#		log('end run')
		log('--')

		LOGFD.close()
		LOGFD = None


def masterlog(str):
	'''log only locally (on the masternode)'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' % (MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))


def log(str):
	'''log message locally, and print it so that synctool-master will pick it up'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' % (MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))

		if MASTERLOG:
			print '%synctool-log%', str


def popen(cmd_args):
	'''same as os.popen(), but use an array of command+arguments'''

	pipe = os.pipe()

	if not os.fork():
		# redirect child's output to write end of the pipe
		os.close(2)
		os.close(1)
		os.dup2(pipe[1], 1)
		os.dup2(pipe[1], 2)

		os.close(pipe[0])

		cmd = cmd_args.pop(0)
		cmd = search_path(cmd)
		cmd_args.insert(0, cmd)

		try:
			os.execv(cmd, cmd_args)
		except OSError, reason:
			stderr("failed to run '%s': %s" % (cmd, reason))

		sys.exit(1)

	else:
		os.close(pipe[1])

		f = os.fdopen(pipe[0], 'r')

		return f

	return None


def search_path(cmd):
	'''search the PATH for the location of cmd'''
	
	# NB. I'm sure this will fail miserably on the Windows platform
	# ah well
	
	if string.find(cmd, '/') >= 0:
		return cmd

	path = os.getenv('PATH')

	if not path:
		path = '/bin:/usr/bin'

	for d in string.split(path, os.pathsep):
		full_path = os.path.join(d, cmd)
		if os.path.isfile(full_path):
			return full_path

	return cmd


#
#	functions straigthening out paths that were given by the user
#
def strip_multiple_slashes(path):
	if not path:
		return path
	
	while path.find('//') != -1:
		path = path.replace('//', '/')
	
	return path


def strip_trailing_slash(path):
	if not path:
		return path
	
	while len(path) > 1 and path[-1] == '/':
		path = path[:-1]
	
	return path


def subst_masterdir(path):
	if path.find('$masterdir/') >= 0:
		if not synctool_param.MASTERDIR:
			stderr('error: $masterdir referenced before it was set')
			sys.exit(-1)
	
	return path.replace('$masterdir/', synctool_param.MASTERDIR + '/')


def prepare_path(path):
	if not path:
		return path
	
	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)
	path = subst_masterdir(path)
	
	return path


if __name__ == '__main__':
	print "synctool_lib doesn't do anything by itself, really"


# EOB
