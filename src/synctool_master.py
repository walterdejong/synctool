#! /usr/bin/env python
#
#	synctool_master.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool
import synctool_ssh
import synctool_param
import synctool_config
import synctool_aggr
import synctool_lib
import synctool_unbuffered
import synctool_nodeset

from synctool_lib import verbose,stdout,stderr,terse,unix_out

import os
import sys
import string
import getopt
import shlex

NODESET = synctool_nodeset.NodeSet()

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
OPT_CHECK_UPDATE = False
OPT_DOWNLOAD = False

PASS_ARGS = None
MASTER_OPTS = None


def run_remote_synctool(nodes):
	if not synctool_param.RSYNC_CMD:
		stderr('%s: error: rsync_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	if not synctool_param.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	if not synctool_param.SYNCTOOL_CMD:
		stderr('%s: error: synctool_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	# prepare rsync command
	if not OPT_SKIP_RSYNC:
		rsync_cmd_arr = shlex.split(synctool_param.RSYNC_CMD)
		rsync_cmd_arr.append('%s/' % synctool_param.MASTERDIR)
	else:
		rsync_cmd_arr = None

	# prepare remote synctool command
	ssh_cmd_arr = shlex.split(synctool_param.SSH_CMD)
	synctool_cmd_arr = shlex.split(synctool_param.SYNCTOOL_CMD)
	synctool_cmd_arr.extend(PASS_ARGS)
	
	# run in parallel
	synctool_lib.run_parallel(master_synctool, worker_synctool,
		(nodes, rsync_cmd_arr, ssh_cmd_arr, synctool_cmd_arr), len(nodes))


def master_synctool(rank, args):
	# the master node only displays what we're running
	(nodes, rsync_cmd_arr, ssh_cmd_arr, synctool_cmd_arr) = args
	
	node = nodes[rank]
	nodename = NODESET.get_nodename_from_interface(node)
	
	if rsync_cmd_arr != None:
		verbose('running rsync $masterdir/ to node %s' % nodename)
		unix_out('%s %s:%s/' % (string.join(rsync_cmd_arr), node, synctool_param.MASTERDIR))
	
	verbose('running synctool on node %s' % nodename)
	unix_out('%s %s %s' % (string.join(ssh_cmd_arr), node, string.join(synctool_cmd_arr)))


def worker_synctool(rank, args):
	'''runs rsync of $masterdir to the nodes and ssh+synctool in parallel'''
	
	(nodes, rsync_cmd_arr, ssh_cmd_arr, synctool_cmd_arr) = args
	
	node = nodes[rank]
	nodename = NODESET.get_nodename_from_interface(node)
	
	if rsync_cmd_arr != None:
		# rsync masterdir to the node
		rsync_cmd_arr.append('%s:%s/' % (node, synctool_param.MASTERDIR))
		synctool_lib.run_with_nodename(rsync_cmd_arr, nodename)
	
	# run 'ssh node synctool_cmd'
	ssh_cmd_arr.append(node)
	ssh_cmd_arr.extend(synctool_cmd_arr)
	
	synctool_lib.run_with_nodename(ssh_cmd_arr, nodename)


def run_local_synctool():
	if not synctool_param.SYNCTOOL_CMD:
		stderr('%s: error: synctool_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]),
			synctool_param.CONF_FILE))
		sys.exit(-1)

	cmd_arr = shlex.split(synctool_param.SYNCTOOL_CMD) + PASS_ARGS
	
	synctool_lib.run_with_nodename(cmd_arr, synctool_param.NODENAME)


def upload(interface, upload_filename, upload_suffix=None):
	'''copy a file from a node into the overlay/ tree'''
	
	if not synctool_param.SCP_CMD:
		stderr('%s: error: scp_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]),
			synctool_param.CONF_FILE))
		sys.exit(-1)
	
	if upload_filename[0] != '/':
		stderr('error: the filename to upload must be an absolute path')
		sys.exit(-1)
	
	trimmed_upload_fn = upload_filename[1:]			# remove leading slash
	
	import synctool_overlay
	
	# make the known groups lists
	synctool_config.remove_ignored_groups()
	synctool_param.MY_GROUPS = synctool_config.get_my_groups()
	synctool_param.ALL_GROUPS = synctool_config.make_all_groups()
	
	if upload_suffix and not upload_suffix in synctool_param.ALL_GROUPS:
		stderr("no such group '%s'" % upload_suffix)
		sys.exit(-1)
	
	# shadow DRY_RUN because that var can not be used correctly here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		dry_run = False
	else:
		dry_run = True
		if not synctool_lib.QUIET:
			stdout('DRY RUN, not uploading any files')
			terse(synctool_lib.TERSE_DRYRUN, 'not uploading any files')
	
	node = NODESET.get_nodename_from_interface(interface)
	
	# pretend that the current node is now the given node;
	# this is needed for find() to find the most optimal reference for the file
	orig_NODENAME = synctool_param.NODENAME
	synctool_param.NODENAME = node
	synctool_config.insert_group(node, node)
	
	orig_MY_GROUPS = synctool_param.MY_GROUPS[:]
	synctool_param.MY_GROUPS = synctool_config.get_my_groups()
	
	# see if file is already in the repository
	(repos_filename, dest) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, upload_filename)
	
	if not dest:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if not repos_filename:
		# no source path found
		if string.find(upload_filename, '...') >= 0:
			stderr("%s is not in the repository, don't know what to map this path to\n"
				"Please give the full path instead of a terse path, or touch the source file\n"
				"in the repository first and try again"
				% os.path.basename(upload_filename))
			sys.exit(1)
		
		# it wasn't a terse path, throw a source path together
		# This picks the first overlay dir as default source, which may not be correct
		# but it is a good guess
		repos_filename = os.path.join(synctool_param.OVERLAY_DIRS[0], trimmed_upload_fn)
		if upload_suffix:
			repos_filename = repos_filename + '._' + upload_suffix
		else:
			repos_filename = repos_filename + '._' + node		# use _nodename as default suffix
	else:
		if upload_suffix:
			# remove the current group suffix an add the specified suffix to the filename
			arr = string.split(repos_filename, '.')
			if len(arr) > 1 and arr[-1][0] == '_':
				repos_filename = string.join(arr[:-1], '.')
			
			repos_filename = repos_filename + '._' + upload_suffix
	
	synctool_param.NODENAME = orig_NODENAME
	synctool_param.MY_GROUPS = orig_MY_GROUPS
	
	verbose('%s:%s uploaded as %s' % (node, upload_filename, repos_filename))
	terse(synctool_lib.TERSE_UPLOAD, repos_filename)
	unix_out('%s %s:%s %s' % (synctool_param.SCP_CMD, interface, dest, repos_filename))
	
	if dry_run:
		stdout('would be uploaded as %s' % synctool_lib.prettypath(repos_filename))
	else:
		# make scp command array
		scp_cmd_arr = shlex.split(synctool_param.SCP_CMD)
		scp_cmd_arr.append('%s:%s' % (interface, dest))
		scp_cmd_arr.append(repos_filename)
		
		synctool_lib.run_with_nodename(scp_cmd_arr, NODESET.get_nodename_from_interface(interface))
		
		if os.path.isfile(repos_filename):
			stdout('uploaded %s' % synctool_lib.prettypath(repos_filename))


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print
	print '  -d, --diff=file                Show diff for file'
	print '  -e, --erase-saved              Erase *.saved backup files'
	print '  -1, --single=file              Update a single file/run single task'
	print '  -r, --ref=file                 Show which source file synctool chooses'
	print '  -u, --upload=file              Pull a remote file into the overlay tree'
	print '  -s, --suffix=group             Give group suffix for the uploaded file'
	print '  -t, --tasks                    Run the scripts in the tasks/ directory'
	print '  -f, --fix                      Perform updates (otherwise, do dry-run)'
	print '  -F, --fullpath                 Show full paths instead of shortened ones'
	print '  -T, --terse                    Show terse, shortened paths'
	print '      --color                    Use colored output (only for terse mode)'
	print '      --no-color                 Do not color output'
	print '      --unix                     Output actions as unix shell commands'
	print '      --skip-rsync               Do not sync the repository'
	print '                                 (eg. when it is on a shared filesystem)'
	print '      --version                  Show current version number'
	print '      --check-update             Check for availibility of newer version'
	print '      --download                 Download latest version'
	print '  -v, --verbose                  Be verbose'
	print '  -q, --quiet                    Suppress informational startup messages'
	print '  -a, --aggregate                Condense output; list nodes per change'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print 'Note that synctool does a dry run unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2011'


