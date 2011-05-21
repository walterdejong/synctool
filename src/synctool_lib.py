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


# options (mostly) set by command-line arguments
DRY_RUN = False
VERBOSE = False
QUIET = False
UNIX_CMD = False
ERASE_SAVED = False
TERSE = True
COLORIZE = True
COLORIZE_BRIGHT = True
COLORIZE_FULL_LINE = False
MASTERLOG = False
LOGFD = None

# print nodename in output?
# This option is pretty useless except in synctool-ssh it may be useful
OPT_NODENAME = True

MONTHS = ( 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec' )

# enums for terse output
TERSE_INFO = 0
TERSE_WARNING = 1
TERSE_ERROR = 2
TERSE_FAIL = 3
TERSE_SYNC = 4
TERSE_LINK = 5
TERSE_MKDIR = 6
TERSE_DELETE = 7
TERSE_OWNER = 8
TERSE_MODE = 9
TERSE_EXEC = 10

TERSE_TXT = (
	'info', 'WARN', 'ERROR', 'FAIL',
	'sync', 'link', 'mkdir', 'rm', 'chown', 'chmod', 'exec'
)

TERSE_COLORS = {
	'info' : 'default',
	'WARN' : 'magenta',
	'ERROR': 'red',
	'FAIL' : 'cyan',
	'sync' : 'default',
	'link' : 'cyan',
	'mkdir': 'blue',		# I'd use yellow on a black background, blue on white
	'rm'   : 'yellow',
	'chown': 'cyan',
	'chmod': 'cyan',
	'exec' : 'green'
}

COLORMAP = {
	'black'   : 30,
	'darkgray': 30,
	'red'     : 31,
	'green'   : 32,
	'yellow'  : 33,
	'blue'    : 34,
	'magenta' : 35,
	'cyan'    : 36,
	'white'   : 37,
	'bold'    : 1,
	'default' : 0,
}


def verbose(str):
	'''do conditional output based on the verbose command line parameter'''

	if VERBOSE:
		print str


def stdout(str):
	if not (UNIX_CMD or TERSE):
		print str

	log(str)


def stderr(str):
	if not TERSE:
		print str
	log(str)


def terse(code, msg):
	if TERSE:
		# convert any path to terse path
		if string.find(msg, ' ') >= 0:
			arr = string.split(msg)
			if arr[-1][0] == '/':
				arr[-1] = terse_path(arr[-1])
				msg = string.join(arr)
		
		else:
			if msg[0] == '/':
				msg = terse_path(msg)
		
		if COLORIZE:		# and sys.stdout.isatty():
			txt = TERSE_TXT[code]
			color = COLORMAP[TERSE_COLORS[TERSE_TXT[code]]]
			
			if COLORIZE_BRIGHT:
				bright = ';1'
			else:
				bright = ''
			
			if COLORIZE_FULL_LINE:
				print '\x1b[%d%sm%s %s\x1b[0m' % (color, bright, txt, msg)
			else:
				print '\x1b[%d%sm%s\x1b[0m %s' % (color, bright, txt, msg)
		else:
			print TERSE_TXT[code], msg


def unix_out(str):
	'''output as unix shell command'''

	if UNIX_CMD:
		print str


def prettypath(path):
	'''print long paths as "$masterdir/path"'''
	
	return terse_path(path)
	
	if synctool_param.FULL_PATH:		# synctool.conf: full_path yes
		return path
	
	if path[:synctool_param.MASTER_LEN] == synctool_param.MASTERDIR + '/':
		return '$masterdir/' + path[synctool_param.MASTER_LEN:]
	
	return path


def terse_path(path, maxlen = 55):
	'''print long path as "//overlay/.../dir/file"'''
	
	if synctool_param.FULL_PATH:
		return path
	
	if path[:synctool_param.MASTER_LEN] == synctool_param.MASTERDIR + '/':
		path = '//' + path[synctool_param.MASTER_LEN:]
	
	if len(path) > maxlen:
		arr = string.split(path, '/')
		
		while len(arr) >= 3:
			idx = len(arr) / 2
			arr[idx] = '...'
			new_path = string.join(arr, '/')
			
			if len(new_path) > maxlen:
				arr.pop(idx)
			else:
				return new_path
	
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
	# TODO use subprocess, or else os.popen()

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
		return os.fdopen(pipe[0], 'r')
	
	return None


def run_with_nodename(cmd_arr, nodename):
	'''run command and show output with nodename'''
	
	f = popen(cmd_arr)
	if not f:
		return
	
	while True:
		line = f.readline()
		if not line:
			break
		
		line = string.strip(line)
		
		# pass output on; simply use 'print' rather than 'stdout()'
		if line[:15] == '%synctool-log% ':
			if line[15:] == '--':
				pass
			else:
				masterlog('%s: %s' % (nodename, line[15:]))
		else:
			if OPT_NODENAME:
				print '%s: %s' % (nodename, line)
			else:
				# do not prepend the nodename of this node to the output
				# if option --no-nodename was given
				print line
	
	f.close()


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


def strip_path(path):
	if not path:
		return path
	
	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)
	
	return path


def prepare_path(path):
	if not path:
		return path
	
	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)
	path = subst_masterdir(path)
	
	return path


def run_parallel(master_func, worker_func, args, worklen):
	'''runs a callback functions with arguments in parallel
	master_func is called in the master; worker_func is called in the worker
	master_func and worker_func are called with two arguments: rank, args
	All arguments 'args' are always passed; check the rank to see what rank
	this parallel process has
	worklen is the total amount of work items to be processed
	This function will not fork more than NUM_PROC processes'''
	
	# Note: I guess using Python's multiprocessing module would be
	# more elegant. However, it needs Python >= 2.6 and some systems
	# still ship with the older Python 2.4 (at the time of writing this)
	
	parallel = 0
	n = 0
	while n < worklen:
		if parallel > synctool_param.NUM_PROC:
			try:
				(pid, status) = os.wait()
			except OSError:
				# odd condition?
				pass
			
			else:
				parallel = parallel - 1
		
		try:
			pid = os.fork()
			if not pid:
				try:
					# the nth thread gets rank n
					worker_func(n, args)
				except KeyboardInterrupt:
					print
				
				sys.exit(0)
			
			if pid == -1:
				stderr('error: fork() failed, breaking off forking loop')
				break
			
			else:
				master_func(n, args)
				
				parallel = parallel + 1
				n = n + 1
		
		except KeyboardInterrupt:
			print
			break
	
	# wait for all children to terminate
	while True:
		try:
			(pid, status) = os.wait()
		except OSError:
			# no more child processes
			break
		
		except KeyboardInterrupt:
			print
			break


if __name__ == '__main__':
	print "synctool_lib doesn't do anything by itself, really"


# EOB
