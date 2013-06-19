#! /usr/bin/env python
#
#	synctool_master.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import sys
import string
import getopt
import shlex
import tempfile
import errno

import synctool.aggr
import synctool.config
import synctool.lib
from synctool.lib import verbose, stdout, stderr, terse, unix_out
import synctool.nodeset
import synctool.overlay
import synctool.param
import synctool.syncstat
import synctool.unbuffered
import synctool.update

NODESET = synctool.nodeset.NodeSet()

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
OPT_CHECK_UPDATE = False
OPT_DOWNLOAD = False

PASS_ARGS = None
MASTER_OPTS = None


def run_remote_synctool(address_list):
	synctool.lib.multiprocess(worker_synctool, address_list)


def worker_synctool(addr):
	'''run rsync of ROOTDIR to the nodes and ssh+synctool, in parallel'''

	nodename = NODESET.get_nodename_from_address(addr)

	if nodename == synctool.param.NODENAME:
		run_local_synctool()
		return

	# rsync ROOTDIR/dirs/ to the node
	# if "it wants it"
	if not (OPT_SKIP_RSYNC or nodename in synctool.param.NO_RSYNC):
		verbose('running rsync $SYNCTOOL/ to node %s' % nodename)
		unix_out('%s %s %s:%s/' % (synctool.param.RSYNC_CMD,
			synctool.param.ROOTDIR, addr, synctool.param.ROOTDIR))

		# make rsync filter to include the correct dirs
		tmp_filename = rsync_include_filter(nodename)

		cmd_arr = shlex.split(synctool.param.RSYNC_CMD)
		cmd_arr.append('--filter=. %s' % tmp_filename)
		cmd_arr.append('%s/' % synctool.param.ROOTDIR)
		cmd_arr.append('%s:%s/' % (addr, synctool.param.ROOTDIR))

		# double check the rsync destination
		# our filters are like playing with fire
		if not synctool.param.ROOTDIR or (
			synctool.param.ROOTDIR == os.path.sep):
			stderr('cowardly refusing to rsync with rootdir == %s' %
					synctool.param.ROOTDIR)
			sys.exit(-1)

		synctool.lib.run_with_nodename(cmd_arr, nodename)

		# delete temp file
		try:
			os.unlink(tmp_filename)
		except OSError:
			# silently ignore unlink error
			pass

	# run 'ssh node synctool_cmd'
	cmd_arr = shlex.split(synctool.param.SSH_CMD)
	cmd_arr.append(addr)
	cmd_arr.extend(shlex.split(synctool.param.SYNCTOOL_CMD))
	cmd_arr.append('--nodename=%s' % nodename)
	cmd_arr.extend(PASS_ARGS)

	verbose('running synctool on node %s' % nodename)
	unix_out(string.join(cmd_arr))

	synctool.lib.run_with_nodename(cmd_arr, nodename)


def run_local_synctool():
	cmd_arr = shlex.split(synctool.param.SYNCTOOL_CMD) + PASS_ARGS

	verbose('running synctool on node %s' % synctool.param.NODENAME)
	unix_out(string.join(cmd_arr))

	synctool.lib.run_with_nodename(cmd_arr, synctool.param.NODENAME)


def rsync_include_filter(nodename):
	'''create temp file with rsync filter rules
	Include only those dirs that apply for this node
	Returns filename of the filter file'''

	try:
		(fd, filename) = tempfile.mkstemp(prefix='synctool-',
											dir=synctool.param.TEMP_DIR)
	except OSError, reason:
		stderr('failed to create temp file: %s' % reason)
		sys.exit(-1)

	try:
		f = os.fdopen(fd, 'w')
	except OSError, reason:
		stderr('failed to open temp file: %s' % reason)
		sys.exit(-1)
	else:
		# include $SYNCTOOL/var/ but exclude
		# the top overlay/ and delete/ dir
		with f:
			f.write('''# synctool rsync filter
+ /var/overlay/
+ /var/overlay/all/
+ /var/delete/
+ /var/delete/all/
''')
			f.write('+ /%s\n' % synctool.param.CONF_FILE)

			# set mygroups for this nodename
			synctool.param.NODENAME = nodename
			synctool.param.MY_GROUPS = synctool.config.get_my_groups()

			# add only the group dirs that apply
			for g in synctool.param.MY_GROUPS:
				d = os.path.join(synctool.param.OVERLAY_DIR, g)
				if os.path.isdir(d):
					f.write('+ /var/overlay/%s/\n' % g)

				d = os.path.join(synctool.param.DELETE_DIR, g)
				if os.path.isdir(d):
					f.write('+ /var/delete/%s/\n' % g)

			# Note: sbin/*.pyc is excluded to keep major differences in
			# Python versions (on master vs. client node) from clashing
			f.write('''- /sbin/*.pyc
- /var/overlay/*
- /var/delete/*
''')

	# Note: remind to delete the temp file later

	return filename