def get_options():
	global NODESET, PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE
	global OPT_CHECK_UPDATE, OPT_DOWNLOAD, MASTER_OPTS

	# check for typo's on the command-line; things like "-diff" will trigger "-f" => "--fix"
	synctool.be_careful_with_getopt()

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:d:1:r:u:s:etfFTqa',
			['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'diff=', 'single=', 'ref=',
			'upload=', 'suffix=', 'erase-saved', 'tasks', 'fix',
			'fullpath', 'terse', 'color', 'no-color',
			'quiet', 'aggregate', 'skip-rsync', 'unix',
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

	# these are only used for checking the validity of command-line option combinations
	opt_diff = False
	opt_single = False
	opt_reference = False
	opt_tasks = False
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
			synctool_param.CONF_FILE = arg
			PASS_ARGS.append(opt)
			PASS_ARGS.append(arg)
			continue
		
		if opt == '--version':
			print synctool_param.VERSION
			sys.exit(0)
	
	synctool_config.read_config()
	
	# then process all the other options
	#
	# Note: some options are passed on to synctool on the node, while
	#       others are not. Therefore some 'continue', while others don't
	#
	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)

		if arg:
			MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?', '-c', '--conf', '--version'):
			# already done
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			PASS_ARGS.append(opt)
			continue

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
			upload_filename = synctool_lib.strip_path(arg)
			continue

		if opt in ('-s', '--suffix'):
			opt_suffix = True
			upload_suffix = arg
			continue

		if opt in ('-t', '--tasks'):
			opt_tasks = True

		if opt in ('-e', '--erase-saved'):
			# This doesn't do anything in master, really
			# because it doesn't use these settings, but hey
			synctool_lib.ERASE_SAVED = True
			synctool_param.BACKUP_COPIES = False

		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True

		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool_lib.DRY_RUN = False

		if opt in ('-F', '--fullpath'):
			synctool_param.FULL_PATH = True

		if opt in ('-T', '--terse'):
			synctool_param.TERSE = True
		
		if opt == '--color':
			synctool_param.COLORIZE = True
		
		if opt == '--no-color':
			synctool_param.COLORIZE = False

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue

		if opt == '--skip-rsync':
			OPT_SKIP_RSYNC = True
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True

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

	synctool.option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix)

	return (upload_filename, upload_suffix)


