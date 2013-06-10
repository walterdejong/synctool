#
#	synctool_lib.py		WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- common functions/variables for synctool suite programs
#

import os
import sys
import string
import time
import shlex
import errno

try:
	import hashlib
	use_hashlib = True
except ImportError:
	import md5
	use_hashlib = False

try:
	import subprocess
	use_subprocess = True
except ImportError:
	use_subprocess = False

import synctool.param


# blocksize for doing I/O while checksumming files
BLOCKSIZE = 16 * 1024

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

MONTHS = ( 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct',
		'Nov','Dec' )

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


def verbose(str):
	'''do conditional output based on the verbose command line parameter'''

	if VERBOSE:
		print str


def stdout(str):
	if not (UNIX_CMD or synctool.param.TERSE):
		print str

	log(str)


def stderr(str):
	print str
	log(str)


def terse(code, msg):
	'''print short message + shortened filename'''

	if synctool.param.TERSE:
		# convert any path to terse path
		if string.find(msg, ' ') >= 0:
			arr = string.split(msg)
			if arr[-1][0] == os.path.sep:
				arr[-1] = terse_path(arr[-1])
				msg = string.join(arr)

		else:
			if msg[0] == os.path.sep:
				msg = terse_path(msg)

		if synctool.param.COLORIZE:		# and sys.stdout.isatty():
			txt = TERSE_TXT[code]
			color = COLORMAP[synctool.param.TERSE_COLORS[
							string.lower(TERSE_TXT[code])]]

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
	'''print long paths as "$masterdir/path"'''

	if synctool.param.FULL_PATH:
		return path

	if synctool.param.TERSE:
		return terse_path(path)

	if path[:synctool.param.MASTER_LEN] == (synctool.param.MASTERDIR +
											os.path.sep):
		return os.path.join('$masterdir', path[synctool.param.MASTER_LEN:])

	return path


def terse_path(path, maxlen = 55):
	'''print long path as "//overlay/.../dir/file"'''

	if synctool.param.FULL_PATH:
		return path

	# by the way, this function will misbehave a bit for a _destination_
	# path named "/var/lib/synctool/" again
	# because this function doesn't know whether it is working with
	# a source or a destination path and it treats them both in the same way

	if path[:synctool.param.MASTER_LEN] == (synctool.param.MASTERDIR +
											os.path.sep):
		path = os.path.sep + os.path.sep + path[synctool.param.MASTER_LEN:]

	if len(path) > maxlen:
		arr = string.split(path, os.path.sep)

		while len(arr) >= 3:
			idx = len(arr) / 2
			arr[idx] = '...'
			new_path = string.join(arr, os.path.sep)

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
	except IOError, (err, reason):
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


