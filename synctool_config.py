#! /usr/bin/env python
#
#	synctool-config	WJ109
#

import os
import sys
import string
import socket
import getopt


DEFAULT_CONF='/var/lib/synctool/synctool.conf'
CONF_FILE=DEFAULT_CONF

ACTION = 0
ACTION_OPTION = None
ARG_NODENAMES = None
ARG_GROUPS = None

# these are enums for the "list" command-line options
ACTION_LIST_NODES = 1
ACTION_LIST_GROUPS = 2
ACTION_NODES = 3
ACTION_GROUPS = 4

# optional: do not list hosts/groups that are ignored
OPT_FILTER_IGNORED = 0
# optional: list interface names for the selected nodes
OPT_INTERFACE = 0


def stdout(str):
	print str


def stderr(str):
	sys.stderr.write(str + '\n')


def read_config():
	'''read the config file and return cfg structure'''

	cfg = {}
	cfg['ignore_groups'] = []

	if os.path.isdir(CONF_FILE):
		filename = os.path.join(filename, CONF_FILE)

# funky ... it is possible to open() directories without problems ...
	if not os.path.isfile(CONF_FILE):
		stderr("no such config file '%s'" % CONF_FILE)
		sys.exit(-1)

	try:
		cwd = os.getcwd()
	except OSError, reason:
		cwd = '.'

	filename = os.path.join(cwd, CONF_FILE)

	try:
		f = open(filename, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (CONF_FILE, reason))
		sys.exit(-1)

	lineno = 0
	errors = 0

	while 1:
		line = f.readline()
		if not line:
			break

		lineno = lineno + 1

		line = string.strip(line)
		if not line:
			continue

		if line[0] == '#':
			continue

		arr = string.split(line)
		if len(arr) <= 1:
			stderr('%s:%d: syntax error ; expected key/value pair' % (CONF_FILE, lineno))
			errors = errors + 1
			continue

		keyword = string.lower(arr[0])