def upload(address, upload_filename, upload_suffix=None):
	'''copy a file from a node into the overlay/ tree'''

	if upload_filename[0] != os.path.sep:
		stderr('error: the filename to upload must be an absolute path')
		sys.exit(-1)

	trimmed_upload_fn = upload_filename[1:]		# remove leading slash

	if upload_suffix and not upload_suffix in synctool.param.ALL_GROUPS:
		stderr("no such group '%s'" % upload_suffix)
		sys.exit(-1)

	# shadow DRY_RUN because that var can not be used correctly here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		dry_run = False
	else:
		dry_run = True
		if not synctool.lib.QUIET:
			stdout('DRY RUN, not uploading any files')
			terse(synctool.lib.TERSE_DRYRUN, 'not uploading any files')

	node = NODESET.get_nodename_from_address(address)

	# pretend that the current node is now the given node;
	# this is needed for find() to find the best reference for the file
	orig_NODENAME = synctool.param.NODENAME
	synctool.param.NODENAME = node
	synctool.config.insert_group(node, node)

	orig_MY_GROUPS = synctool.param.MY_GROUPS[:]
	synctool.param.MY_GROUPS = synctool.config.get_my_groups()

	# see if file is already in the repository
	(obj, err) = synctool.overlay.find_terse(synctool.overlay.OV_OVERLAY,
					upload_filename)

	if err == synctool.overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)

	if err == synctool.overlay.OV_NOT_FOUND:
		# no source path found
		if string.find(upload_filename, '...') >= 0:
			stderr("%s is not in the repository, don't know what to map "
				"this path to\n"
				"Please give the full path instead of a terse path, "
				"or touch the source file\n"
				"in the repository first and try again" %
				os.path.basename(upload_filename))
			sys.exit(1)

		# it wasn't a terse path, throw a source path together
		# This picks the 'all' overlay dir as default source,
		# which may not be correct -- but it is a good guess
		repos_filename = os.path.join(synctool.param.OVERLAY_DIR, 'all',
							trimmed_upload_fn)
		if upload_suffix:
			repos_filename = repos_filename + '._' + upload_suffix
		else:
			# use _nodename as default suffix
			repos_filename = repos_filename + '._' + node
	else:
		if upload_suffix:
			# remove the current group suffix
			# and add the specified suffix to the filename
			(repos_filename, ext) = os.path.splitext(obj.src_path)
			repos_filename += '._' + upload_suffix
		else:
			repos_filename = obj.src_path

	synctool.param.NODENAME = orig_NODENAME
	synctool.param.MY_GROUPS = orig_MY_GROUPS

	verbose('%s:%s uploaded as %s' % (node, upload_filename, repos_filename))
	terse(synctool.lib.TERSE_UPLOAD, repos_filename)
	unix_out('%s %s:%s %s' % (synctool.param.SCP_CMD, address,
								upload_filename, repos_filename))

	if dry_run:
		stdout('would be uploaded as %s' %
			synctool.lib.prettypath(repos_filename))
	else:
		# first check if the directory in the repository exists
		repos_dir = os.path.dirname(repos_filename)
		stat = synctool.syncstat.SyncStat(repos_dir)
		if not stat.exists():
			verbose('making directory %s' %
				synctool.lib.prettypath(repos_dir))
			unix_out('mkdir -p %s' % repos_dir)
			synctool.lib.mkdir_p(repos_dir)

		# make scp command array
		scp_cmd_arr = shlex.split(synctool.param.SCP_CMD)
		scp_cmd_arr.append('%s:%s' % (address, upload_filename))
		scp_cmd_arr.append(repos_filename)

		synctool.lib.run_with_nodename(scp_cmd_arr,
			NODESET.get_nodename_from_address(address))

		if os.path.isfile(repos_filename):
			stdout('uploaded %s' % synctool.lib.prettypath(repos_filename))


def make_tempdir():
	if not os.path.isdir(synctool.param.TEMP_DIR):
		try:
			os.mkdir(synctool.param.TEMP_DIR, 0750)
		except OSError, reason:
			stderr('failed to create tempdir %s: %s' %
				(synctool.param.TEMP_DIR, reason))
			sys.exit(-1)


def check_cmd_config():
	'''check whether the commands as given in synctool.conf actually exist'''

	# pretty lame code
	# Maybe the _CMD params should be a dict?

	errors = 0

