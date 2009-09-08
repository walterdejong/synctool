#! /usr/bin/env python
#
#	synctool-ssh	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2009
#

import synctool_config
import synctool_lib

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt


# these are set by command-line options
NODELIST = None
GROUPLIST = None
EXCLUDELIST = None
EXCLUDEGROUPS = None

# map interface names back to node definition names
NAMEMAP = {}

OPT_AGGREGATE = 0
MASTER_OPTS = None


def make_nodeset():
	global NAMEMAP

	nodes = []
	explicit_includes = []

	if not NODELIST and not GROUPLIST:
		nodes = synctool_config.get_all_nodes()

	if NODELIST:
		nodes = string.split(NODELIST, ',')
		explicit_includes = nodes[:]

# check if the nodes exist at all
	all_nodes = synctool_config.get_all_nodes()
	for node in nodes:
		if not node in all_nodes:
			stderr("no such node '%s'" % node)
			return None

	if GROUPLIST:
		groups = string.split(GROUPLIST, ',')

# check if the groups exist at all
		all_groups = synctool_config.get_all_groups()
		for group in groups:
			if not group in all_groups:
				stderr("no such group '%s'" % group)
				return None

		nodes_in_groups = synctool_config.get_nodes_in_groups(groups)
		nodes.extend(nodes_in_groups)

	excludes = []

	if EXCLUDELIST:
		excludes = string.split(EXCLUDELIST, ',')

	if EXCLUDEGROUPS:
		groups = string.split(EXCLUDEGROUPS, ',')
		nodes_in_groups = synctool_config.get_nodes_in_groups(groups)
		excludes.extend(nodes_in_groups)

	for node in excludes:
		if node in nodes and not node in explicit_includes:
			nodes.remove(node)

	if len(nodes) <= 0:
		return []

	nodeset = []

	for node in nodes:
		if node in synctool_config.IGNORE_GROUPS and not node in explicit_includes:
			verbose('node %s is ignored' % node)
			continue

		groups = synctool_config.get_groups(node)
		do_continue = 0
		for group in groups:
			if group in synctool_config.IGNORE_GROUPS:
				verbose('group %s is ignored' % group)
				do_continue = 1
				break

		if do_continue:
			continue

		iface = synctool_config.get_node_interface(node)
		NAMEMAP[iface] = node

		if not iface in nodeset:			# make sure we do not have duplicates
			nodeset.append(iface)

	return nodeset


def run_remote_cmd(nodes, remote_cmd):
	if not synctool_config.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	run_parallel(nodes, synctool_config.SSH_CMD, remote_cmd)


def run_parallel(nodes, cmd, cmd_args, join_char=None):
	parallel = 0

	for node in nodes:
		if node == synctool_config.NODENAME:
			verbose('running %s' % cmd_args)
			unix_out(cmd_args)
		else:
			the_command = string.split(cmd)
			the_command = the_command[0]
			the_command = os.path.basename(the_command)

			if join_char != None:
				verbose('running %s to %s%s%s' % (the_command, node, join_char, cmd_args))
				unix_out('%s %s%s%s' % (cmd, node, join_char, cmd_args))
			else:
				verbose('running %s to %s %s' % (the_command, node, cmd_args))
				unix_out('%s %s %s' % (cmd, node, cmd_args))

		if synctool_lib.DRY_RUN:
			continue
#
#	run commands in parallel, as many as defined
#
		if parallel > synctool_config.NUM_PROC:
			try:
				if os.wait() != -1:
					parallel = parallel - 1

			except OSError:
				pass

		pid = os.fork()

		if not pid:
#
#	is this node the localhost? then run locally
#
			if node == synctool_config.NODENAME:
				run_local_cmd(cmd_args)
				sys.exit(0)

#
#	execute remote command and show output with the nodename
#
			if join_char != None:
				f = os.popen('%s %s%s%s 2>&1' % (cmd, node, join_char, cmd_args), 'r')
			else:
				f = os.popen('%s %s %s 2>&1' % (cmd, node, cmd_args), 'r')

			while 1:
				line = f.readline()
				if not line:
					break

				line = string.strip(line)

				stdout('%s: %s' % (NAMEMAP[node], line))

			f.close()
			sys.exit(0)

		if pid == -1:
			stderr('error: failed to fork()')
		else:
			parallel = parallel + 1

#
#	wait for children to terminate
#
	while 1:
		try:
			if os.wait() == -1:
				break

		except OSError:
			break


def run_parallel_cmds(nodes, cmds):
	'''fork and run multiple commands in sequence'''
	'''cmds[] is an array of tuples (cmd, cmd_args, join_char)'''

	parallel = 0

	for node in nodes:
#
#	run commands in parallel, as many as defined
#
		if parallel > synctool_config.NUM_PROC:
			try:
				if os.wait() != -1:
					parallel = parallel - 1

			except OSError:
				pass

		pid = os.fork()

		if not pid:
