#! /usr/bin/env python
#
#	synctool_master.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2009
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
	'''run synctool_cmd locally on this host'''

	if not synctool_config.SYNCTOOL_CMD:
		stderr('%s: error: synctool_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	synctool_ssh.run_local_cmd(shlex.split(synctool_config.SYNCTOOL_CMD) + PASS_ARGS)


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
	print '  -T, --tier                     Sync with other synctool-masters'
	print '  -l, --log=logfile              Log taken actions to logfile'
	print '  -v, --verbose                  Be verbose'
	print '  -q, --quiet                    Suppress informational startup messages'
	print '  -a, --aggregate                Condense output; list nodes per change'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@sara.nl> (c) 2003-2009'


def get_options():
	global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE, MASTER_OPTS

#	if len(sys.argv) <= 1:
#		usage()
#		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:vn:g:x:X:d:1:tfql:aT", ['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'diff=', 'single=', 'tasks', 'fix', 'quiet', 'log=', 'aggregate', 'tier', 'skip-rsync', 'unix'])
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
			synctool_lib.VERBOSE = 1
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
			synctool_lib.QUIET = 1
			PASS_ARGS.append(opt)
			continue

		if opt in ('-f', '--fix'):
			synctool_lib.DRY_RUN = 0
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

		if opt in ('-l', '--log'):
			synctool_lib.LOGFILE = arg
			PASS_ARGS.append(opt)
			PASS_ARGS.append(arg)
			continue

		if opt in ('-T', '--tier'):
			synctool_ssh.MULTI_TIER = synctool_ssh.MULTI_TIER + 1
			if synctool_ssh.MULTI_TIER > 1:
				PASS_ARGS.append(opt)
			continue

		PASS_ARGS.append(opt)

		if arg != None:
			PASS_ARGS.append(arg)

	if args != None:
		MASTER_OPTS.extend(args)
		PASS_ARGS.extend(args)


if __name__ == '__main__':
	get_options()

	synctool_lib.openlog()

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		synctool_lib.closelog()
		sys.exit(0)

	synctool_config.read_config()
	synctool_config.add_myhostname()

#############
#
#	enable debugging
#
#############
#	synctool_config.OPT_DEBUG = True
#	synctool_ssh.OPT_DEBUG = True

	nodes = synctool_ssh.make_nodeset()
	if nodes == None:
		sys.exit(1)

#
#	see if we need to run synctool locally, on the current host
#
	if synctool_config.NODENAME != None:
		iface = synctool_config.get_node_interface(synctool_config.NODENAME)
		if iface in nodes:
			nodes.remove(iface)
			run_local_synctool()

	if len(nodes) > 0:
		run_remote_synctool(nodes)

	synctool_lib.closelog()


# EOB
