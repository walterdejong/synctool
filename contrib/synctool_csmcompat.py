#! /usr/bin/env python
#
#	synctool-csmcompat	WJ109
#

import synctool_config

import os
import sys
import string
import getopt

CMD_LSNODE='/opt/bin/lsnode'
CMD_NODEGRP='/opt/bin/nodegrp'


def read_csm_config():
	csm = {}
	csm['host'] = {}
	csm['emptygroups'] = []

# get all nodes
	f = os.popen(CMD_LSNODE, 'r')
	lines = f.readlines()
	f.close()

	lines = map(string.strip, lines)
	lines = map(strip_domain, lines)

	for node in lines:
		csm['host'][node] = []

# get all groups
	f = os.popen('%s -L' % CMD_NODEGRP, 'r')
	lines = f.readlines()
	f.close()

	lines = map(string.strip, lines)
	lines = filter(filter_validated, lines)

	for line in lines:
		arr = string.split(line, ':')

		group = arr[0]

		arr = string.split(string.strip(arr[1]), ',')

		arr.remove('static')
		arr.remove('validated')

		try:
			arr.remove('')
		except ValueError:
			pass

		if len(arr) == 0:
#			print 'CSM defines empty group: %s' % group
			csm['emptygroups'].append(group)
		else:
			for host in arr:
				node = strip_domain(host)

				if not csm['host'].has_key(node):
					if node == '+EmptyGroup':			# ignore +EmptyGroup host
						continue

					print 'CSM group %s lists unknown node %s' % (group, node)
					continue

				csm['host'][node].append(group)

	return csm


def strip_domain(hostname):
	arr = string.split(hostname, '.')
	return arr[0]


def filter_validated(line):
	if string.find(line, 'static,validated') >= 0:
		return 1

	return 0


def check_csmcompat(csm):
	warn = 0

# first check nodes
	nodes = synctool_config.get_all_nodes()
	ifaces = {}

	for node in nodes:
		host = synctool_config.get_node_interface(node)
		ifaces[host] = node

		if not csm['host'].has_key(host) and not node in synctool_config.IGNORE_GROUPS:
			print 'synctool node %s is not defined in CSM' % host
			warn = warn + 1

	for host in csm['host'].keys():
		if not ifaces.has_key(host):
			print 'CSM host %s is not defined in synctool' % host
			warn = warn + 1

# check groups
	nodes = synctool_config.get_all_nodes()

	for node in nodes:
		host = synctool_config.get_node_interface(node)

		synctool_groups = synctool_config.get_groups(node)
		synctool_groups.sort()

		try:
			csm_groups = csm['host'][host]
		except KeyError:			# this is OK because we checked all nodes earlier
			continue

		csm_groups.sort()

		if synctool_groups == csm_groups:
			continue

		for group in synctool_groups:
			if group == node or group == host:		# filter default synctool groups
				continue

			if not group in csm_groups:
 				print 'CSM host %s is not a member of group %s' % (host, group)
				warn = warn + 1

		for group in csm_groups:
			if not group in synctool_groups:
				print 'synctool node %s is not a member of group %s' % (node, group)
				warn = warn + 1

	for group in csm['emptygroups']:
		if not group in synctool_config.IGNORE_GROUPS:
			print 'CSM defines empty group %s' % group
			warn = warn + 1

	if not warn:
		print 'synctool and CSM configs are in sync'


def usage():
	print 'usage: %s [options]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file (default: %s)' % synctool_config.DEFAULT_CONF
	print
	print '%s checks consistency between the CSM and synctool configs' % os.path.basename(sys.argv[0])


def get_options():
	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) <= 1:
		return

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:", ['help', 'conf='])
	except getopt.error, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)

	except getopt.GetoptError, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)

	except:
		usage()
		sys.exit(1)

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_config.CONF_FILE=arg
			continue


if __name__ == '__main__':
	get_options()

	synctool_config.read_config()
	csm = read_csm_config()

	check_csmcompat(csm)


# EOB
