#! /usr/bin/env python
#
#	synctool-ssh	WJ109
#

import synctool_config

import os
import sys
import string
import getopt


OPT_DEBUG = 0

# these are set by command-line options
NODELIST = None
GROUPLIST = None
EXCLUDELIST = None
EXCLUDEGROUPS = None

# map interface names back to node definition names
NAMEMAP = {}


def make_nodeset(cfg):
	global NAMEMAP

	nodes = []
	explicit_includes = []

	if not NODELIST and not GROUPLIST:
		nodes = synctool_config.get_all_nodes(cfg)

	if NODELIST:
		nodes = string.split(NODELIST, ',')
		explicit_includes = nodes[:]

	if GROUPLIST:
		groups = string.split(GROUPLIST, ',')
		nodes_in_groups = synctool_config.get_nodes_in_groups(cfg, groups)
		nodes.extend(nodes_in_groups)

	excludes = []

	if EXCLUDELIST:
		excludes = string.split(EXCLUDELIST, ',')

	if EXCLUDEGROUPS:
		groups = string.split(EXCLUDEGROUPS, ',')
		nodes_in_groups = synctool_config.get_nodes_in_groups(cfg, groups)
		excludes.extend(nodes_in_groups)

	for node in excludes:
		if node in nodes and not node in explicit_includes:
			nodes.remove(node)

	if len(nodes) <= 0:
		return []

	nodeset = []

	for node in nodes:
		if node in cfg['ignore_groups'] and not node in explicit_includes:
			if OPT_DEBUG:
				print 'debug: %s is ignored' % node
			continue

		iface = synctool_config.get_node_interface(cfg, node)
		NAMEMAP[iface] = node

		if not iface in nodeset:			# make sure we do not have duplicates
			nodeset.append(iface)

	return nodeset


def run_remote_cmd(cfg, nodes, remote_cmd):
	if not cfg.has_key('ssh_cmd'):
		print '%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE)
		sys.exit(-1)

	ssh_cmd = cfg['ssh_cmd']

	run_parallel(cfg, nodes, ssh_cmd, remote_cmd)


def run_parallel(cfg, nodes, cmd, cmd_args, join_char=None):
	if not cfg.has_key('num_proc'):
		num_proc = 16						# use sensible default
	else:
		num_proc = int(cfg['num_proc'])

	parallel = 0

	for node in nodes:
		if OPT_DEBUG:
			if join_char != None:
				print 'debug: %s %s%s%s' % (cmd, node, join_char, cmd_args)
			else:
				print 'debug: %s %s %s' % (cmd, node, cmd_args)
			continue

#
#	run commands in parallel, as many as defined
#
		if parallel > num_proc:
			try:
				if os.wait() != -1:
					parallel = parallel - 1

			except OSError:
				pass

		pid = os.fork()

		if not pid:
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

				print '%s: %s' % (NAMEMAP[node], line)

			f.close()
			sys.exit(0)

		if pid == -1:
			print 'error: failed to fork()'
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


def usage():
	print 'usage: %s [options] <remote command>' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -d, --debug                    Do not run the remote command'
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-ssh by Walter de Jong <walter@sara.nl> (c) 2009'


def get_options():
	global NODELIST, GROUPLIST, EXCLUDELIST, EXCLUDEGROUPS, REMOTE_CMD, OPT_DEBUG

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:dn:g:x:X:", ['help', 'conf=', 'debug', 'node=', 'group=', 'exclude=', 'exclude-group='])
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

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_config.CONF_FILE = arg
			continue

		if opt in ('-d', '--debug'):
			OPT_DEBUG = 1
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

	if args == None or len(args) <= 0:
		print '%s: missing remote command' % os.path.basename(sys.argv[0])
		sys.exit(1)

	return string.join(args)


if __name__ == '__main__':
	cmd = get_options()
	cfg = synctool_config.read_config()

	nodes = make_nodeset(cfg)
	run_remote_cmd(cfg, nodes, cmd)


# EOB
