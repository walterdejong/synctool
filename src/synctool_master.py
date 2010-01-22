#! /usr/bin/env python
#
#	synctool_master.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2009
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

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt
import shlex

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False

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
	print '  -t, --tasks                    Run the scripts in the tasks/ directory'
	print '  -f, --fix                      Perform updates (otherwise, do dry-run)'
	print '      --unix                     Output actions as unix shell commands'
	print '      --skip-rsync               Do not sync the repository'
	print '                                 (eg. when it is on a shared filesystem)'
	print '  -v, --verbose                  Be verbose'
	print '  -q, --quiet                    Suppress informational startup messages'
	print '  -a, --aggregate                Condense output; list nodes per change'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2009'


def get_options():
	global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE, MASTER_OPTS

#	if len(sys.argv) <= 1:
#		usage()
#		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:d:1:tfqa', ['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'diff=', 'single=', 'tasks', 'fix', 'quiet', 'aggregate', 'skip-rsync', 'unix'])
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

	PASS_ARGS = []
	MASTER_OPTS = [ sys.argv[0] ]

	for opt, arg in opts:
		MASTER_OPTS.append(opt)
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

		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True
			PASS_ARGS.append(opt)
			continue

		if opt in ('-f', '--fix'):
			synctool_lib.DRY_RUN = False
			PASS_ARGS.append(opt)
			continue

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue

		if opt == '--skip-rsync':
			OPT_SKIP_RSYNC = True
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			PASS_ARGS.append(opt)
			continue

		PASS_ARGS.append(opt)

		if arg != None:
			PASS_ARGS.append(arg)

# enable logging at the master node
	PASS_ARGS.append('--masterlog')

	if args != None:
		MASTER_OPTS.extend(args)
		PASS_ARGS.extend(args)


if __name__ == '__main__':
	get_options()

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

	for node in nodes:
#
#	is this node the localhost? then run locally
#
		if node == synctool_config.NODENAME:
			run_local_synctool()
			nodes.remove(node)
			break

	run_remote_synctool(nodes)

	synctool_lib.closelog()


# EOB
