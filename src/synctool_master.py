#! /usr/bin/env python
#
#	synctool_master.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2010
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool
import synctool_ssh
import synctool_config
import synctool_aggr
import synctool_lib
import synctool_unbuffered

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt
import shlex

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
OPT_VERSION = False
OPT_CHECK_UPDATE = False
OPT_DOWNLOAD = False

PASS_ARGS = None
MASTER_OPTS = None


def run_remote_synctool(nodes):
	if not synctool_config.RSYNC_CMD:
		stderr('%s: error: rsync_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	if not synctool_config.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	if not synctool_config.SYNCTOOL_CMD:
		stderr('%s: error: synctool_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	cmds = []

# append rsync command
	if not OPT_SKIP_RSYNC:
		cmds.append([ shlex.split(synctool_config.RSYNC_CMD) + [ '%s/' % synctool_config.MASTERDIR ], [ '%s/' % synctool_config.MASTERDIR ], ':' ])

# append synctool command
	cmds.append([ shlex.split(synctool_config.SSH_CMD), shlex.split(synctool_config.SYNCTOOL_CMD) + PASS_ARGS, None ])

	synctool_ssh.run_parallel_cmds(nodes, cmds)


def run_local_synctool():
	cmd_arr = shlex.split(synctool_config.SYNCTOOL_CMD) + PASS_ARGS
	synctool_ssh.run_local_cmd(cmd_arr)


def upload(interface, upload_filename, upload_suffix=None):
	'''copy a file from a node into the overlay/ tree'''

	if not synctool_config.SCP_CMD:
		stderr('%s: error: scp_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	if upload_filename[0] != '/':
		stderr('error: the filename to upload must be an absolute path')
		sys.exit(-1)

	trimmed_upload_fn = upload_filename[1:]			# remove leading slash

	import synctool_core

# make the known groups lists
	synctool_config.remove_ignored_groups()
	synctool_config.GROUPS = synctool_config.get_my_groups()
	synctool_config.ALL_GROUPS = synctool_config.make_all_groups()

	if upload_suffix and not upload_suffix in synctool_config.ALL_GROUPS:
		stderr("no such group '%s'" % upload_suffix)
		sys.exit(-1)
		
# shadow DRY_RUN because that var can not be used correctly here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		dry_run = False
	else:
		dry_run = True
		if not synctool_lib.QUIET:
			stdout('DRY RUN, not uploading any files')

	node = synctool_ssh.get_nodename_from_interface(interface)

# see if file is already in the repository
	repos_filename = synctool_core.find_synctree('overlay', upload_filename)
	if not repos_filename:
		repos_filename = os.path.join(synctool_config.MASTERDIR, 'overlay', trimmed_upload_fn)
		if upload_suffix:
			repos_filename = repos_filename + '._' + upload_suffix
		else:
			repos_filename = repos_filename + '._' + node		# use _nodename as default suffix
	else:
		if upload_suffix:
			arr = string.split(repos_filename, '.')
			if len(arr) > 1 and arr[-1][0] == '_':
				repos_filename = string.join(arr[:-1], '.')

			repos_filename = repos_filename + '._' + upload_suffix

	verbose('%s:%s uploaded as %s' % (node, upload_filename, repos_filename))
	unix_out('%s %s:%s %s' % (synctool_config.SCP_CMD, interface, upload_filename, repos_filename))

# display short path name
	masterlen = len(synctool_config.MASTERDIR) + 1
	short_repos_filename = '$masterdir/%s' % repos_filename[masterlen:]

	if dry_run:
		stdout('would be uploaded as %s' % short_repos_filename)
	else:
		# make scp command array
		cmd_arr = shlex.split(synctool_config.SCP_CMD)
		cmd_arr.append('%s:%s' % (interface, upload_filename))
		cmd_arr.append(repos_filename)

		synctool_ssh.run_local_cmd(cmd_arr)

		if os.path.isfile(repos_filename):
			stdout('uploaded %s' % short_repos_filename)


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print
	print '  -d, --diff=file                Show diff for file'
	print '  -1, --single=file              Update a single file/run single task'
	print '  -r, --ref=file                 Show which source file synctool chooses'
	print '  -u, --upload=file              Pull a remote file into the overlay tree'
	print '  -s, --suffix=group             Give group suffix for the uploaded file'
	print '  -t, --tasks                    Run the scripts in the tasks/ directory'
	print '  -f, --fix                      Perform updates (otherwise, do dry-run)'
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
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2010'


def get_options():
	global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE, OPT_VERSION, OPT_CHECK_UPDATE, OPT_DOWNLOAD, MASTER_OPTS

#	if len(sys.argv) <= 1:
#		usage()
#		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:d:1:r:u:s:tfqa', ['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'diff=', 'single=', 'ref=', 'upload=', 'suffix=', 'tasks', 'fix', 'quiet', 'aggregate',
			'skip-rsync', 'unix', 'version', 'check-update', 'download'])
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

	synctool_ssh.NODELIST = ''
	synctool_ssh.GROUPLIST = ''

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

	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)

		if arg:
			MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_config.CONF_FILE = arg
			PASS_ARGS.append(opt)
			PASS_ARGS.append(arg)
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			PASS_ARGS.append(opt)
			continue

		if opt in ('-n', '--node'):
			if not synctool_ssh.NODELIST:
				synctool_ssh.NODELIST = arg
			else:
				synctool_ssh.NODELIST = synctool_ssh.NODELIST + ',' + arg
			continue

		if opt in ('-g', '--group'):
			if not synctool_ssh.GROUPLIST:
				synctool_ssh.GROUPLIST = arg
			else:
				synctool_ssh.GROUPLIST = synctool_ssh.GROUPLIST + ',' + arg
			continue

		if opt in ('-x', '--exclude'):
			if not synctool_ssh.EXCLUDELIST:
				synctool_ssh.EXCLUDELIST = arg
			else:
				synctool_ssh.EXCLUDELIST = synctool_ssh.EXCLUDELIST + ',' + arg
			continue

		if opt in ('-X', '--exclude-group'):
			if not synctool_ssh.EXCLUDEGROUPS:
				synctool_ssh.EXCLUDEGROUPS = arg
			else:
				synctool_ssh.EXCLUDEGROUPS = synctool_ssh.EXCLUDEGROUPS + ',' + arg
			continue

		if opt in ('-d', '--diff'):
			opt_diff = True

		if opt in ('-1', '--single'):
			opt_single = True

		if opt in ('-r', '--ref'):
			opt_reference = True

		if opt in ('-u', '--upload'):
			opt_upload = True
			upload_filename = arg
			continue

		if opt in ('-s', '--suffix'):
			opt_suffix = True
			upload_suffix = arg
			continue

		if opt in ('-t', '--tasks'):
			opt_tasks = True

		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True

		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool_lib.DRY_RUN = False

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue

		if opt == '--skip-rsync':
			OPT_SKIP_RSYNC = True
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True

		if opt == '--version':
			OPT_VERSION = True
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

	synctool.option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix)

	return (upload_filename, upload_suffix)


if __name__ == '__main__':
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)

	(upload_filename, upload_suffix) = get_options()

	if OPT_VERSION:
		print synctool_config.VERSION
		sys.exit(0)

	if OPT_CHECK_UPDATE:
		import synctool_update
		sys.exit(synctool_update.check())

	if OPT_DOWNLOAD:
		import synctool_update
		sys.exit(synctool_update.download())

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.read_config()
	synctool_config.add_myhostname()

# ooh ... testing for DRY_RUN doesn't work here
	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
		synctool_lib.openlog()

	nodes = synctool_ssh.make_nodeset()
	if nodes == None:
		sys.exit(1)

	if upload_filename:			# upload a file
		if len(nodes) != 1:
			print "The option --upload can only be run on just one node"
			print "Please use --node=nodename to specify the node to upload from"
			sys.exit(1)
	
		upload(nodes[0], upload_filename, upload_suffix)

	else:						# do regular synctool run
		local_interface = synctool_config.get_node_interface(synctool_config.NODENAME)

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


# EOB
