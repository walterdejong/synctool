#! /usr/bin/env python -tt
#
#	synctool-config	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_configparser
import synctool_param
import synctool_lib

from synctool_configparser import stderr

import os
import sys
import string
import socket
import getopt
import errno

ACTION = 0
ACTION_OPTION = None
ARG_NODENAMES = None
ARG_GROUPS = None
ARG_CMDS = None

# these are enums for the "list" command-line options
ACTION_LIST_NODES = 1
ACTION_LIST_GROUPS = 2
ACTION_NODES = 3
ACTION_GROUPS = 4
ACTION_MASTERDIR = 5
ACTION_CMDS = 6
ACTION_NUMPROC = 7
ACTION_VERSION = 8
ACTION_PREFIX = 9
ACTION_LOGFILE = 10
ACTION_NODENAME = 11
ACTION_LIST_DIRS = 12
ACTION_PKGMGR = 13

# optional: do not list hosts/groups that are ignored
OPT_FILTER_IGNORED = False
# optional: list interface names for the selected nodes
OPT_INTERFACE = False
# optional: list hostnames for the selected nodes
OPT_HOSTNAME = False


def read_config():
	'''read the config file and set a bunch of globals'''

	global CONFIGPARSER_MODULE

	if not os.path.isfile(synctool_param.CONF_FILE):
		stderr("no such config file '%s'" % synctool_param.CONF_FILE)
		sys.exit(-1)

	errors = synctool_configparser.read_config_file(synctool_param.CONF_FILE)

	# if missing, set default directories
	if synctool_param.MASTERDIR == None:
		synctool_param.MASTERDIR = '/var/lib/synctool'

		if not os.path.isdir(synctool_param.MASTERDIR):
			stderr('error: no such directory: %s' % d)
			errors += 1

	if not synctool_param.OVERLAY_DIR:
		d = os.path.join(synctool_param.MASTERDIR, 'overlay')
		if not os.path.isdir(d):
			stderr('error: no such directory: %s' % d)
			errors += 1
		else:
			synctool_param.OVERLAY_DIR = d

	# treat a missing 'overlay/all/' dir as an error
	d = os.path.join(synctool_param.OVERLAY_DIR, 'all')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	if not synctool_param.DELETE_DIR:
		d = os.path.join(synctool_param.MASTERDIR, 'delete')
		if not os.path.isdir(d):
			stderr('error: no such directory: %s' % d)
			errors += 1
		else:
			synctool_param.DELETE_DIR = d

	d = os.path.join(synctool_param.DELETE_DIR, 'all')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	if not synctool_param.TASKS_DIR:
		d = os.path.join(synctool_param.MASTERDIR, 'tasks')
		if not os.path.isdir(d):
			stderr('error: no such directory: %s' % d)
			errors += 1
		else:
			synctool_param.TASKS_DIR = d

	d = os.path.join(synctool_param.TASKS_DIR, 'all')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	if not synctool_param.SCRIPT_DIR:
		d = os.path.join(synctool_param.MASTERDIR, 'scripts')
		if not os.path.isdir(d):
			stderr('error: no such directory: %s' % d)
			errors += 1
		else:
			synctool_param.SCRIPT_DIR = d

	if errors > 0:
		sys.exit(-1)

	if not synctool_param.TEMP_DIR:
		synctool_param.TEMP_DIR = '/tmp/synctool'

	# implicitly add group 'all'
	if not synctool_param.GROUP_DEFS.has_key('all'):
		synctool_param.GROUP_DEFS['all'] = None

	# implicitly add 'nodename' as first group
	for node in get_all_nodes():
		insert_group(node, node)
		synctool_param.NODES[node].append('all')

	# implicitly add group 'none'
	if not synctool_param.GROUP_DEFS.has_key('none'):
		synctool_param.GROUP_DEFS['none'] = None

	if not 'none' in synctool_param.IGNORE_GROUPS:
		synctool_param.IGNORE_GROUPS.append('none')


def check_cmd_config(param_name, cmd):
	'''check whether the command given in the config exists
	Returns (True, full pathed command) when OK,
	and (False, None) on error'''

	if not cmd:
		stderr("%s: error: parameter '%s' is missing" %
			(synctool_param.CONF_FILE, param_name))
		return (False, None)

	arr = string.split(cmd)
	path = synctool_lib.search_path(arr[0])
	if not path:
		stderr("%s: error: %s '%s' not found in PATH" %
			(synctool_param.CONF_FILE, param_name, arr[0]))
		return (False, None)

	# reassemble command with full path
	arr[0] = path
	cmd = string.join(arr)
	return (True, cmd)