#	(ok, synctool.param.DIFF_CMD) = synctool.config.check_cmd_config(
#									'diff_cmd', synctool.param.DIFF_CMD)
#	if not ok:
#		errors += 1

#	(ok, synctool.param.PING_CMD) = synctool.config.check_cmd_config(
#									'ping_cmd', synctool.param.PING_CMD)
#	if not ok:
#		errors += 1

	(ok, synctool.param.SSH_CMD) = synctool.config.check_cmd_config(
									'ssh_cmd', synctool.param.SSH_CMD)
	if not ok:
		errors += 1

#	(ok, synctool.param.SCP_CMD) = synctool.config.check_cmd_config(
#									'scp_cmd', synctool.param.SCP_CMD)
#	if not ok:
#		errors += 1

	(ok, synctool.param.RSYNC_CMD) = synctool.config.check_cmd_config(
									'rsync_cmd', synctool.param.RSYNC_CMD)
	if not ok:
		errors += 1

	(ok, synctool.param.SYNCTOOL_CMD) = synctool.config.check_cmd_config(
								'synctool_cmd', synctool.param.SYNCTOOL_CMD)
	if not ok:
		errors += 1

#	(ok, synctool.param.PKG_CMD) = synctool.config.check_cmd_config(
#									'pkg_cmd', synctool.param.PKG_CMD)
#	if not ok:
#		errors += 1

	if errors > 0:
		sys.exit(1)


def be_careful_with_getopt():
	'''check sys.argv for dangerous common typo's on the command-line'''

	# be extra careful with possible typo's on the command-line
	# because '-f' might run --fix because of the way that getopt() works

	for arg in sys.argv:

		# This is probably going to give stupid-looking output
		# in some cases, but it's better to be safe than sorry

		if arg[:2] == '-d' and string.find(arg, 'f') > -1:
			print "Did you mean '--diff'?"
			sys.exit(1)

		if arg[:2] == '-r' and string.find(arg, 'f') > -1:
			if string.count(arg, 'e') >= 2:
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


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print ('                                 (default: %s)' %
		synctool.param.DEFAULT_CONF)
	print '''  -n, --node=nodelist            Execute only on these nodes
  -g, --group=grouplist          Execute only on these groups of nodes
  -x, --exclude=nodelist         Exclude these nodes from the selected group
  -X, --exclude-group=grouplist  Exclude these groups from the selection

  -d, --diff=file                Show diff for file
  -1, --single=file              Update a single file
  -r, --ref=file                 Show which source file synctool chooses
  -u, --upload=file              Pull a remote file into the overlay tree
  -s, --suffix=group             Give group suffix for the uploaded file
  -e, --erase-saved              Erase *.saved backup files
  -f, --fix                      Perform updates (otherwise, do dry-run)
      --no-post                  Do not run any .post scripts
  -p, --numproc=num              Number of concurrent procs
  -F, --fullpath                 Show full paths instead of shortened ones
  -T, --terse                    Show terse, shortened paths
      --color                    Use colored output (only for terse mode)
      --no-color                 Do not color output
      --unix                     Output actions as unix shell commands
      --skip-rsync               Do not sync the repository
                                 (eg. when it is on a shared filesystem)
      --version                  Show current version number
      --check-update             Check for availibility of newer version
      --download                 Download latest version
  -v, --verbose                  Be verbose
  -q, --quiet                    Suppress informational startup messages
  -a, --aggregate                Condense output; list nodes per change

A nodelist or grouplist is a comma-separated list
Note that synctool does a dry run unless you specify --fix

Written by Walter de Jong <walter@heiho.net> (c) 2003-2013'''