#
#	keyword: masterdir
#
		if keyword == 'masterdir':
			if cfg.has_key('masterdir'):
				stderr("%s:%d: redefinition of masterdir" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cfg['masterdir'] = arr[1]
			continue

#
#	keyword: symlink_mode
#
		if keyword == 'symlink_mode':
			if cfg.has_key('symlink_mode'):
				stderr("%s:%d: redefinition of symlink_mode" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			try:
				mode = int(arr[1], 8)
			except ValueError:
				stderr("%s:%d: invalid argument for symlink_mode" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cfg['symlink_mode'] = mode
			continue

#
#	keyword: host / node
#
		if keyword == 'host' or keyword == 'node':
			if len(arr) < 2:
				stderr("%s:%d: '%s' requires at least 1 argument: the hostname" % (CONF_FILE, lineno, keyword))
				errors = errors + 1
				continue

			if not cfg.has_key('host'):
				cfg['host'] = {}

			host = arr[1]
			groups = arr[2:]

			if cfg['host'].has_key(host):
				stderr("%s:%d: redefinition of node %s" % (CONF_FILE, lineno, host))
				errors = errors + 1
				continue

			if groups[-1][:10] == 'interface:':
				interface = groups[-1][10:]
				groups = groups[:-1]

				if not cfg.has_key('interfaces'):
					cfg['interfaces'] = {}

				if cfg['interfaces'].has_key(host):
					stderr("%s:%d: redefinition of interface for node %s" % (CONF_FILE, lineno, host))
					errors = errors + 1
					continue

				cfg['interfaces'][host] = interface

			if len(groups) > 0:
				cfg['host'][host] = groups

			continue

#
#	keyword: ignore_host / ignore_node
#
		if keyword == 'ignore_host' or keyword == 'ignore_node':
			if len(arr) < 2:
				stderr("%s:%d: '%s' requires 1 argument: the hostname to ignore" % (CONF_FILE, lineno, keyword))
				errors = errors + 1
				continue

			cfg['ignore_groups'].append(arr[1])
			continue

#
#	keyword: ignore_group
#
		if keyword == 'ignore_group':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_group' requires at least 1 argument: the group to ignore" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cfg['ignore_groups'].extend(arr[1:])
			continue

#
#	keyword: on_update
#
		if keyword == 'on_update':
			if len(arr) < 3:
				stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('on_update'):
				cfg['on_update'] = {}

			file = arr[1]
			cmd = string.join(arr[2:])

			if cfg['on_update'].has_key(file):
				stderr("%s:%d: redefinition of on_update %s" % (CONF_FILE, lineno, file))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[2][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (CONF_FILE, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[2])
			else:
				full_cmd = arr[2]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['on_update'][file] = cmd
			continue

#
#	keyword: always_run
#
		if keyword == 'always_run':
			if len(arr) < 2:
				stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('always_run'):
				cfg['always_run'] = []

			cmd = string.join(arr[1:])

			if cmd in cfg['always_run']:
				stderr("%s:%d: same command defined again: %s" % (CONF_FILE, lineno, cmd))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[1][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (CONF_FILE, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[1])
			else:
				full_cmd = arr[1]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['always_run'].append(cmd)
			continue

#
#	keyword: diff_cmd
#
		if keyword == 'diff_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'diff_cmd' requires an argument: the full path to the 'diff' command" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('diff_cmd'):
				stderr("%s:%d: redefinition of diff_cmd" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, cmd))
				errors = errors + 1
				continue

			cfg['diff_cmd'] = string.join(arr[1:])
			continue

#
#	keyword: ssh_cmd
#
		if keyword == 'ssh_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'ssh_cmd' requires an argument: the full path to the 'ssh' command" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('ssh_cmd'):
				stderr("%s:%d: redefinition of ssh_cmd" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, cmd))
				errors = errors + 1
				continue

			cfg['ssh_cmd'] = string.join(arr[1:])
			continue

#
#	keyword: rsync_cmd
#
		if keyword == 'rsync_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'rsync_cmd' requires an argument: the full path to the 'rsync' command" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('rsync_cmd'):
				stderr("%s:%d: redefinition of rsync_cmd" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, cmd))
				errors = errors + 1
				continue

			cfg['rsync_cmd'] = string.join(arr[1:])
			continue

#
#	keyword: synctool_cmd
#
		if keyword == 'synctool_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'synctool_cmd' requires an argument: the full path to the remote 'synctool' command" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('synctool_cmd'):
				stderr("%s:%d: redefinition of synctool_cmd" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (CONF_FILE, lineno, cmd))
				errors = errors + 1
				continue

			cfg['synctool_cmd'] = string.join(arr[1:])
			continue

#
#	keyword: num_proc
#
		if keyword == 'num_proc':
			if cfg.has_key('num_proc'):
				stderr("%s:%d: redefinition of num_proc" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			try:
				num_proc = int(arr[1])
			except ValueError:
				stderr("%s:%d: invalid argument for num_proc" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			if num_proc < 1:
				stderr("%s:%d: invalid argument for num_proc" % (CONF_FILE, lineno))
				errors = errors + 1
				continue

			cfg['num_proc'] = num_proc
			continue

		stderr("%s:%d: unknown keyword '%s'" % (CONF_FILE, lineno, keyword))
		errors = errors + 1

	f.close()

	if not cfg.has_key('masterdir'):
		cfg['masterdir'] = '.'

	if errors > 0:
		sys.exit(-1)

# implicitly add 'hostname' as first group
	for host in cfg['host'].keys():
		if not host in cfg['host'][host]:
			cfg['host'][host].insert(0, host)

	return cfg


def add_myhostname(cfg):
	'''add the hostname of the current host to the configuration, so that it can be used'''

#
#	get my hostname
#
	hostname = socket.gethostname()
	arr = string.split(hostname, '.')
	cfg['hostname'] = arr[0]

	if cfg['host'].has_key(hostname):
		if arr[0] != hostname and cfg['host'].has_key(arr[0]):
			stderr("%s: conflict; host %s and %s are both defined" % (CONF_FILE, hostname, arr[0]))
			sys.exit(-1)
	else:
		if cfg['host'].has_key(arr[0]):
			hostname = arr[0]

	if cfg['host'].has_key(hostname):
		cfg['host'][hostname].insert(0, hostname)		# implicitly add 'hostname' as first group


# remove ignored groups from all hosts
def remove_ignored_groups(cfg):
	for host in cfg['host'].keys():
		changed = 0
		groups = cfg['host'][host]
		for ignore in cfg['ignore_groups']:
			if ignore in groups:
				groups.remove(ignore)
				changed = 1

		if changed:
			cfg['host'][host] = groups


def get_all_nodes(cfg):
	return cfg['host'].keys()


def get_node_interface(cfg, node):
	if cfg.has_key('interfaces') and cfg['interfaces'].has_key(node):
		return cfg['interfaces'][node]

	return node


def list_all_nodes(cfg):
	nodes = get_all_nodes(cfg)
	nodes.sort()

	for host in nodes:
		if host in cfg['ignore_groups']:
			if OPT_INTERFACE:
				host = get_node_interface(cfg, host)

			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % host
		else:
			if OPT_INTERFACE:
				host = get_node_interface(cfg, host)

			print host


def make_all_groups(cfg):
	'''make a list of all possible groups'''

	all_groups = []
	host_dict = cfg['host']
	for host in host_dict.keys():
		for group in host_dict[host]:
			if not group in all_groups:
				all_groups.append(group)

	all_groups.extend(cfg['ignore_groups'])		# although ignored, they are existing groups
	return all_groups


def get_all_groups(cfg):
	arr = []

	nodes = cfg['host'].keys()

	for group in make_all_groups(cfg):
		if not group in arr:
			arr.append(group)

	return arr


def list_all_groups(cfg):
	groups = get_all_groups(cfg)
	groups.sort()

	for group in groups:
		if group in cfg['ignore_groups']:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_nodes(cfg, nodenames):
	arr = []

	for nodename in nodenames:
		if cfg['host'].has_key(nodename):
			for group in cfg['host'][nodename]:
				if not group in arr:
					arr.append(group)

	return arr


def list_nodes(cfg, nodenames):
	for nodename in nodenames:
		if not cfg['host'].has_key(nodename):
			stderr("no such node '%s' defined" % nodename)
			sys.exit(1)

	groups = get_nodes(cfg, nodenames)
	groups.sort()

	for group in groups:
		if group in cfg['ignore_groups']:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_nodegroups(cfg, nodegroups):
	arr = []

	nodes = cfg['host'].keys()

	for nodegroup in nodegroups:
		for node in nodes:
			if nodegroup in cfg['host'][node] and not node in arr:
				arr.append(node)

	return arr


def list_nodegroups(cfg, nodegroups):
	all_groups = make_all_groups(cfg)

	for nodegroup in nodegroups:
		if not nodegroup in all_groups:
			stderr("no such nodegroup '%s' defined" % nodegroup)
			sys.exit(1)

	arr = get_nodegroups(cfg, nodegroups)
	arr.sort()

	for node in arr:
		if node in cfg['ignore_groups']:
			if OPT_INTERFACE:
				node = get_node_interface(cfg, node)

			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % node
		else:
			if OPT_INTERFACE:
				node = get_node_interface(cfg, node)

			print node


def set_action(a, opt):
	global ACTION, ACTION_OPTION

	if ACTION > 0:
		stderr('the options %s and %s can not be combined' % (ACTION_OPTION, opt))
		sys.exit(1)

	ACTION = a
	ACTION_OPTION = opt


def usage():
	print 'usage: %s [options] [<argument>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help               Display this information'
	print '  -c, --conf=dir/file      Use this config file (default: %s)' % DEFAULT_CONF
	print '  -l, --list-nodes         List all configured nodes'
	print '  -L, --list-groups        List all configured groups'
	print '  -n, --node=nodelist      List all groups this node is in'
	print '  -g, --group=grouplist    List all nodes in this group'
	print '  -i, --interface          List selected nodes by interface'
	print '  -f, --filter-ignored     Do not list ignored nodes and groups'
	print
	print 'A node/group list can be a single value, or a comma-separated list'


def get_options():
	global CONF_FILE, ARG_NODENAMES, ARG_GROUPS, OPT_FILTER_IGNORED, OPT_INTERFACE

	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:lLn:g:if", ['help', 'conf=', 'list-nodes', 'list-groups', 'node=', 'group=', 'interface', 'filter-ignored'])
		except getopt.error, (reason):
			print
			print '%s: %s' % (progname, reason)
			print
			usage()
			sys.exit(1)

		except getopt.GetoptError, (reason):
			print
			print '%s: %s' % (progname, reason)
			print
			usage()
			sys.exit(1)

		except:
			usage()
			sys.exit(1)

		errors = 0

		for opt, arg in opts:
			if opt in ('-h', '--help', '-?'):
				usage()
				sys.exit(1)

			if opt in ('-c', '--conf'):
				CONF_FILE=arg
				continue

			if opt in ('-l', '--list-nodes'):
				set_action(ACTION_LIST_NODES, '--list-nodes')
				continue

			if opt in ('-L', '--list-groups'):
				set_action(ACTION_LIST_GROUPS, '--list-groups')
				continue

			if opt in ('-n', '--node'):
				set_action(ACTION_NODES, '--node')
				ARG_NODENAMES = string.split(arg, ',')
				continue

			if opt in ('-g', '--group'):
				set_action(ACTION_GROUPS, '--group')
				ARG_GROUPS = string.split(arg, ',')
				continue

			if opt in ('-i', '--interface'):
				OPT_INTERFACE = 1
				continue

			if opt in ('-f', '--filter-ignored'):
				OPT_FILTER_IGNORED = 1
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command-line')
		sys.exit(1)

	if not ACTION:
		usage()
		sys.exit(1)



if __name__ == '__main__':
	get_options()

	cfg = read_config()

	if ACTION == ACTION_LIST_NODES:
		list_all_nodes(cfg)

	elif ACTION == ACTION_LIST_GROUPS:
		list_all_groups(cfg)

	elif ACTION == ACTION_NODES:
		if not ARG_NODENAMES:
			stderr("option '--node' requires an argument; the node name")
			sys.exit(1)

		list_nodes(cfg, ARG_NODENAMES)

	elif ACTION == ACTION_GROUPS:
		if not ARG_GROUPS:
			stderr("option '--node-group' requires an argument; the node group name")
			sys.exit(1)

		list_nodegroups(cfg, ARG_GROUPS)


# EOB