def main():
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)

	(upload_filename, upload_suffix) = get_options()

	if OPT_CHECK_UPDATE:
		import synctool_update
		sys.exit(synctool_update.check())

	if OPT_DOWNLOAD:
		import synctool_update
		sys.exit(synctool_update.download())

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.add_myhostname()

	# ooh ... testing for DRY_RUN doesn't work here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		synctool_lib.openlog()

	nodes = NODESET.interfaces()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)

	if upload_filename:			# upload a file
		if len(nodes) != 1:
			print "The option --upload can only be run on just one node"
			print "Please use --node=nodename to specify the node to upload from"
			sys.exit(1)
		
		upload(nodes[0], upload_filename, upload_suffix)

	else:						# do regular synctool run
		local_interface = synctool_config.get_node_interface(synctool_param.NODENAME)

		for node in nodes:
			#
			#	is this node the localhost? then run locally
			#
			if node == local_interface:
				run_local_synctool()
				nodes.remove(node)
				break

		run_remote_synctool(nodes)

	synctool_lib.closelog()


if __name__ == '__main__':
	try:
		main()
	except IOError, ioerr:
		if ioerr.errno == 32:		# Broken pipe
			pass
		else:
			print ioerr

	except KeyboardInterrupt:		# user pressed Ctrl-C
		pass

# EOB
