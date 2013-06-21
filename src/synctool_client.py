#! /usr/bin/env python
#
#	synctool	WJ103
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import sys
import time
import shlex
import getopt
import errno
import subprocess

import synctool.config
import synctool.lib
from synctool.lib import verbose, stdout, stderr, terse, unix_out
import synctool.overlay
import synctool.param
import synctool.syncstat

# get_options() returns these action codes
ACTION_DEFAULT = 0
ACTION_DIFF = 1
ACTION_ERASE_SAVED = 2
ACTION_REFERENCE = 3

SINGLE_FILES = []

# list of changed directories
# This is for running .post scripts on changed directories
# every element is a tuple: (src_path, dest_path)
DIR_CHANGED = []


def run_command(cmd):
	'''run a shell command'''

	# a command can have arguments
	arr = shlex.split(cmd)
	cmdfile = arr[0]

	stat = synctool.syncstat.SyncStat(cmdfile)

	if not stat.exists():
		stderr('error: command %s not found' %
			synctool.lib.prettypath(cmdfile))
		return

	if not stat.is_exec():
		stderr("warning: file '%s' is not executable" %
			synctool.lib.prettypath(cmdfile))
		return

	# run the shell command
	synctool.lib.shell_command(cmd)


def run_command_in_dir(dest_dir, cmd):
	'''change directory to dest_dir, and run the shell command'''

	verbose('  os.chdir(%s)' % dest_dir)
	unix_out('cd %s' % dest_dir)

	cwd = os.getcwd()

	# if dry run, the target directory may not exist yet
	# (mkdir has not been called for real, for a dry run)
	if synctool.lib.DRY_RUN:
		run_command(cmd)

		verbose('  os.chdir(%s)' % cwd)
		unix_out('cd %s' % cwd)
		unix_out('')
		return

	try:
		os.chdir(dest_dir)
	except OSError, reason:
		stderr('error changing directory to %s: %s' % (dest_dir, reason))
	else:
		run_command(cmd)

		verbose('  os.chdir(%s)' % cwd)
		unix_out('cd %s' % cwd)
		unix_out('')

		try:
			os.chdir(cwd)
		except OSError, reason:
			stderr('error changing directory to %s: %s' % (cwd, reason))


def run_post(src, dest):
	'''run any on_update or .post script commands for destination path'''

	if synctool.lib.NO_POST:
		return

	stat = synctool.syncstat.SyncStat(dest)

	if stat.is_dir():
		# directories will be handled later, so save this pair
		pair = (src, dest)
		DIR_CHANGED.append(pair)
		return

	dest_dir = os.path.dirname(dest)

	# file has changed, run appropriate .post script
	postscript = synctool.overlay.postscript_for_path(src, dest)
	if postscript:
		run_command_in_dir(dest_dir, postscript)

	# content of directory was changed, so save this pair
	pair = (os.path.dirname(src), dest_dir)
	if not pair in DIR_CHANGED:
		DIR_CHANGED.append(pair)


def run_post_on_directory(src, dest):
	'''run .post script for a changed directory'''

	if synctool.lib.NO_POST:
		return

	# the script is executed with the changed dir as current working dir

	# run appropriate .post script
	postscript = synctool.overlay.postscript_for_path(src, dest)
	if postscript:
		run_command_in_dir(dest, postscript)


def sort_directory_pair(a, b):
	'''sort function for directory pairs
	a and b are directory pair tuples: (src, dest)
	sort the deepest destination directories first'''

	n = -cmp(len(a[1]), len(b[1]))
	if not n:
		return cmp(a[1], b[1])

	return n


def run_post_on_directories():
	'''run pending .post scripts on directories that were changed'''

	if synctool.lib.NO_POST:
		return

	global DIR_CHANGED

	# sort by dest_dir with deepest dirs first
	DIR_CHANGED.sort(sort_directory_pair)

	# run .post scripts on every dir
	# Note how you can have multiple sources for the same destination,
	# and this triggers all .post scripts for those sources
	for (src, dest) in DIR_CHANGED:
		run_post_on_directory(src, dest)

	# they have run, now cleanup DIR_CHANGED
	DIR_CHANGED = {}


def overlay_callback(obj):
	'''compare files and run post-script if needed'''

	verbose('checking %s' % obj.print_src())

	if obj.compare_files():
		run_post(obj.src_path, obj.dest_path)