def add_myhostname():
	# FIXME do away with hostnames (!)

	'''add the hostname of the current host to the configuration,
	so that it can be used
	also determine the nodename of the current host'''

	# In practice, the nodename is determined by the master in synctool.conf
	# The master then tells the client what its nodename is
	#
	# The nodename detection really only runs for the master node itself;
	# it's not important unless you manage the master with the same synctool
	# (which is discouraged, but it is possible to do so)

	#
	#	get my hostname
	#
	synctool_param.HOSTNAME = hostname = socket.getfqdn()

	arr = string.split(hostname, '.')
	short_hostname = arr[0]

	all_nodes = get_all_nodes()

	nodename = synctool_param.NODENAME

	if nodename != None:
		# nodename was already set
		# the master can set it because it already knows the node's nodename
		pass

	elif synctool_param.HOST_ID != None:
		arr = string.split(synctool_param.HOST_ID, '.')
		nodename = arr[0]

	elif synctool_param.HOSTNAMES.has_key(hostname):
		nodename = synctool_param.HOSTNAMES[hostname]

	elif synctool_param.HOSTNAMES.has_key(short_hostname):
		nodename = synctool_param.HOSTNAMES[short_hostname]

	elif short_hostname in all_nodes:
		nodename = short_hostname

	elif hostname in all_nodes:
		nodename = hostname

	else:
		# try to find a node that has the (short) hostname listed as interface
		# or as a group
		for node in all_nodes:
			iface = get_node_interface(node)
			if iface == short_hostname or iface == hostname:
				nodename = node
				break

			groups = get_groups(node)
			if short_hostname in groups or hostname in groups:
				nodename = node
				break

	synctool_param.NODENAME = nodename

	if nodename != None:
		# implicitly add hostname as first group
		insert_group(nodename, hostname)
		insert_group(nodename, short_hostname)
		insert_group(nodename, nodename)


def remove_ignored_groups():
	'''remove ignored groups from all node definitions'''

	for host in synctool_param.NODES.keys():
		changed = False
		groups = synctool_param.NODES[host]
		for ignore in synctool_param.IGNORE_GROUPS:
			if ignore in groups:
				groups.remove(ignore)
				changed = True

		if changed:
			synctool_param.NODES[host] = groups


def insert_group(node, group):
	'''add group to node definition'''

	if synctool_param.NODES.has_key(node):
		if group in synctool_param.NODES[node]:
			# remove the group and reinsert it to make sure it comes first
			synctool_param.NODES[node].remove(group)

		synctool_param.NODES[node].insert(0, group)
	else:
		synctool_param.NODES[node] = [group]


def get_all_nodes():
	return synctool_param.NODES.keys()


def get_node_interface(node):
	if synctool_param.INTERFACES.has_key(node):
		return synctool_param.INTERFACES[node]

	return node


def get_node_hostname(node):
	if synctool_param.HOSTNAMES_BY_NODE.has_key(node):
		return synctool_param.HOSTNAMES_BY_NODE[node]

	return node


def list_all_nodes():
	nodes = get_all_nodes()
	nodes.sort()

	if synctool_param.IGNORE_GROUPS != None:
		ignore_nodes = get_nodes_in_groups(synctool_param.IGNORE_GROUPS)
	else:
		ignore_nodes = []

	for host in nodes:
		if host in ignore_nodes:
			if OPT_INTERFACE:
				host = get_node_interface(host)

			elif OPT_HOSTNAME:
				host = get_node_hostname(host)

			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % host
		else:
			if OPT_INTERFACE:
				host = get_node_interface(host)

			elif OPT_HOSTNAME:
				host = get_node_hostname(host)

			print host


def make_all_groups():
	'''make a list of all possible groups
	This is a set of all group names plus all node names'''

	arr = synctool_param.GROUP_DEFS.keys()
	arr.extend(synctool_param.NODES.keys())

# older versions of python do not support sets BUT that doesn't matter ...
# all groups + nodes should have no duplicates anyway
#	return list(set(arr))
	return arr


def list_all_groups():
	groups = synctool_param.GROUP_DEFS.keys()
	groups.sort()

	for group in groups:
		if group in synctool_param.IGNORE_GROUPS:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_groups(nodename):
	'''returns the groups for the node'''

	if synctool_param.NODES.has_key(nodename):
		return synctool_param.NODES[nodename]

	return []


def get_my_groups():
	'''returns the groups for this node'''

	if synctool_param.NODES.has_key(synctool_param.NODENAME):
		return synctool_param.NODES[synctool_param.NODENAME]

	return []


def list_nodes(nodenames):
	groups = []

	for nodename in nodenames:
		if not synctool_param.NODES.has_key(nodename):
			stderr("no such node '%s' defined" % nodename)
			sys.exit(1)

		if OPT_INTERFACE:
			print get_node_interface(nodename)

		elif OPT_HOSTNAME:
			print get_node_hostname(nodename)

		else:
			for group in get_groups(nodename):
				if not group in groups:
					groups.append(group)

