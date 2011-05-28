#! /usr/bin/env python
#
#	synctool	WJ103
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_config
import synctool_lib
import synctool_overlay
import synctool_stat

from synctool_lib import verbose,stdout,stderr,terse,unix_out,dryrun_msg

import sys
import os
import os.path
import string
import getopt
import time
import shlex

try:
	import subprocess
	use_subprocess = True
except ImportError:
	use_subprocess = False

# get_options() returns these action codes
ACTION_DEFAULT = 0
ACTION_DIFF = 1
ACTION_RUN_TASKS = 3
ACTION_REFERENCE = 4

# blocksize for doing I/O while checksumming files
BLOCKSIZE = 16 * 1024

SINGLE_FILES = []

# list of changed directories
# This is for running .post scripts on changed directories
# every element is a tuple: (src_path, dest_path)
DIR_CHANGED = []


def run_command(cmd):
	'''run a shell command'''
	
	if synctool_lib.DRY_RUN:
		not_str = 'not '
	else:
		not_str = ''
	
	if cmd[0] != '/':
		# if relative path, use scriptdir
		cmd = synctool_param.SCRIPT_DIR + '/' + cmd
	
	# a command can have arguments
	arr = shlex.split(cmd)
	cmdfile = arr[0]
	
	stat = synctool_stat.SyncStat(cmdfile)
	
	if not stat.exists():
		stderr('error: command %s not found' % synctool_lib.prettypath(cmdfile))
		return
	
	if not stat.isExec():
		stderr("warning: file '%s' is not executable" % synctool_lib.prettypath(cmdfile))
		return
	
	if not synctool_lib.QUIET:
		stdout('%srunning command %s' % (not_str, synctool_lib.prettypath(cmd)))
	
	terse(synctool_lib.TERSE_EXEC, cmdfile)
	unix_out('# run command %s' % cmdfile)
	unix_out(cmd)
	
	if not synctool_lib.DRY_RUN:
		verbose('  os.system("%s")' % synctool_lib.prettypath(cmd))
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if use_subprocess:
			try:
				subprocess.Popen(cmd, shell=True)
			except:
				stderr("failed to run shell command '%s' : %s" % (synctool_lib.prettypath(cmd), reason))
		else:
			try:
				os.system(cmd)
			except OSError, reason:
				stderr("failed to run shell command '%s' : %s" % (synctool_lib.prettypath(cmd), reason))
		
		sys.stdout.flush()
		sys.stderr.flush()
	else:
		verbose(dryrun_msg('  os.system("%s")' % synctool_lib.prettypath(cmd), 'action'))


def run_command_in_dir(dest_dir, cmd):
	'''change directory to dest_dir, and run the shell command'''
	
	verbose('  os.chdir(%s)' % dest_dir)
	unix_out('cd %s' % dest_dir)
	
	cwd = os.getcwd()
	
	# if dry run, the target directory may not exist yet (mkdir has not been called for real, for a dry run)
	if synctool_lib.DRY_RUN:
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
	
	global DIR_CHANGED
	
	stat = synctool_stat.SyncStat(dest)
	
	if stat.isDir():
		# directories will be handled later, so save this pair
		pair = (src, dest)
		DIR_CHANGED.append(pair)
		return
	
	dest_dir = os.path.dirname(dest)
	
	# file has changed, run on_update command
	if synctool_param.ON_UPDATE.has_key(dest):
		run_command_in_dir(dest_dir, synctool_param.ON_UPDATE[dest])
	
	# file has changed, run appropriate .post script
	postscript = synctool_overlay.postscript_for_path(src, dest)
	if postscript:
		run_command_in_dir(dest_dir, postscript)
	
	# content of directory was changed, so save this pair
	pair = (os.path.dirname(src), dest_dir)
	if not pair in DIR_CHANGED:
		DIR_CHANGED.append(pair)


def run_post_on_directory(src, dest):
	'''run .post script for a changed directory'''
	
	# Note that the script is executed with the changed dir as current working dir
	
	if synctool_param.ON_UPDATE.has_key(dest):
		run_command_in_dir(dest, synctool_param.ON_UPDATE[dest])
	
	# run appropriate .post script
	postscript = synctool_overlay.postscript_for_path(src, dest)
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
	
	synctool_overlay.visit(synctool_overlay.OV_OVERLAY, overlay_callback)


def delete_callback(obj):
	'''delete files'''
	
	if obj.dest_isDir():		# do not delete directories
		return
	
	if obj.dest_exists():
		if synctool_lib.DRY_RUN:
			not_str = 'not '
		else:
			not_str = ''
		
		stdout('%sdeleting %s : %s' % (not_str, obj.print_src(), obj.print_dest()))
		hard_delete_file(obj)
		run_post(obj.src_path, obj.dest_path)


def delete_files():
	synctool_overlay.visit(synctool_overlay.OV_DELETE, delete_callback)


def tasks_callback(obj):
	'''run tasks'''
	
	if not obj.src_isDir():
		run_command(obj.src_path)
		unix_out('')


