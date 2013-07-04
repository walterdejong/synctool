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
import stat
import time
import errno
import time
import syslog
import signal
import multiprocessing
import Queue

import synctool.param

# options (mostly) set by command-line arguments
DRY_RUN = True
VERBOSE = False
QUIET = False
UNIX_CMD = False
NO_POST = False
MASTERLOG = False

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


def stderr(msg):
	print msg


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


def dryrun_msg(msg):
	'''print a "dry run" message filled to (almost) 80 chars'''

	if not DRY_RUN:
		return msg

	l1 = len(msg) + 4

	add = '# dry run'
	l2 = len(add)

	i = 0
	while i < 4:
		# format output; align columns by steps of 20
		col = 79 + i * 20
		if l1 + l2 <= col:
			return msg + (' ' * (col - (l1 + l2))) + add

		i += 1

	# else return a longer message
	return msg + '    ' + add


def openlog():
	if DRY_RUN or not synctool.param.SYSLOGGING:
		return

	syslog.openlog('synctool', 0, syslog.LOG_USER)


def closelog():
	if DRY_RUN or not synctool.param.SYSLOGGING:
		return

	log('--')
	syslog.closelog()


def _masterlog(msg):
	'''log only locally (on the master node)'''

	if DRY_RUN or not synctool.param.SYSLOGGING:
		return

	syslog.syslog(syslog.LOG_INFO|syslog.LOG_USER, msg)


def log(msg):
	'''log message to syslog'''

	if DRY_RUN or not synctool.param.SYSLOGGING:
		return

	if MASTERLOG:
		# print it with magic prefix,
		# synctool-master will pick it up
		print '%synctool-log%', msg
	else:
		_masterlog(msg)


def run_with_nodename(cmd_arr, nodename):
	'''run command and show output with nodename
	It will run regardless of what DRY_RUN is'''

	try:
		f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
	except OSError, reason:
		stderr('failed to run command %s: %s' % (cmd_arr[0], reason))
		return

	with f:
		for line in f:
			line = line.strip()

			# if output is a log line, pass it to the master's syslog
			if line[:15] == '%synctool-log% ':
				if line[15:] == '--':
					pass
				else:
					_masterlog('%s: %s' % (nodename, line[15:]))
			else:
				# pass output on; simply use 'print' rather than 'stdout()'
				if OPT_NODENAME:
					print '%s: %s' % (nodename, line)
				else:
					# do not prepend the nodename of this node to the output
					# if option --no-nodename was given
					print line


def shell_command(cmd):
	'''run a shell command
	Unless DRY_RUN is set'''

	if DRY_RUN:
		not_str = 'not '
	else:
		not_str = ''

	# a command can have arguments
	cmd_arr = shlex.split(cmd)
	cmdfile = cmd_arr[0]

	if not QUIET:
		stdout('%srunning command %s' % (not_str, prettypath(cmd)))

	verbose(dryrun_msg('  os.system(%s)' % prettypath(cmd)))
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
	'''like mkdir -p; make directory and subdirectories
	Returns False on error, else True'''

	# temporarily restore admin's umask
	mask = os.umask(synctool.param.ORIG_UMASK)

	ok = _mkdir_p(path)
	if not ok:
		stderr('error: failed to create directory %s' % path)

	os.umask(mask)
	return ok


def _mkdir_p(path):
	'''recursively make directory + leading directories'''

	# recursive function; do not print error messages here

	if not path:
		# this happens at the root of a relative path
		return True

	try:
		statbuf = os.stat(path)
	except OSError, reason:
		if reason.errno == errno.ENOENT:
			# path does not exist
			pass
		else:
			# stat() error
			return False
	else:
		# path already exists
		# check it's a directory, just to be sure
		if not stat.S_ISDIR(statbuf.st_mode):
			return False

		return True

	# recurse: make sure the parent directory exists
	if not _mkdir_p(os.path.dirname(path)):
		# there was an error
		return False

	try:
		os.mkdir(path)
	except OSError:
		return False

	return True


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
	# http://www.bryceboe.com/2010/08/26/ \
	#   python-multiprocessing-and-keyboardinterrupt/

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
