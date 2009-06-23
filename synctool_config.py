#! /usr/bin/env python
#
#	synctool-config	WJ109
#

import os
import sys
import string
import socket
import getopt


DEFAULT_CONF='synctool.conf'
CONF_FILE=DEFAULT_CONF

ACTION = 0
ACTION_OPTION = None
ARG_NODENAMES = None
ARG_NODEGROUPS = None

# these are enums for the "list" command-line options
ACTION_LIST_NODES = 1
ACTION_LIST_GROUPS = 2
ACTION_NODES = 3
ACTION_NODEGROUPS = 4
ACTION_INTERFACES = 5
ACTION_GROUP_INTERFACES = 6



def stdout(str):
	print str


def stderr(str):
	sys.stderr.write(str + '\n')


def read_config(filename):
	'''read the config file and return cfg structure'''

	if not filename:
		filename = os.path.join('.', DEFAULT_CONF)

	cfg = {}
	cfg['ignore_groups'] = []

	if os.path.isdir(filename):
		filename = os.path.join(filename, DEFAULT_CONF)

# funky ... it is possible to open() directories without problems ...
	if not os.path.isfile(filename):
		stderr("no such config file '%s'" % filename)
		sys.exit(-1)

	try:
		cwd = os.getcwd()
	except OSError, reason:
		cwd = '.'

	filename = os.path.join(cwd, filename)

	try:
		f = open(filename, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (filename, reason))
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
			stderr('%s:%d: syntax error ; expected key/value pair' % (filename, lineno))
			errors = errors + 1
			continue

		keyword = string.lower(arr[0])