def run_tasks():
	synctool_overlay.visit(synctool_overlay.OV_TASKS, tasks_callback)


def always_run():
	'''always run these commands'''
	
	for cmd in synctool_param.ALWAYS_RUN:
		run_command(cmd)
		unix_out('')


def single_files(filename):
	'''check/update a single file'''
	'''returns (True, path_in_synctree) if file is different'''
	
	if not filename:
		stderr('missing filename')
		return (False, None)
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return (False, None)
	
	verbose('checking against %s' % obj.print_src())
	
	changed = compare_files(obj)
	if not changed:
		stdout('%s is up to date' % filename)
		terse(synctool_lib.TERSE_OK, filename)
		unix_out('# %s is up to date\n' % obj.print_dest())
	
	return (changed, obj.src_path)


def single_task(filename):
	'''run a single task'''

	if not filename:
		stderr('missing task filename')
		return
	
	task_script = filename
	if task_script[0] != '/':				# trick to make find() work for tasks, too
		task_script = '/' + task_script
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_TASKS, task_script)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr("no such task '%s'" % filename)
		return
	
	run_command(obj.src_path)
	unix_out('')


def reference(filename):
	'''show which source file in the repository synctool chooses to use'''
	
	if not filename:
		stderr('missing filename')
		return
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return
	
	print obj.print_src()


def diff_files(filename):
	'''display a diff of the file'''
	
	if not synctool_param.DIFF_CMD:
		stderr('error: diff_cmd is undefined in %s' % synctool_param.CONF_FILE)
		return
	
	synctool_lib.DRY_RUN = True						# be sure that it doesn't do any updates
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		return
	
	if synctool_lib.UNIX_CMD:
		unix_out('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.src_path))
	else:
		verbose('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.print_src()))
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if use_subprocess:
			cmd_arr = shlex.split(synctool_param.DIFF_CMD)
			cmd_arr.append(dest)
			cmd_arr.append(obj.src_path)
			subprocess.Popen(cmd_arr, shell=False)
		else:
			os.system('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.src_path))
		
		sys.stdout.flush()
		sys.stderr.flush()


def be_careful_with_getopt():
	'''check sys.argv for dangerous common typo's on the command-line'''
	
	# be extra careful with possible typo's on the command-line
	# because '-f' might run --fix because of the way that getopt() works
	
	for arg in sys.argv:
		
		# This is probably going to give stupid-looking output in some cases,
		# but it's better to be safe than sorry
		
		if arg[:2] == '-d' and string.find(arg, 'f') > -1:
			print "Did you mean '--diff'?"
			sys.exit(1)

		if arg[:2] == '-r' and string.find(arg, 'f') > -1:
			if string.count(arg, 'e') >= 2:
				print "Did you mean '--reference'?"
			else:
				print "Did you mean '--ref'?"
			sys.exit(1)


def	option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix):
	'''some combinations of command-line options don't make sense; alert the user and abort'''
	
	if opt_upload and (opt_diff or opt_single or opt_reference or opt_tasks):
		stderr("the --upload option can not be combined with --diff, --single, --ref, or --tasks")
		sys.exit(1)
	
	if opt_suffix and not opt_upload:
		stderr("option --suffix can only be used together with --upload")
		sys.exit(1)
	
	if opt_diff and (opt_single or opt_reference or opt_tasks or opt_fix):
		stderr("option --diff can not be combined with --single, --ref, --tasks, or --fix")
		sys.exit(1)
	
	if opt_reference and (opt_single or opt_tasks or opt_fix):
		stderr("option --reference can not be combined with --single, --tasks, or --fix")
		sys.exit(1)


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file'
	print '                        (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -d, --diff=file       Show diff for file'
	print '  -e, --erase-saved     Erase *.saved backup files'
	print '  -1, --single=file     Update a single file/run single task'
	print '  -r, --ref=file        Show which source file synctool chooses'
	print '  -t, --tasks           Run the scripts in the tasks/ directory'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -F, --fullpath        Show full paths instead of shortened ones'
	print '  -T, --terse           Show terse, shortened paths'
	print '      --color           Use colored output (only for terse mode)'
	print '      --no-color        Do not color output'
	print '      --unix            Output actions as unix shell commands'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '      --version         Print current version number'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that synctool does a dry run unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2011'


def get_options():
	global SINGLE_FILES
	
	progname = os.path.basename(sys.argv[0])
	
	synctool_lib.DRY_RUN = True				# set default dry-run
	
	# check for dangerous common typo's on the command-line
	be_careful_with_getopt()
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:d:1:r:etfFTvq',
			['help', 'conf=', 'diff=', 'single=', 'ref=', 'erase-saved',
			'tasks', 'fix', 'fullpath', 'terse', 'color', 'no-color',
			'verbose', 'quiet', 'unix', 'masterlog', 'version'])
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
	
	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue
		
		if opt == '--version':
			print synctool_param.VERSION
			sys.exit(0)
	
	synctool_config.read_config()
	
	if not synctool_param.TERSE:
		# giving --terse changes program behavior as early as
		# in the get_options() loop itself, so set it here already
		for opt, args in opts:
			if opt in ('-T', '--terse'):
				synctool_param.TERSE = True
				synctool_param.FULL_PATH = False
				continue
			
			if opt in ('-F', '--fullpath'):
				synctool_param.FULL_PATH = True
				continue
	
	# then go process all the other options
	errors = 0
	
	action = ACTION_DEFAULT
	SINGLE_FILES = []
	
	# these are only used for checking the validity of command-line option combinations
	opt_diff = False
	opt_single = False
	opt_reference = False
	opt_tasks = False
	opt_upload = False
	opt_suffix = False
	opt_fix = False
	
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?', '-c', '--conf', '-T', '--terse', '-F', '--fullpath', '--version'):
			# already done
			continue
		
# dry run already is default
#
#		if opt in ('-n', '--dry-run'):
#			synctool_lib.DRY_RUN = True
#			continue
		
		if opt in ('-e', '--erase-saved'):
			synctool_lib.ERASE_SAVED = True
			synctool_param.BACKUP_COPIES = False
			continue
		
		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool_lib.DRY_RUN = False
			continue
		
		if opt == '--color':
			synctool_param.COLORIZE = True
			continue
		
		if opt == '--no-color':
			synctool_param.COLORIZE = False
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			continue
		
		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True
			continue
		
		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue
		
		if opt == '--masterlog':
			synctool_lib.MASTERLOG = True
			continue
		
		if opt in ('-d', '--diff'):
			opt_diff = True
			action = ACTION_DIFF
			file = synctool_lib.strip_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt in ('-1', '--single'):
			opt_single = True
			file = synctool_lib.strip_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt in ('-t', '--task', '--tasks'):
			opt_tasks = True
			action = ACTION_RUN_TASKS
			continue
		
		if opt in ('-r', '--ref', '--reference'):
			opt_reference = True
			action = ACTION_REFERENCE
			file = synctool_lib.strip_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		stderr("unknown command line option '%s'" % opt)
		errors = errors + 1

	if errors:
		usage()
		sys.exit(1)
	
	option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix)
	
	return action


