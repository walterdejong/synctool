#
#	synctool.config.py	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_lib

import os
import sys
import string
import socket
import getopt
import errno

import synctool.configparser
from synctool.configparser import stderr


def read_config():
	'''read the config file and set a bunch of globals'''

	if not os.path.isfile(synctool_param.CONF_FILE):
		stderr("no such config file '%s'" % synctool_param.CONF_FILE)
		sys.exit(-1)

	errors = synctool.configparser.read_config_file(synctool_param.CONF_FILE)

	# if missing, set default directories
	if not synctool_param.MASTERDIR:
		synctool_param.MASTERDIR = '/var/lib/synctool'

		if not os.path.isdir(synctool_param.MASTERDIR):
			stderr('error: no such directory: %s' % d)
			errors += 1

	# overlay/ and delete/ must be under $masterdir
	d = os.path.join(synctool_param.MASTERDIR, 'overlay')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	# set it, even if it does not exists
	synctool_param.OVERLAY_DIR = d

	# treat a missing 'overlay/all/' dir as an error
	d = os.path.join(synctool_param.OVERLAY_DIR, 'all')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	d = os.path.join(synctool_param.MASTERDIR, 'delete')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	synctool_param.DELETE_DIR = d

	d = os.path.join(synctool_param.DELETE_DIR, 'all')
	if not os.path.isdir(d):
		stderr('error: no such directory: %s' % d)
		errors += 1

	if not synctool_param.TEMP_DIR:
		synctool_param.TEMP_DIR = '/tmp/synctool'
		# do not make temp dir here; it is only used on the master node

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

	# initialize ALL_GROUPS
	synctool_param.ALL_GROUPS = make_all_groups()

	# make the default nodeset
	# note that it may still contain ignored nodes
	# the NodeSet will print warnings about ignored nodes
	errors += make_default_nodeset()

	# remove ignored groups from node definitions
	remove_ignored_groups()

	if errors > 0:
		sys.exit(-1)


def make_default_nodeset():
	errors = 0

	# check that the listed nodes / groups exist at all
	groups = []
	for g in synctool_param.DEFAULT_NODESET:
		if g == 'none':
			groups = []
			continue

		if not g in synctool_param.ALL_GROUPS:
			stderr("config error: unknown node or group '%s' "
				"in default_nodeset" % g)
			errors += 1
			continue

		if not g in groups:
			groups.append(g)

	if not errors:
		if not groups:
			# if there was 'none', the nodeset will be empty
			synctool_param.DEFAULT_NODESET = []
		else:
			synctool_param.DEFAULT_NODESET = get_nodes_in_groups(groups)

	return errors


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


def init_mynodename():
	'''determine the nodename of the current host
	and initialize MY_GROUPS'''

	# In practice, the nodename is determined by the master in synctool.conf
	# The master then tells the client what its nodename is
	# In two special cases, we still need to detect the nodename:
	# 1. user runs synctool.py in stand-alone mode on a node
	# 2. master node itself is being managed by synctool
	#
	# In older versions, the hostname was implicitly treated as a group
	# This is no longer the case

	# get my hostname
	synctool_param.HOSTNAME = hostname = socket.getfqdn()

	arr = string.split(hostname, '.')
	short_hostname = arr[0]

	all_nodes = get_all_nodes()

	nodename = synctool_param.NODENAME
	if nodename != None:
		# nodename was already set
		# the master set it because it already knows the node's nodename
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
		# try to find a node that has the (short) hostname
		# listed as interface or as a group
		for node in all_nodes:
			addr = get_node_ipaddress(node)
			if addr == short_hostname or addr == hostname:
				nodename = node
				break

			groups = get_groups(node)
			if short_hostname in groups or hostname in groups:
				nodename = node
				break

	# At this point, nodename can still be None
	# It only really matters for synctool.py, which checks this condition

	synctool_param.NODENAME = nodename
	synctool_param.MY_GROUPS = get_my_groups()


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


def get_node_ipaddress(node):
	if synctool_param.IPADDRESSES.has_key(node):
		return synctool_param.IPADDRESSES[node]

	return node


def get_node_hostname(node):
	if synctool_param.HOSTNAMES_BY_NODE.has_key(node):
		return synctool_param.HOSTNAMES_BY_NODE[node]

	return node


def make_all_groups():
	'''make a list of all possible groups
	This is a set of all group names plus all node names'''

	arr = synctool_param.GROUP_DEFS.keys()
	arr.extend(synctool_param.NODES.keys())

# older versions of python do not support sets BUT that doesn't matter ...
# all groups + nodes should have no duplicates anyway
#	return list(set(arr))
	return arr


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


def get_nodes_in_groups(groups):
	'''returns the nodes that are in [groups]'''

	arr = []

	nodes = synctool_param.NODES.keys()

	for g in groups:
		for node in nodes:
			if g in synctool_param.NODES[node] and not node in arr:
				arr.append(node)

	return arr


# EOB
