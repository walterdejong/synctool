#! /usr/bin/env python
#
#	synctool-ssh	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2010
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_unbuffered
import synctool_config
import synctool_aggr
import synctool_lib

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt
import shlex

# these are set by command-line options
NODELIST = None
GROUPLIST = None
EXCLUDELIST = None
EXCLUDEGROUPS = None

# map interface names back to node definition names
NAMEMAP = {}

OPT_AGGREGATE = False
OPT_NODENAME = True
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
		all_groups = synctool_config.make_all_groups()
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


def get_nodename_from_interface(iface):
	if NAMEMAP.has_key(iface):
		return NAMEMAP[iface]

	return iface


def run_remote_cmd(nodes, remote_cmd_args):
	'''nodes[] is nodeset to run on'''
	'''remote_cmd_args[] is array of command + arguments'''
	'''join_char is ':' or None'''

	if not synctool_config.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	cmd = synctool_config.SSH_CMD
	cmd_args = shlex.split(cmd)

# cmd_str is used for printing info only
	cmd_str = string.join(remote_cmd_args)

	parallel = 0

	for node in nodes:
		if node == synctool_config.NODENAME:
			verbose('running %s' % cmd_str)
			unix_out(cmd_str)
		else:
			the_command = os.path.basename(cmd_args[0])
			verbose('running %s to %s %s' % (the_command, NAMEMAP[node], cmd_str))
			unix_out('%s %s %s' % (cmd, node, cmd_str))

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
			_run_command(cmd_args, node, None, remote_cmd_args)
			sys.exit(0)

		if pid == -1:
			stderr('error: failed to fork()')
		else:
			parallel = parallel + 1

#
#	wait for children to terminate
#
	while True:
		try:
			if os.wait() == -1:
				break

		except OSError:
			break


def _run_command(cmd_arr, node, join_char, cmd_args):
	'''cmd_arr[] is an array that can be passed to e.g. os.execv(), or synctool_lib.popen()
	cmd_args[] contains the additional arguments to the command
	The resulting command will be: cmd_arr + node + join_char + cmd_args'''

#
#	is this node the local node?
#
	if node == synctool_config.NODENAME:
		run_local_cmd(cmd_args)
		return

	nodename = NAMEMAP[node]

# make the command arguments ready for synctool_lib.popen()
	if join_char:
		cmd_args[0] = '%s%s%s' % (node, join_char, cmd_args[0])
	else:
		cmd_arr.append(node)
	cmd_arr.extend(cmd_args)

# execute remote command and show output with the nodename
	f = synctool_lib.popen(cmd_arr)

	while True:
		line = f.readline()
		if not line:
			break

		line = string.strip(line)

# pass output on; simply use 'print' rather than 'stdout()'
# do not prepend the nodename of this node to the output if option --no-nodename was given
		if line[:15] == '%synctool-log% ':
			if line[15:] == '--':
				pass
			else:
				synctool_lib.masterlog('%s: %s' % (nodename, line[15:]))
		else:
			if OPT_NODENAME:
				print '%s: %s' % (nodename, line)
			else:
				print line

	f.close()


def run_parallel_cmds(nodes, cmds):
	'''fork and run multiple commands in sequence
	cmds[] is an array of tuples (cmd_arr[], cmd_args[], join_char)
	cmd_arr[] is an array that can be passed to e.g. os.execv(), or synctool_lib.popen()
	cmd_args[] contains the additional arguments to the command

	The resulting command will be: cmd_arr + node + join_char + cmd_args'''

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
			for (cmd_arr, cmd_args, join_char) in cmds:
# show what we're going to do
				the_command = os.path.basename(cmd_arr[0])
				if node == synctool_config.NODENAME:
					cmd_str = string.join(cmd_args)
					verbose('running %s %s' % (the_command, cmd_str))
					unix_out('%s %s' % (string.join(cmd_arr), cmd_str))
				else:
					if join_char:
						cmd_str = '%s%s%s' % (NAMEMAP[node], join_char, string.join(cmd_args))
					else:
						cmd_str = '%s %s' % (NAMEMAP[node], string.join(cmd_args))

					verbose('running %s %s' % (the_command, cmd_str))

					if join_char:
						cmd_str = '%s%s%s' % (node, join_char, string.join(cmd_args))
					else:
						cmd_str = '%s %s' % (node, string.join(cmd_args))

					unix_out('%s %s' % (string.join(cmd_arr), cmd_str))

# the rsync must run, even for dry runs
#				if synctool_lib.DRY_RUN:
#					continue

				_run_command(cmd_arr, node, join_char, cmd_args)

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


def run_local_cmd(cmd_args):
	'''run command on the local host'''

	cmd_str = string.join(cmd_args)

	verbose('running command %s' % cmd_str)
	unix_out(cmd_str)

	if synctool_lib.DRY_RUN:
		return

	f = synctool_lib.popen(cmd_args)

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
				synctool_lib.masterlog('%s: %s' % (synctool_config.NODENAME, line[15:]))
		else:
			print '%s: %s' % (synctool_config.NODENAME, line)

	f.close()


def usage():
	print 'usage: %s [options] <remote command>' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print '  -a, --aggregate                Condense output'
	print
	print '  -v, --verbose                  Be verbose'
	print '  -N, --no-nodename              Do not prepend nodename to output'
	print '      --unix                     Output actions as unix shell commands'
	print '      --dry-run                  Do not run the remote command'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-ssh by Walter de Jong <walter@heiho.net> (c) 2009-2010'


def get_options():
	global NODELIST, GROUPLIST, EXCLUDELIST, EXCLUDEGROUPS, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE, OPT_NODENAME

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aNq', ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'aggregate', 'no-nodename', 'unix', 'dry-run', 'quiet'])
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
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
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
			OPT_AGGREGATE = True
			continue

		if opt in ('-N', '--no-nodename'):
			OPT_NODENAME = False
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue

		if opt == '--dry-run':
			synctool_lib.DRY_RUN = True
			continue

		if opt in ('-q', '--quiet'):
			# silently ignore this option
			continue

	if args == None or len(args) <= 0:
		print '%s: missing remote command' % os.path.basename(sys.argv[0])
		sys.exit(1)

	if args != None:
		MASTER_OPTS.extend(args)

	return args


if __name__ == '__main__':
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)

	cmd_args = get_options()

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.read_config()
	synctool_config.add_myhostname()

	nodes = make_nodeset()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)

	run_remote_cmd(nodes, cmd_args)


# EOB