#	groups.sort()							# group order is important

	for group in groups:
		if group in synctool_param.IGNORE_GROUPS:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_nodes_in_groups(nodegroups):
	'''returns the nodes that are in [groups]'''

	arr = []

	nodes = synctool_param.NODES.keys()

	for nodegroup in nodegroups:
		for node in nodes:
			if nodegroup in synctool_param.NODES[node] and not node in arr:
				arr.append(node)

	return arr


def list_nodegroups(nodegroups):
	all_groups = make_all_groups()

	for nodegroup in nodegroups:
		if not nodegroup in all_groups:
			stderr("no such nodegroup '%s' defined" % nodegroup)
			sys.exit(1)

	arr = get_nodes_in_groups(nodegroups)
	arr.sort()

	for node in arr:
		if node in synctool_param.IGNORE_GROUPS:
			if OPT_INTERFACE:
				node = get_node_interface(node)

			elif OPT_HOSTNAME:
				node = get_node_hostname(node)

			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % node
		else:
			if OPT_INTERFACE:
				node = get_node_interface(node)

			elif OPT_HOSTNAME:
				node = get_node_hostname(node)

			print node


def list_commands(cmds):
	'''display command setting'''

	for cmd in cmds:
		if cmd == 'diff':
			(ok, a) = check_cmd_config('diff_cmd', synctool_param.DIFF_CMD)
			if ok:
				print synctool_param.DIFF_CMD

		if cmd == 'ping':
			(ok, a) = check_cmd_config('ping_cmd', synctool_param.PING_CMD)
			if ok:
				print synctool_param.PING_CMD

		elif cmd == 'ssh':
			(ok, a) = check_cmd_config('ssh_cmd', synctool_param.SSH_CMD)
			if ok:
				print synctool_param.SSH_CMD

		elif cmd == 'scp':
			(ok, a) = check_cmd_config('scp_cmd', synctool_param.SCP_CMD)
			if ok:
				print synctool_param.SCP_CMD

		elif cmd == 'rsync':
			(ok, a) = check_cmd_config('rsync_cmd', synctool_param.RSYNC_CMD)
			if ok:
				print synctool_param.RSYNC_CMD

		elif cmd == 'synctool':
			(ok, a) = check_cmd_config('synctool_cmd',
										synctool_param.SYNCTOOL_CMD)
			if ok:
				print synctool_param.SYNCTOOL_CMD

		elif cmd == 'pkg':
			(ok, a) = check_cmd_config('pkg_cmd', synctool_param.PKG_CMD)
			if ok:
				print synctool_param.PKG_CMD

		else:
			stderr("no such command '%s' available in synctool" % cmd)


def list_dirs():
	'''display directory settings'''

	print 'masterdir', synctool_param.MASTERDIR

	# Note: do not use prettypath() here, for shell scripters
	# They will still have to awk anyway ...

	print 'overlaydir', synctool_param.OVERLAY_DIR
	print 'deletedir', synctool_param.DELETE_DIR
	print 'tasksdir', synctool_param.TASKS_DIR
	print 'scriptdir', synctool_param.SCRIPT_DIR
	print 'tempdir', synctool_param.TEMP_DIR


def set_action(a, opt):
	global ACTION, ACTION_OPTION

	if ACTION > 0:
		stderr('options %s and %s can not be combined' % (ACTION_OPTION, opt))
		sys.exit(1)

	ACTION = a
	ACTION_OPTION = opt


def usage():
	print 'usage: %s [options] [<argument>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help               Display this information'
	print '  -c, --conf=dir/file      Use this config file'
	print ('                           (default: %s)' %
		synctool_param.DEFAULT_CONF)

	print '  -l, --list-nodes         List all configured nodes'
	print '  -L, --list-groups        List all configured groups'
	print '  -n, --node=nodelist      List all groups this node is in'
	print '  -g, --group=grouplist    List all nodes in this group'
	print '  -i, --ipaddress          List selected nodes by IP address'
	print '  -i, --interface          Same thing; old form for --ipaddress'
	print '  -H, --hostname           List selected nodes by hostname'
	print '  -f, --filter-ignored     Do not list ignored nodes and groups'
	print
	print '  -C, --command=command    Display setting for command'
	print '  -P, --package-manager    Display configured package manager'
	print '  -p, --numproc            Display numproc setting'
	print '  -m, --masterdir          Display the masterdir setting'
	print '  -d, --list-dirs          Display directory settings'
	print '      --prefix             Display installation prefix'
	print '      --logfile            Display configured logfile'
	print '      --nodename           Display my nodename'
	print '  -v, --version            Display synctool version'
	print
	print 'A node/group list can be a single value, or a comma-separated list'
	print 'A command is a list of these: diff,ping,ssh,scp,rsync,synctool,pkg'
	print
	print 'synctool-config by Walter de Jong <walter@heiho.net> (c) 2009-2013'