def overlay_files():
	'''run the overlay function'''

	synctool.overlay.visit(synctool.overlay.OV_OVERLAY, overlay_callback)


def delete_callback(obj):
	'''delete files'''

	if obj.dest_is_dir():		# do not delete directories
		return

	if obj.dest_exists():
		if synctool.lib.DRY_RUN:
			not_str = 'not '
		else:
			not_str = ''

		stdout('%sdeleting %s : %s' % (not_str, obj.print_src(),
										obj.print_dest()))
		obj.hard_delete_file()
		run_post(obj.src_path, obj.dest_path)


def delete_files():
	synctool.overlay.visit(synctool.overlay.OV_DELETE, delete_callback)


def erase_saved_callback(obj):
	'''erase *.saved backup files'''

	# really, this is all

	obj.erase_saved()


def erase_saved():
	'''List and delete *.saved backup files'''

	synctool.overlay.visit(synctool.overlay.OV_OVERLAY, erase_saved_callback)


def single_files(filename):
	'''check/update a single file
	Returns (True, path_in_synctree) if file is different'''

	if not filename:
		stderr('missing filename')
		return (False, None)

	(obj, err) = synctool.overlay.find_terse(
					synctool.overlay.OV_OVERLAY, filename)
	if err == synctool.overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)

	if err == synctool.overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return (False, None)

	verbose('checking against %s' % obj.print_src())

	changed = obj.compare_files()
	if not changed:
		stdout('%s is up to date' % filename)
		terse(synctool.lib.TERSE_OK, filename)
		unix_out('# %s is up to date\n' % obj.print_dest())

	return (changed, obj.src_path)


def single_erase_saved(filename):
	'''erase a single backup file'''

	if not filename:
		stderr('missing filename')
		return (False, None)

	(obj, err) = synctool.overlay.find_terse(
					synctool.overlay.OV_OVERLAY, filename)
	if err == synctool.overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)

	if err == synctool.overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return (False, None)

	obj.erase_saved()


def reference(filename):
	'''show which source file in the repository synctool chooses to use'''

	if not filename:
		stderr('missing filename')
		return

	(obj, err) = synctool.overlay.find_terse(
		synctool.overlay.OV_OVERLAY, filename)
	if err == synctool.overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)

	if err == synctool.overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return

	print obj.print_src()


def diff_files(filename):
	'''display a diff of the file'''

	if not synctool.param.DIFF_CMD:
		stderr('error: diff_cmd is undefined in %s' %
			synctool.param.CONF_FILE)
		return

	# be sure that it doesn't do any updates
	synctool.lib.DRY_RUN = True

	(obj, err) = synctool.overlay.find_terse(
		synctool.overlay.OV_OVERLAY, filename)
	if err == synctool.overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)

	if err == synctool.overlay.OV_NOT_FOUND:
		return

	if synctool.lib.UNIX_CMD:
		unix_out('%s %s %s' % (synctool.param.DIFF_CMD,
								obj.dest_path, obj.src_path))
	else:
		verbose('%s %s %s' % (synctool.param.DIFF_CMD,
								obj.dest_path, obj.print_src()))
		sys.stdout.flush()
		sys.stderr.flush()

		cmd_arr = shlex.split(synctool.param.DIFF_CMD)
		cmd_arr.append(obj.dest_path)
		cmd_arr.append(obj.src_path)
		try:
			subprocess.call(cmd_arr, shell=False)
		except OSError, reason:
			stderr('failed to run diff_cmd: %s' % reason)

		sys.stdout.flush()
		sys.stderr.flush()


def be_careful_with_getopt():
	'''check sys.argv for dangerous common typo's on the command-line'''

	# be extra careful with possible typo's on the command-line
	# because '-f' might run --fix because of the way that getopt() works

	for arg in sys.argv:

		# This is probably going to give stupid-looking output
		# in some cases, but it's better to be safe than sorry

		if arg[:2] == '-d' and arg.find('f') > -1:
			print "Did you mean '--diff'?"
			sys.exit(1)

		if arg[:2] == '-r' and arg.find('f') > -1:
			if arg.count('e') >= 2:
				print "Did you mean '--reference'?"
			else:
				print "Did you mean '--ref'?"
			sys.exit(1)