if __name__ == '__main__':
	action = get_options()
	
	synctool_config.add_myhostname()
	
	if synctool_param.NODENAME == None:
		stderr('unable to determine my nodename, please check %s' % synctool_param.CONF_FILE)
		sys.exit(1)
	
	if synctool_param.NODENAME in synctool_param.IGNORE_GROUPS:
		stderr('%s: node %s is disabled in the config file' % (synctool_param.CONF_FILE, synctool_param.NODENAME))
		sys.exit(1)
	
	synctool_config.remove_ignored_groups()
	
	synctool_param.MY_GROUPS = synctool_config.get_my_groups()
	synctool_param.ALL_GROUPS = synctool_config.make_all_groups()
	
	if synctool_lib.UNIX_CMD:
		t = time.localtime(time.time())
		
		unix_out('#')
		unix_out('# script generated by synctool on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# NODENAME=%s' % synctool_param.NODENAME)
		unix_out('# HOSTNAME=%s' % synctool_param.HOSTNAME)
		unix_out('# MASTERDIR=%s' % synctool_param.MASTERDIR)
		unix_out('# SYMLINK_MODE=0%o' % synctool_param.SYMLINK_MODE)
		unix_out('#')
		
		if not synctool_lib.DRY_RUN:
			unix_out('# NOTE: --fix specified, applying updates')
			unix_out('#')
		
		unix_out('')
	else:
		if not synctool_lib.QUIET:
			verbose('my nodename: %s' % synctool_param.NODENAME)
			verbose('my hostname: %s' % synctool_param.HOSTNAME)
			verbose('masterdir: %s' % synctool_param.MASTERDIR)
			verbose('symlink_mode: 0%o' % synctool_param.SYMLINK_MODE)
			
			if synctool_param.LOGFILE != None and not synctool_lib.DRY_RUN:
				verbose('logfile: %s' % synctool_param.LOGFILE)
			
			verbose('')
			
			if synctool_lib.DRY_RUN:
				stdout('DRY RUN, not doing any updates')
				terse(synctool_lib.TERSE_DRYRUN, 'not doing any updates')
			else:
				stdout('--fix specified, applying changes')
				terse(synctool_lib.TERSE_FIXING, ' applying changes')
			
			verbose('')
	
	synctool_lib.openlog()
	
	os.putenv('SYNCTOOL_NODENAME', synctool_param.NODENAME)
	os.putenv('SYNCTOOL_MASTERDIR', synctool_param.MASTERDIR)
	
	if action == ACTION_DIFF:
		for file in SINGLE_FILES:
			diff_files(file)
	
	elif action == ACTION_RUN_TASKS:
		if SINGLE_FILES:
			for single_file in SINGLE_FILES:
				single_task(single_file)
		else:
			run_tasks()
	
	elif action == ACTION_REFERENCE:
		for file in SINGLE_FILES:
			reference(file)
	
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
		always_run()
	
	unix_out('# EOB')
	
	synctool_lib.closelog()


# EOB