#
#	run the commands one after another
#
			for (cmd, cmd_args, join_char) in cmds:
# show what we're going to do
				if node == synctool_config.NODENAME:
					verbose('running %s' % cmd_args)
					unix_out(cmd_args)
				else:
					the_command = string.split(cmd)
					the_command = the_command[0]
					the_command = os.path.basename(the_command)

				if join_char != None:
					verbose('running %s to %s%s%s' % (the_command, node, join_char, cmd_args))
					unix_out('%s %s%s%s' % (cmd, node, join_char, cmd_args))
				else:
					verbose('running %s to %s %s' % (the_command, node, cmd_args))
					unix_out('%s %s %s' % (cmd, node, cmd_args))

# the rysnc must run, even for dry runs
#				if synctool_lib.DRY_RUN:
#					continue

#
#	is this node the localhost? then run locally
#
				if node == synctool_config.NODENAME:
					run_local_cmd(cmd_args)
					continue

#
#	execute remote command and show output with the nodename
#
				if join_char != None:
					f = os.popen('%s %s%s%s 2>&1' % (cmd, node, join_char, cmd_args), 'r')
				else:
					f = os.popen('%s %s %s 2>&1' % (cmd, node, cmd_args), 'r')

				lines = f.readlines()		# collect output
				f.close()

				lines = map(string.strip, lines)

				for line in lines:
					stdout('%s: %s' % (NAMEMAP[node], line))

# all done, child exits
			sys.exit(0)

		if pid == -1:
			stderr('error: failed to fork()')
		else:
			parallel = parallel + 1

#
#	wait for children to terminate
#
	while 1:
		try:
			if os.wait() == -1:
				break

		except OSError:
			break


def run_local_cmd(cmd):
	verbose('running command %s' % cmd)
	unix_out(cmd)

	if synctool_lib.DRY_RUN:
		return

	f = os.popen('%s 2>&1' % cmd, 'r')
	lines = f.readlines()
	f.close()

	lines = map(string.strip, lines);

	for line in lines:
		stdout('%s: %s' % (NAMEMAP[synctool_config.NODENAME], line))


def run_local_cmds(cmds):
	for cmd in cmds:
		run_local_cmd(cmd)


def run_with_aggregate():
	'''pipe the output through the aggregator'''

	global MASTER_OPTS
#
#	simply re-run this command, but with a pipe
#
	if '-a' in MASTER_OPTS:
		MASTER_OPTS.remove('-a')

	if '--aggregate' in MASTER_OPTS:
		MASTER_OPTS.remove('--aggregate')

	f = os.popen('%s %s' % (sys.argv[0], string.join(MASTER_OPTS)), 'r')
	synctool_aggr.aggregate(f)
	f.close()


def usage():
	print 'usage: %s [options] <remote command>' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -v, --verbose                  Be verbose'
	print
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print '  -a, --aggregate                Condense output'
	print
	print '      --unix                     Output actions as unix shell commands'
	print '      --dry-run                  Do not run the remote command'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-ssh by Walter de Jong <walter@sara.nl> (c) 2009'


def get_options():
	global NODELIST, GROUPLIST, EXCLUDELIST, EXCLUDEGROUPS, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:vn:g:x:X:", ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'unix', 'dry-run'])
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

	NODELIST = ''
	GROUPLIST = ''

	MASTER_OPTS = []

	for opt, arg in opts:
		MASTER_OPTS.append(opt)
		MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_config.CONF_FILE = arg
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = 1
			continue

		if opt in ('-n', '--node'):
			if not NODELIST:
				NODELIST = arg
			else:
				NODELIST = NODELIST + ',' + arg
			continue

		if opt in ('-g', '--group'):
			if not GROUPLIST:
				GROUPLIST = arg
			else:
				GROUPLIST = GROUPLIST + ',' + arg
			continue

		if opt in ('-x', '--exclude'):
			if not EXCLUDELIST:
				EXCLUDELIST = arg
			else:
				EXCLUDELIST = EXCLUDELIST + ',' + arg
			continue

		if opt in ('-X', '--exclude-group'):
			if not EXCLUDEGROUPS:
				EXCLUDEGROUPS = arg
			else:
				EXCLUDEGROUPS = EXCLUDEGROUPS + ',' + arg
			continue

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = 1
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = 1
			continue

		if opt == '--dry-run':
			synctool_lib.DRY_RUN = 1
			continue

	if args == None or len(args) <= 0:
		print '%s: missing remote command' % os.path.basename(sys.argv[0])
		sys.exit(1)

	return string.join(args)


if __name__ == '__main__':
	cmd = get_options()

	if OPT_AGGREGATE:
		run_with_aggregate()
		sys.exit(0)

	synctool_config.read_config()
	synctool_config.add_myhostname()

	nodes = make_nodeset()
	if nodes == None:
		sys.exit(1)

	run_remote_cmd(nodes, cmd)


# EOB
