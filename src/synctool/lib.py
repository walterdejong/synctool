#
#	synctool.lib.py		WJ109
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- common functions/variables for synctool suite programs
#

import os
import sys
import subprocess
import shlex
import time
import errno
import time
import signal
import multiprocessing
import Queue

import synctool.param

# options (mostly) set by command-line arguments
DRY_RUN = False
VERBOSE = False
QUIET = False
UNIX_CMD = False
NO_POST = False
MASTERLOG = False
LOGFD = None

# print nodename in output?
# This option is pretty useless except in synctool-ssh it may be useful
OPT_NODENAME = True

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
			'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

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
TERSE_UPLOAD = 11
TERSE_NEW = 12
TERSE_TYPE = 13
TERSE_DRYRUN = 14
TERSE_FIXING = 15
TERSE_OK = 16

TERSE_TXT = (
	'info', 'WARN', 'ERROR', 'FAIL',
	'sync', 'link', 'mkdir', 'rm', 'chown', 'chmod', 'exec',
	'upload', 'new', 'type', 'DRYRUN', 'FIXING', 'OK'
)

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


def verbose(msg):
	'''do conditional output based on the verbose command line parameter'''

	if VERBOSE:
		print msg


def stdout(msg):
	if not (UNIX_CMD or synctool.param.TERSE):
		print msg

	log(msg)


def stderr(msg):
	print msg
	log(msg)


def terse(code, msg):
	'''print short message + shortened filename'''

	if synctool.param.TERSE:
		# convert any path to terse path
		if msg.find(' ') >= 0:
			arr = msg.split()
			if arr[-1][0] == os.sep:
				arr[-1] = terse_path(arr[-1])
				msg = ' '.join(arr)

		else:
			if msg[0] == os.sep:
				msg = terse_path(msg)

		if synctool.param.COLORIZE:		# and sys.stdout.isatty():
			txt = TERSE_TXT[code]
			color = COLORMAP[synctool.param.TERSE_COLORS[
							TERSE_TXT[code].lower()]]

			if synctool.param.COLORIZE_BRIGHT:
				bright = ';1'
			else:
				bright = ''

			if synctool.param.COLORIZE_FULL_LINE:
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
	'''print long paths as "$overlay/path"'''

	if synctool.param.FULL_PATH:
		return path

	if synctool.param.TERSE:
		return terse_path(path)

	if path[:synctool.param.OVERLAY_LEN] == (synctool.param.OVERLAY_DIR +
											os.sep):
		return os.path.join('$overlay', path[synctool.param.OVERLAY_LEN:])

	if path[:synctool.param.DELETE_LEN] == (synctool.param.DELETE_DIR +
											os.sep):
		return os.path.join('$delete', path[synctool.param.DELETE_LEN:])

	return path


def terse_path(path, maxlen = 55):
	'''print long path as "//overlay/.../dir/file"'''

	if synctool.param.FULL_PATH:
		return path

	# by the way, this function will misbehave a bit for a _destination_
	# path named "/opt/synctool/var/" again
	# because this function doesn't know whether it is working with
	# a source or a destination path and it treats them both in the same way

	if path[:synctool.param.VAR_LEN] == (synctool.param.VAR_DIR +
										os.sep):
		path = os.sep + os.sep + path[synctool.param.VAR_LEN:]

	if len(path) > maxlen:
		arr = path.split(os.sep)

		while len(arr) >= 3:
			idx = len(arr) / 2
			arr[idx] = '...'
			new_path = os.sep.join(arr)

			if len(new_path) > maxlen:
				arr.pop(idx)
			else:
				return new_path

	return path


def dryrun_msg(str, action = 'update'):
	'''print a "dry run" message filled to (almost) 80 chars
	so that it looks nice on the terminal'''

	l1 = len(str) + 4

	msg = '# dry run, %s not performed' % action
	l2 = len(msg)

	if l1 + l2 <= 79:
		return str + (' ' * (79 - (l1 + l2))) + msg

	if l1 + 13 <= 79:
		# message is long, but we can shorten and it will fit on a line
		msg = '# dry run'
		l2 = 9
		return str + (' ' * (79 - (l1 + l2))) + msg

	# don't bother, return a long message
	return str + '    ' + msg


def openlog():
	global LOGFD

	if DRY_RUN or not synctool.param.LOGFILE:
		return

	LOGFD = None
	try:
		LOGFD = open(synctool.param.LOGFILE, 'a')
	except IOError, reason:
		print ('error: failed to open logfile %s : %s' %
			(synctool.param.LOGFILE, reason))
		sys.exit(-1)

#	log('start run')


def closelog():
	global LOGFD

	if LOGFD != None:
#		log('end run')
		log('--')

		LOGFD.close()
		LOGFD = None


def masterlog(msg):
	'''log only locally (on the masternode)'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' %
			(MONTHS[t[1]-1], t[2], t[3], t[4], t[5], msg))


def log(msg):
	'''log message locally, and print it so that synctool-master will pick it up'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' %
			(MONTHS[t[1]-1], t[2], t[3], t[4], t[5], msg))

		if MASTERLOG:
			print '%synctool-log%', msg


def run_with_nodename(cmd_arr, nodename):
	'''run command and show output with nodename'''

	try:
		f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
	except OSError, reason:
		stderr('failed to run command %s: %s' % (cmd_arr[0], reason))
		return

	with f:
		while True:
			line = f.readline()
			if not line:
				break

			line = line.strip()

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