def	option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
	opt_upload, opt_suffix, opt_fix):

	'''some combinations of command-line options don't make sense;
	alert the user and abort'''

	if opt_erase_saved and (opt_diff or opt_reference or opt_upload):
		stderr("option --erase-saved can not be combined with other actions")
		sys.exit(1)

	if opt_upload and (opt_diff or opt_single or opt_reference):
		stderr("option --upload can not be combined with other actions")
		sys.exit(1)

	if opt_suffix and not opt_upload:
		stderr("option --suffix can only be used together with --upload")
		sys.exit(1)

	if opt_diff and (opt_single or opt_reference or opt_fix):
		stderr("option --diff can not be combined with other actions")
		sys.exit(1)

	if opt_reference and (opt_single or opt_fix):
		stderr("option --reference can not be combined with other actions")
		sys.exit(1)


def check_cmd_config():
	'''check whether the commands as given in synctool.conf actually exist'''

	(ok, synctool.param.DIFF_CMD) = synctool.config.check_cmd_config(
									'diff_cmd', synctool.param.DIFF_CMD)
	if not ok:
		sys.exit(-1)


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file'
	print ('                        (default: %s)' %
		synctool.param.DEFAULT_CONF)
	print '''  -d, --diff=file       Show diff for file
  -1, --single=file     Update a single file
  -r, --ref=file        Show which source file synctool chooses
  -e, --erase-saved     Erase *.saved backup files
  -f, --fix             Perform updates (otherwise, do dry-run)
      --no-post         Do not run any .post scripts
  -F, --fullpath        Show full paths instead of shortened ones
  -T, --terse           Show terse, shortened paths
      --color           Use colored output (only for terse mode)
      --no-color        Do not color output
      --unix            Output actions as unix shell commands
  -v, --verbose         Be verbose
  -q, --quiet           Suppress informational startup messages
      --version         Print current version number

synctool can help you administer your cluster of machines
Note that synctool does a dry run unless you specify --fix
'''


def get_options():
	global SINGLE_FILES

	progname = os.path.basename(sys.argv[0])

	synctool.lib.DRY_RUN = True		# set default dry-run

	# check for dangerous common typo's on the command-line
	be_careful_with_getopt()

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:d:1:r:efFTvq',
			['help', 'conf=', 'diff=', 'single=', 'ref=',
			'erase-saved', 'fix', 'no-post', 'fullpath',
			'terse', 'color', 'no-color',
			'verbose', 'quiet', 'unix', 'masterlog', 'nodename=', 'version'])
	except getopt.error, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)

	except getopt.GetoptError, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)

	except:
		usage()
		sys.exit(1)

	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command line')
		sys.exit(1)

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool.param.CONF_FILE = arg
			continue

		if opt == '--version':
			print synctool.param.VERSION
			sys.exit(0)

	# first read the config file
	synctool.config.read_config()
	check_cmd_config()

	if not synctool.param.TERSE:
		# giving --terse changes program behavior as early as
		# in the get_options() loop itself, so set it here already
		for opt, args in opts:
			if opt in ('-T', '--terse'):
				synctool.param.TERSE = True
				synctool.param.FULL_PATH = False
				continue

			if opt in ('-F', '--fullpath'):
				synctool.param.FULL_PATH = True
				continue

	# then go process all the other options
	errors = 0

	action = ACTION_DEFAULT
	SINGLE_FILES = []

	# these are only used for checking the validity of option combinations
	opt_diff = False
	opt_single = False
	opt_reference = False
	opt_erase_saved = False
	opt_upload = False
	opt_suffix = False
	opt_fix = False

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?', '-c', '--conf',
			'-T', '--terse', '-F', '--fullpath', '--version'):
			# already done
			continue