def get_options():
	global CONF_FILE, ARG_NODENAMES, ARG_GROUPS, ARG_CMDS
	global OPT_FILTER_IGNORED, OPT_INTERFACE, OPT_HOSTNAME

	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:lLn:g:iHfC:Ppmdv',
			['help', 'conf=', 'list-nodes', 'list-groups', 'node=', 'group=',
			'interface', 'ipaddress', 'hostname', 'filter-ignored',
			'command', 'package-manager', 'numproc', 'masterdir', 'list-dirs',
			'prefix', 'logfile', 'nodename', 'version'])

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

	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command-line')
		sys.exit(1)

	errors = 0

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE=arg
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

		if opt in ('-i', '--interface', 'ipaddress'):
			OPT_INTERFACE = True
			continue

		if opt in ('-H', '--hostname'):
			OPT_HOSTNAME = True
			continue

		if opt in ('-f', '--filter-ignored'):
			OPT_FILTER_IGNORED = True
			continue

		if opt in ('-C', '--command'):
			set_action(ACTION_CMDS, '--command')
			ARG_CMDS = string.split(arg, ',')
			continue

		if opt in ('-P', '--package-manager'):
			set_action(ACTION_PKGMGR, '--package-manager')
			continue

		if opt in ('-p', '--numproc'):
			set_action(ACTION_NUMPROC, '--numproc')
			continue

		if opt in ('-m', '--masterdir'):
			set_action(ACTION_MASTERDIR, '--masterdir')
			continue

		if opt in ('-d', '--list-dirs'):
			set_action(ACTION_LIST_DIRS, '--list-dirs')
			continue

		if opt == '--prefix':
			set_action(ACTION_PREFIX, '--prefix')
			continue

		if opt == '--logfile':
			set_action(ACTION_LOGFILE, '--logfile')
			continue

		if opt == '--nodename':
			set_action(ACTION_NODENAME, '--nodename')
			continue

		if opt in ('-v', '--version'):
			set_action(ACTION_VERSION, '--version')
			continue

		stderr("unknown command line option '%s'" % opt)
		errors = errors + 1

	if errors:
		usage()
		sys.exit(1)

	if not ACTION:
		usage()
		sys.exit(1)


def main():
	get_options()

	if ACTION == ACTION_VERSION:
		print synctool_param.VERSION
		sys.exit(0)

	if OPT_INTERFACE and OPT_HOSTNAME:
		stderr('options --interface, --ipaddress and --hostname can not '
			'be combined')
		sys.exit(1)

	read_config()

	if ACTION == ACTION_LIST_NODES:
		list_all_nodes()

	elif ACTION == ACTION_LIST_GROUPS:
		list_all_groups()

	elif ACTION == ACTION_NODES:
		if not ARG_NODENAMES:
			stderr("option '--node' requires an argument; the node name")
			sys.exit(1)

		list_nodes(ARG_NODENAMES)

	elif ACTION == ACTION_GROUPS:
		if not ARG_GROUPS:
			stderr("option '--node-group' requires an argument; "
				"the node group name")
			sys.exit(1)

		list_nodegroups(ARG_GROUPS)

	elif ACTION == ACTION_MASTERDIR:
		print synctool_param.MASTERDIR

	elif ACTION == ACTION_CMDS:
		list_commands(ARG_CMDS)

	elif ACTION == ACTION_NUMPROC:
		print synctool_param.NUM_PROC

	elif ACTION == ACTION_PREFIX:
		print os.path.abspath(os.path.dirname(sys.argv[0]))

	elif ACTION == ACTION_LOGFILE:
		print synctool_param.LOGFILE

	elif ACTION == ACTION_NODENAME:
		add_myhostname()

		if synctool_param.NODENAME == None:
			stderr('unable to determine my nodename (%s), please check %s' %
				(synctool_config.HOSTNAME, synctool_param.CONF_FILE))
			sys.exit(1)

		if synctool_param.NODENAME in synctool_param.IGNORE_GROUPS:
			if not synctool_param.OPT_FILTER_IGNORED:
				if OPT_INTERFACE:
					print ('none (%s ignored)' %
						get_node_interface(synctool_param.NODENAME))
				else:
					print 'none (%s ignored)' % synctool_param.NODENAME

			sys.exit(0)

		if OPT_INTERFACE:
			print get_node_interface(synctool_param.NODENAME)
		else:
			print synctool_param.NODENAME

	elif ACTION == ACTION_LIST_DIRS:
		list_dirs()

	elif ACTION == ACTION_PKGMGR:
		print synctool_param.PACKAGE_MANAGER

	else:
		raise RuntimeError, 'bug: unknown ACTION code %d' % ACTION


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