def shell_command(cmd):
	'''run a shell command'''

	if DRY_RUN:
		not_str = 'not '
	else:
		not_str = ''

	# a command can have arguments
	cmd_arr = shlex.split(cmd)
	cmdfile = cmd_arr[0]

	if not QUIET:
		stdout('%srunning command %s' % (not_str, prettypath(cmd)))

	verbose(dryrun_msg('  os.system("%s")' % prettypath(cmd), 'action'))
	unix_out('# run command %s' % cmdfile)
	unix_out(cmd)
	terse(TERSE_EXEC, cmdfile)

	if not DRY_RUN:
		sys.stdout.flush()
		sys.stderr.flush()

		try:
			subprocess.call(cmd, shell=True)
		except OSError, reason:
			stderr("failed to run shell command '%s' : %s" %
				(prettypath(cmd), reason))

		sys.stdout.flush()
		sys.stderr.flush()


def search_path(cmd):
	'''search the PATH for the location of cmd'''

	if cmd.find(os.sep) >= 0 or (os.altsep != None and
								cmd.find(os.altsep) >= 0):
		return cmd

	path = os.environ['PATH']
	if not path:
		path = os.pathsep.join(['/bin', '/sbin', '/usr/bin', '/usr/sbin',
			'/usr/local/bin', '/usr/local/sbin'])

	for d in path.split(os.pathsep):
		full_path = os.path.join(d, cmd)
		if os.access(full_path, os.X_OK):
			return full_path

	return None


def mkdir_p(path):
	'''like mkdir -p; make directory and subdirectories'''

	# note: this function does not change the umask

	arr = path.split(os.sep)
	if arr[0] == '':
		# first element is empty; this happens when path starts with '/'
		arr.pop(0)

	if not arr:
		return

	# 'walk' the path
	mkdir_path = ''
	for elem in arr:
		mkdir_path = os.path.join(mkdir_path, elem)

		# see if the directory already exists
		try:
			os.stat(mkdir_path)
		except OSError, err:
			if err.errno == errno.ENOENT:
				pass
			else:
				# odd ...
				stderr('error: stat(%s): %s' % (mkdir_path, err))
				# and what now??
		else:
			# no error from stat(), directory already exists
			continue

		# make the directory
		try:
			os.mkdir(mkdir_path)		# uses the default umask
		except OSError, err:
			if err.errno == errno.EEXIST:
				# "File exists" (it's a directory, but OK)
				# this is unexpected, but still possible
				continue

			stderr('error: mkdir(%s) failed: %s' % (mkdir_path, err))


#
# functions straigthening out paths that were given by the user
#
def strip_multiple_slashes(path):
	if not path:
		return path

	double = os.sep + os.sep
	while path.find(double) != -1:
		path = path.replace(double, os.sep)

	if os.path.altsep:
		double = os.path.altsep + os.path.altsep
		while path.find(double) != -1:
			path = path.replace(double, os.sep)

	return path


def strip_trailing_slash(path):
	if not path:
		return path

	while len(path) > 1 and path[-1] == os.sep:
		path = path[:-1]

	return path


def strip_path(path):
	if not path:
		return path

	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)

	return path


def strip_terse_path(path):
	if not path:
		return path

	if not synctool.param.TERSE:
		return strip_path(path)

	# terse paths may start with two slashes
	if len(path) >= 2 and path[:1] == '//':
		is_terse = True
	else:
		is_terse = False

	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)

	# the first slash was accidentally stripped, so restore it
	if is_terse:
		path = os.sep + path

	return path


def prepare_path(path):
	if not path:
		return path

	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)
	path = path.replace('$SYNCTOOL/', synctool.param.ROOTDIR + os.sep)
	return path


def multiprocess(fn, work):
	'''run a function in parallel'''

	# Thanks go to Bryce Boe
	# http://www.bryceboe.com/2010/08/26/python-multiprocessing-and-keyboardinterrupt/

	if synctool.param.SLEEP_TIME != 0:
		synctool.param.NUM_PROC = 1

	# make a work queue
	jobq = multiprocessing.Queue()
	for item in work:
		jobq.put(item)

	# start NUMPROC worker processes
	pool = []
	i = 0
	while i < synctool.param.NUM_PROC:
		p = multiprocessing.Process(target=_worker, args=(fn, jobq))
		pool.append(p)
		p.start()
		i += 1

	try:
		for p in pool:
			p.join()

	except KeyboardInterrupt:
		# user hit Ctrl-C
		# terminate all workers
		for p in pool:
			p.terminate()
			p.join()

		# re-raise KeyboardInterrupt, for __main__ to catch
		raise


def _worker(fn, jobq):
	'''fn is the worker function to call
	jobq is a multiprocessing.Queue of function arguments
	If --zzz was given, sleep after finishing the work
	No return value is passed back'''

	# ignore interrupts, ignore Ctrl-C
	# the Ctrl-C will be caught by the parent process
	signal.signal(signal.SIGINT, signal.SIG_IGN)

	while not jobq.empty():
		try:
			arg = jobq.get(block=False)
		except Queue.Empty:
			break

		else:
			fn(arg)

			if synctool.param.SLEEP_TIME > 0:
				time.sleep(synctool.param.SLEEP_TIME)


if __name__ == '__main__':
	# __main__ is needed because of multiprocessing module
	pass


# EOB