def masterlog(str):
	'''log only locally (on the masternode)'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' %
			(MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))


def log(str):
	'''log message locally, and print it so that synctool-master will pick it up'''

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' %
			(MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))

		if MASTERLOG:
			print '%synctool-log%', str


def checksum_files(file1, file2):
	'''do a quick checksum of 2 files'''

	err = None
	reason = None
	try:
		f1 = open(file1, 'r')
	except IOError, (err, reason):
		stderr('error: failed to open %s : %s' % (file1, reason))
		raise

	try:
		f2 = open(file2, 'r')
	except IOError, (err, reason):
		stderr('error: failed to open %s : %s' % (file2, reason))
		raise

	if use_hashlib:
		sum1 = hashlib.md5()
		sum2 = hashlib.md5()
	else:
		sum1 = md5.new()
		sum2 = md5.new()

	len1 = len2 = 0
	ended = False
	while len1 == len2 and sum1.digest() == sum2.digest() and not ended:
		data1 = f1.read(BLOCKSIZE)
		if not data1:
			ended = True
		else:
			len1 = len1 + len(data1)
			sum1.update(data1)

		data2 = f2.read(BLOCKSIZE)
		if not data2:
			ended = True
		else:
			len2 = len2 + len(data2)
			sum2.update(data2)

		if sum1.digest() != sum2.digest():
			# checksum mismatch; early exit
			break

	f1.close()
	f2.close()
	return sum1.digest(), sum2.digest()


def popen(cmd_arr):
	'''same as os.popen(), but use an array of command+arguments'''

	if use_subprocess:
		try:
			f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
		except OSError:
			f = None

		return f

	# we do not have subprocess module (Python version < 2.4, very old)

	pipe = os.pipe()

	pid = os.fork()
	if not pid:
		# redirect child's output to write end of the pipe
		os.close(2)
		os.close(1)
		os.dup2(pipe[1], 1)
		os.dup2(pipe[1], 2)

		os.close(pipe[0])

		cmd = cmd_arr.pop(0)
		cmd = search_path(cmd)
		cmd_arr.insert(0, cmd)

		try:
			os.execv(cmd, cmd_arr)
		except OSError, reason:
			stderr("failed to run '%s': %s" % (cmd, reason))

		sys.exit(1)

	if pid == -1:
		return None

	os.close(pipe[1])
	return os.fdopen(pipe[0], 'r')


def run_with_nodename(cmd_arr, nodename):
	'''run command and show output with nodename'''

	f = popen(cmd_arr)
	if not f:
		stderr('failed to run command %s' % cmd_arr[0])
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

	terse(TERSE_EXEC, cmdfile)
	unix_out('# run command %s' % cmdfile)
	unix_out(cmd)

	if not DRY_RUN:
		verbose('  os.system("%s")' % prettypath(cmd))

		sys.stdout.flush()
		sys.stderr.flush()

		if use_subprocess:
			try:
				subprocess.call(cmd, shell=True)
			except OSError, reason:
				stderr("failed to run shell command '%s' : %s" %
					(prettypath(cmd), reason))
		else:
			try:
				os.system(cmd)
			except OSError, reason:
				stderr("failed to run shell command '%s' : %s" %
					(prettypath(cmd), reason))

		sys.stdout.flush()
		sys.stderr.flush()
	else:
		verbose(dryrun_msg('  os.system("%s")' % prettypath(cmd), 'action'))


def search_path(cmd):
	'''search the PATH for the location of cmd'''

	if string.find(cmd, os.sep) >= 0 or (os.altsep != None and
		string.find(cmd, os.altsep) >= 0):
		return cmd

	path = os.getenv('PATH')

	if not path:
		path = '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin'

	for d in string.split(path, os.pathsep):
		full_path = os.path.join(d, cmd)
		if os.path.isfile(full_path):
			return full_path

	return cmd


def mkdir_p(path):
	'''like mkdir -p; make directory and subdirectories'''

	# note: this function does not change the umask

	arr = string.split(path, os.path.sep)
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

	double = os.path.sep + os.path.sep
	while path.find(double) != -1:
		path = path.replace(double, os.path.sep)

	if os.path.altsep:
		double = os.path.altsep + os.path.altsep
		while path.find(double) != -1:
			path = path.replace(double, os.path.sep)

	return path


def strip_trailing_slash(path):
	if not path:
		return path

	while len(path) > 1 and path[-1] == os.path.sep:
		path = path[:-1]

	return path


def subst_masterdir(path):
	master = '$masterdir' + os.path.sep
	if path.find(master) >= 0:
		if not synctool.param.MASTERDIR:
			stderr('error: $masterdir referenced before it was set')
			sys.exit(-1)

	return path.replace(master, synctool.param.MASTERDIR + os.path.sep)


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
		isTerse = True
	else:
		isTerse = False

	path = strip_multiple_slashes(path)
	path = strip_trailing_slash(path)

	# the first slash was accidentally stripped, so restore it
	if isTerse:
		path = os.path.sep + path

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
		if parallel > synctool.param.NUM_PROC:
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

				parallel += 1
				n += 1

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


# EOB