# dry run already is default
#
#		if opt in ('-n', '--dry-run'):
#			synctool.lib.DRY_RUN = True
#			continue

		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool.lib.DRY_RUN = False
			continue

		if opt == '--no-post':
			synctool.lib.NO_POST = True
			continue

		if opt == '--color':
			synctool.param.COLORIZE = True
			continue

		if opt == '--no-color':
			synctool.param.COLORIZE = False
			continue

		if opt in ('-v', '--verbose'):
			synctool.lib.VERBOSE = True
			continue

		if opt in ('-q', '--quiet'):
			synctool.lib.QUIET = True
			continue

		if opt == '--unix':
			synctool.lib.UNIX_CMD = True
			continue

		if opt == '--masterlog':
			# used by the master for message logging purposes
			synctool.lib.MASTERLOG = True
			continue

		if opt == '--nodename':
			# used by the master to set the client's nodename
			synctool.param.NODENAME = arg
			continue

		if opt in ('-d', '--diff'):
			opt_diff = True
			action = ACTION_DIFF
			f = synctool.lib.strip_path(arg)
			if not f in SINGLE_FILES:
				SINGLE_FILES.append(f)
			continue

		if opt in ('-1', '--single'):
			opt_single = True
			f = synctool.lib.strip_path(arg)
			if not f in SINGLE_FILES:
				SINGLE_FILES.append(f)
			continue

		if opt in ('-r', '--ref', '--reference'):
			opt_reference = True
			action = ACTION_REFERENCE
			f = synctool.lib.strip_path(arg)
			if not f in SINGLE_FILES:
				SINGLE_FILES.append(f)
			continue

		if opt in ('-e', '--erase-saved'):
			opt_erase_saved = True
			action = ACTION_ERASE_SAVED
			continue

		stderr("unknown command line option '%s'" % opt)
		errors += 1

	if errors:
		usage()
		sys.exit(1)

	option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
		opt_upload, opt_suffix, opt_fix)

	return action


def main():
	synctool.param.init()

	action = get_options()

	synctool.config.init_mynodename()

	if not synctool.param.NODENAME:
		stderr('unable to determine my nodename (%s)' %
				synctool.param.HOSTNAME)
		stderr('please check %s' % synctool.param.CONF_FILE)
		sys.exit(1)

	if synctool.param.NODENAME in synctool.param.IGNORE_GROUPS:
		# this is only a warning ...
		# you can still run synctool-pkg on the client by hand
		stderr('warning: node %s is disabled in %s' %
			(synctool.param.NODENAME, synctool.param.CONF_FILE))

	if synctool.lib.UNIX_CMD:
		t = time.localtime(time.time())

		unix_out('#')
		unix_out('# script generated by synctool on '
			'%04d/%02d/%02d %02d:%02d:%02d' %
			(t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# NODENAME=%s' % synctool.param.NODENAME)
		unix_out('# HOSTNAME=%s' % synctool.param.HOSTNAME)
		unix_out('# ROOTDIR=%s' % synctool.param.ROOTDIR)
		unix_out('#')

		if not synctool.lib.DRY_RUN:
			unix_out('# NOTE: --fix specified, applying updates')
			unix_out('#')

		unix_out('')
	else:
		if not synctool.lib.QUIET:
			verbose('my nodename: %s' % synctool.param.NODENAME)
			verbose('my hostname: %s' % synctool.param.HOSTNAME)
			verbose('rootdir: %s' % synctool.param.ROOTDIR)

			if synctool.param.LOGFILE != None and not synctool.lib.DRY_RUN:
				verbose('logfile: %s' % synctool.param.LOGFILE)

			verbose('')

			if synctool.lib.DRY_RUN:
				stdout('DRY RUN, not doing any updates')
				terse(synctool.lib.TERSE_DRYRUN, 'not doing any updates')
			else:
				stdout('--fix specified, applying changes')
				terse(synctool.lib.TERSE_FIXING, ' applying changes')

			verbose('')

	synctool.lib.openlog()

	os.environ['SYNCTOOL_NODENAME'] = synctool.param.NODENAME
	os.environ['SYNCTOOL_ROOTDIR'] = synctool.param.ROOTDIR

	if action == ACTION_DIFF:
		for f in SINGLE_FILES:
			diff_files(f)

	elif action == ACTION_REFERENCE:
		for f in SINGLE_FILES:
			reference(f)

	elif action == ACTION_ERASE_SAVED:
		if SINGLE_FILES:
			for single_file in SINGLE_FILES:
				single_erase_saved(single_file)
		else:
			erase_saved()

	elif SINGLE_FILES:
		for single_file in SINGLE_FILES:
			(changed, src) = single_files(single_file)
			if changed:
				run_post(src, single_file)

		run_post_on_directories()

	else:
		overlay_files()
		delete_files()
		run_post_on_directories()

	unix_out('# EOB')

	synctool.lib.closelog()


if __name__ == '__main__':
	try:
		main()
	except IOError, ioerr:
		if ioerr.errno == errno.EPIPE:		# Broken pipe
			pass
		else:
			print ioerr

	except KeyboardInterrupt:		# user pressed Ctrl-C
		print

# EOB