#
#	keyword: masterdir
#
		if keyword == 'masterdir':
			if cfg.has_key('masterdir'):
				stderr("%s:%d: redefinition of masterdir" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['masterdir'] = arr[1]
			continue

#
#	keyword: symlink_mode
#
		if keyword == 'symlink_mode':
			if cfg.has_key('symlink_mode'):
				stderr("%s:%d: redefinition of symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			try:
				mode = int(arr[1], 8)
			except ValueError:
				stderr("%s:%d: invalid argument for symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['symlink_mode'] = mode
			continue

#
#	keyword: host
#
		if keyword == 'host':
			if len(arr) < 2:
				stderr("%s:%d: 'host' requires at least 1 argument: the hostname" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('host'):
				cfg['host'] = {}

			host = arr[1]
			groups = arr[2:]

			if cfg['host'].has_key(host):
				stderr("%s:%d: redefinition of host %s" % (filename, lineno, host))
				errors = errors + 1
				continue

			if groups[-1][:10] == 'interface:':
				interface = groups[-1][10:]
				groups = groups[:-1]

				if not cfg.has_key('interfaces'):
					cfg['interfaces'] = {}

				if cfg['interfaces'].has_key(host):
					stderr("%s:%d: redefinition of interface for host %s" % (filename, lineno, host))
					errors = errors + 1
					continue

				cfg['interfaces'][host] = interface

			if len(groups) > 0:
				cfg['host'][host] = groups

			continue

#
#	keyword: ignore_host
#
		if keyword == 'ignore_host':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_host' requires 1 argument: the hostname to ignore" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['ignore_groups'].append(arr[1])
			continue

#
#	keyword: ignore_group
#
		if keyword == 'ignore_group':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_group' requires at least 1 argument: the group to ignore" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['ignore_groups'].extend(arr[1:])
			continue

#
#	keyword: on_update
#
		if keyword == 'on_update':
			if len(arr) < 3:
				stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('on_update'):
				cfg['on_update'] = {}

			file = arr[1]
			cmd = string.join(arr[2:])

			if cfg['on_update'].has_key(file):
				stderr("%s:%d: redefinition of on_update %s" % (filename, lineno, file))
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
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[2])
			else:
				full_cmd = arr[2]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['on_update'][file] = cmd
			continue

#
#	keyword: always_run
#
		if keyword == 'always_run':
			if len(arr) < 2:
				stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('always_run'):
				cfg['always_run'] = []

			cmd = string.join(arr[1:])

			if cmd in cfg['always_run']:
				stderr("%s:%d: same command defined again: %s" % (filename, lineno, cmd))
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
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[1])
			else:
				full_cmd = arr[1]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['always_run'].append(cmd)
			continue

#
#	keyword: diff_cmd
#
		if keyword == 'diff_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'diff_cmd' requires an argument: the full path to the 'diff' command" % (filename, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('diff_cmd'):
				stderr("%s:%d: redefinition of diff_cmd" % (filename, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, cmd))
				errors = errors + 1
				continue

			cfg['diff_cmd'] = string.join(arr[1:])
			continue

		stderr("%s:%d: unknown keyword '%s'" % (filename, lineno, keyword))
		errors = errors + 1

	f.close()

	if not cfg.has_key('masterdir'):
		cfg['masterdir'] = '.'

#
#	get my hostname
#
	hostname = socket.gethostname()
	arr = string.split(hostname, '.')

	if arr[0] in cfg['ignore_groups']:
		stderr('%s: host %s is disabled in the config file' % (filename, arr[0]))
		errors = errors + 1
	else:
		if cfg['host'].has_key(hostname):
			cfg['hostname'] = hostname

			if len(arr) > 0 and arr[0] != hostname and cfg['host'].has_key(arr[0]):
				stderr("%s: conflict; host %s and %s are both defined" % (filename, hostname, arr[0]))
				errors = errors + 1
		else:
			if len(arr) > 0 and cfg['host'].has_key(arr[0]):
				cfg['hostname'] = arr[0]
				hostname = arr[0]
			else:
				stderr('%s: no entry for host %s defined' % (filename, hostname))
				errors = errors + 1

	if errors > 0:
		sys.exit(-1)

# implicitly add 'hostname' as first group
	if not hostname in cfg['host'][hostname]:
		cfg['host'][hostname].insert(0, hostname)

	for host in cfg['host'].keys():
		if not host in cfg['host'][host]:
			cfg['host'][host].insert(0, host)

# remove ignored groups from all hosts
		changed = 0
		groups = cfg['host'][host]
		for ignore in cfg['ignore_groups']:
			if ignore in groups:
				groups.remove(ignore)
				changed = 1

		if changed:
			cfg['host'][host] = groups

	return cfg


def get_all_nodes(cfg):
	return cfg['host'].keys()


def list_all_nodes(cfg):
	nodes = get_all_nodes(cfg)
	nodes.sort()

	for host in nodes:
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
		if not group in nodes:
			arr.append(group)

	return arr


def list_all_groups(cfg):
	groups = get_all_groups(cfg)

	groups.sort()

	for group in groups:
		if group in cfg['ignore_groups']:
			print '%s (ignored group)' % group
		else:
			print group


def get_nodes(cfg, nodenames):
	arr = []

	for nodename in nodenames:
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

	for group in groups:
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
		print node


def get_interfaces(cfg):
	nodes = cfg['host'].keys()

	arr = []

	for node in nodes:
		if cfg.has_key('interfaces') and cfg['interfaces'].has_key(node):
			arr.append(cfg['interfaces'][node])
		else:
			arr.append(node)

	return arr


def list_interfaces(cfg):
	arr = get_interfaces(cfg)
	arr.sort()

	for interface in arr:
		print interface


def get_group_interfaces(cfg, nodegroups):
	all_groups = make_all_groups(cfg)

	for nodegroup in nodegroups:
		if not nodegroup in all_groups:
			stderr("no such nodegroup '%s' defined" % nodegroup)
			sys.exit(1)

	nodes = get_nodegroups(cfg, nodegroups)

	arr = []

	for node in nodes:
		if cfg.has_key('interfaces') and cfg['interfaces'].has_key(node):
			if not cfg['interfaces'][node] in arr:
				arr.append(cfg['interfaces'][node])
		else:
			if not node in arr:
				arr.append(node)

	return arr


def list_group_interfaces(cfg, nodegroup):
	arr = get_group_interfaces(cfg, nodegroup)
	arr.sort()

	for interface in arr:
		print interface


def set_action(a, opt):
	global ACTION, ACTION_OPTION

	if ACTION > 0:
		stderr('the options %s and %s can not be combined' % (ACTION_OPTION, opt))
		sys.exit(1)

	ACTION = a
	ACTION_OPTION = opt


def usage():
	print 'usage: %s [options] [<argument> [..]]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                           Display this information'
	print '  -c, --conf=dir/file                  Use this config file (default: %s)' % DEFAULT_CONF
	print '  -l, --list-nodes                     List all configured nodes'
	print '  -g, --groups                         List all known groups'
	print '  -n, --node <node name> [..]          List all groups this node is in'
	print '  -N, --node-group <group name> [..]   List all nodes in this group'
	print '  -i, --interfaces                     List all nodes by interface'
	print '  -I, --group-interfaces <group> [..]  List all nodes from group by interface'


def get_options():
	global CONF_FILE, ARG_NODENAMES, ARG_NODEGROUPS

	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:lgn:N:iI:", ['help', 'conf=', 'list-nodes', 'groups', 'node=', 'node-group=', 'interfaces', 'group-interfaces'])
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

			if opt in ('-g', '--groups'):
				set_action(ACTION_LIST_GROUPS, '--groups')
				continue

			if opt in ('-n', '--node'):
				set_action(ACTION_NODES, '--node')
				ARG_NODENAMES = [ arg ]
				continue

			if opt in ('-N', '--node-group'):
				set_action(ACTION_NODEGROUPS, '--node-group')
				ARG_NODEGROUPS = [ arg ]
				continue

			if opt in ('-i', '--interfaces'):
				set_action(ACTION_INTERFACES, '--interfaces')
				continue

			if opt in ('-I', '--group-interfaces'):
				set_action(ACTION_GROUP_INTERFACES, '--group-interfaces')
				ARG_NODEGROUPS = [ arg ]
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

	if args != None and len(args) > 0:
		if ARG_NODENAMES != None:
			ARG_NODENAMES.extend(args)

		elif ARG_NODEGROUPS != None:
			ARG_NODEGROUPS.extend(args)

		else:
			stderr('error: excessive arguments on command-line')
			sys.exit(1)


if __name__ == '__main__':
	get_options()

	cfg = read_config(CONF_FILE)

	if ACTION == ACTION_LIST_NODES:
		list_all_nodes(cfg)

	elif ACTION == ACTION_LIST_GROUPS:
		list_all_groups(cfg)

	elif ACTION == ACTION_NODES:
		if not ARG_NODENAMES:
			stderr("option '--node' requires an argument; the node name")
			sys.exit(1)

		list_nodes(cfg, ARG_NODENAMES)

	elif ACTION == ACTION_NODEGROUPS:
		if not ARG_NODEGROUPS:
			stderr("option '--node-group' requires an argument; the node group name")
			sys.exit(1)

		list_nodegroups(cfg, ARG_NODEGROUPS)

	elif ACTION == ACTION_INTERFACES:
		list_interfaces(cfg)

	elif ACTION == ACTION_GROUP_INTERFACES:
		list_group_interfaces(cfg, ARG_NODEGROUPS)


# EOB