def get_options():
	global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE
	global OPT_CHECK_UPDATE, OPT_DOWNLOAD, MASTER_OPTS

	# check for typo's on the command-line;
	# things like "-diff" will trigger "-f" => "--fix"
	be_careful_with_getopt()

	try:
		opts, args = getopt.getopt(sys.argv[1:],
			'hc:vn:g:x:X:d:1:r:u:s:efpFTqa',
			['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'diff=', 'single=', 'ref=',
			'upload=', 'suffix=', 'erase-saved', 'fix', 'no-post',
			'numproc=', 'fullpath', 'terse', 'color', 'no-color',
			'quiet', 'aggregate', 'unix', 'skip-rsync',
			'version', 'check-update', 'download'])
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

	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command line')
		sys.exit(1)

	upload_filename = None
	upload_suffix = None

	# these are only used for checking the validity of option combinations
	opt_diff = False
	opt_single = False
	opt_reference = False
	opt_erase_saved = False
	opt_upload = False
	opt_suffix = False
	opt_fix = False

	PASS_ARGS = []
	MASTER_OPTS = [ sys.argv[0] ]

	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool.param.CONF_FILE = arg
			PASS_ARGS.append(opt)
			PASS_ARGS.append(arg)
			continue

		if opt == '--version':
			print synctool.param.VERSION
			sys.exit(0)

	synctool.config.read_config()
	check_cmd_config()

	# then process all the other options
	#
	# Note: some options are passed on to synctool on the node, while
	# others are not. Therefore some 'continue', while others don't

	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)

		if arg:
			MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?', '-c', '--conf', '--version'):
			# already done
			continue

		if opt in ('-v', '--verbose'):
			synctool.lib.VERBOSE = True

		if opt in ('-n', '--node'):
			NODESET.add_node(arg)
			continue

		if opt in ('-g', '--group'):
			NODESET.add_group(arg)
			continue

		if opt in ('-x', '--exclude'):
			NODESET.exclude_node(arg)
			continue

		if opt in ('-X', '--exclude-group'):
			NODESET.exclude_group(arg)
			continue

		if opt in ('-d', '--diff'):
			opt_diff = True

		if opt in ('-1', '--single'):
			opt_single = True

		if opt in ('-r', '--ref'):
			opt_reference = True

		if opt in ('-u', '--upload'):
			opt_upload = True
			upload_filename = synctool.lib.strip_path(arg)
			continue

		if opt in ('-s', '--suffix'):
			opt_suffix = True
			upload_suffix = arg
			continue

		if opt in ('-e', '--erase-saved'):
			opt_erase_saved = True

		if opt in ('-q', '--quiet'):
			synctool.lib.QUIET = True

		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool.lib.DRY_RUN = False

		if opt == '--no-post':
			synctool.lib.NO_POST = True

		if opt in ('-p', '--numproc'):
			try:
				synctool.param.NUM_PROC = int(arg)
			except ValueError:
				print ("%s: option '%s' requires a numeric value" %
					(os.path.basename(sys.argv[0]), opt))
				sys.exit(1)

			if synctool.param.NUM_PROC < 1:
				print ('%s: invalid value for numproc' %
					os.path.basename(sys.argv[0]))
				sys.exit(1)

			continue

		if opt in ('-F', '--fullpath'):
			synctool.param.FULL_PATH = True
			synctool.param.TERSE = False

		if opt in ('-T', '--terse'):
			synctool.param.TERSE = True
			synctool.param.FULL_PATH = False

		if opt == '--color':
			synctool.param.COLORIZE = True

		if opt == '--no-color':
			synctool.param.COLORIZE = False

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue

		if opt == '--unix':
			synctool.lib.UNIX_CMD = True

		if opt == '--skip-rsync':
			OPT_SKIP_RSYNC = True
			continue

		if opt == '--check-update':
			OPT_CHECK_UPDATE = True
			continue

		if opt == '--download':
			OPT_DOWNLOAD = True
			continue

		if opt:
			PASS_ARGS.append(opt)

		if arg:
			PASS_ARGS.append(arg)

	# enable logging at the master node
	PASS_ARGS.append('--masterlog')

	if args != None:
		MASTER_OPTS.extend(args)
		PASS_ARGS.extend(args)

	option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
		opt_upload, opt_suffix, opt_fix)

	return (upload_filename, upload_suffix)


def main():
	synctool.param.init()

	sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

	(upload_filename, upload_suffix) = get_options()

	if OPT_CHECK_UPDATE:
		if not synctool.update.check():
			# no newer version available
			sys.exit(0)

		sys.exit(1)

	if OPT_DOWNLOAD:
		if not synctool.update.download():
			# download error
			sys.exit(-1)

		sys.exit(0)

	if OPT_AGGREGATE:
		if not synctool.aggr.run(MASTER_OPTS):
			sys.exit(-1)

		sys.exit(0)

	synctool.config.init_mynodename()

	# ooh ... testing for DRY_RUN doesn't work here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		synctool.lib.openlog()

	address_list = NODESET.addresses()
	if not address_list:
		print 'no valid nodes specified'
		sys.exit(1)

	if upload_filename:
		# upload a file
		if len(address_list) != 1:
			print 'The option --upload can only be run on just one node'
			print ('Please use --node=nodename to specify the node '
				'to upload from')
			sys.exit(1)

		upload(address_list[0], upload_filename, upload_suffix)

	else:
		# do regular synctool run
		make_tempdir()
		run_remote_synctool(address_list)

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
		pass

# EOB
