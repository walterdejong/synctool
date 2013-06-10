#
#	synctool.nodeset.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_lib

from synctool_lib import verbose,stderr

import synctool_config
import synctool_param

import string

# The nodeset helps making a set of nodes from command-line arguments
# It is used by synctool-master, dsh, dcp, dsh-ping
#
# usage: first make an instance of NodeSet
#        then add nodes, groups, excluded nodes/groups
#        call synctool_config.read_config()
#        call nodeset.addresses(), which will return a list of addresses
#        use the address list to contact the nodes
#        use nodeset.get_nodename_from_address() to get a nodename

class NodeSet:
	'''class representing a set of nodes'''

	def __init__(self):
		self.nodelist = []
		self.grouplist = []
		self.exclude_nodes = []
		self.exclude_groups = []
		self.namemap = {}

	def add_node(self, nodelist):
		nodes = string.split(nodelist, ',')
		for node in nodes:
			if not node in self.nodelist:
				self.nodelist.append(node)

	def add_group(self, grouplist):
		groups = string.split(grouplist, ',')
		for group in groups:
			if not group in self.grouplist:
				self.grouplist.append(group)

	def exclude_node(self, nodelist):
		nodes = string.split(nodelist, ',')
		for node in nodes:
			if not node in self.exclude_nodes:
				self.exclude_nodes.append(node)

	def exclude_group(self, grouplist):
		groups = string.split(grouplist, ',')
		for group in groups:
			if not group in self.exclude_groups:
				self.exclude_groups.append(group)

	def addresses(self):
		'''return list of addresses of relevant nodes'''

		explicit_includes = self.nodelist[:]

		# by default, work on default_nodeset
		if not self.nodelist and not self.grouplist:
			if not synctool_param.DEFAULT_NODESET:
				return []

			self.nodelist = synctool_param.DEFAULT_NODESET
		else:
			# check if the nodes exist at all
			# the user may have given bogus names
			all_nodes = synctool_config.get_all_nodes()
			for node in self.nodelist:
				if not node in all_nodes:
					stderr("no such node '%s'" % node)
					return None

			if self.grouplist:
				# check if the groups exist at all
				for group in self.grouplist:
					if not group in synctool_param.ALL_GROUPS:
						stderr("no such group '%s'" % group)
						return None

				self.nodelist.extend(synctool_config.get_nodes_in_groups(
										self.grouplist))

		if self.exclude_groups:
			self.exclude_nodes.extend(synctool_config.get_nodes_in_groups(
										self.exclude_groups))

		for node in self.exclude_nodes:
			# remove excluded nodes, if not explicitly included
			if node in self.nodelist and not node in explicit_includes:
				self.nodelist.remove(node)

		if len(self.nodelist) <= 0:
			return []

		addrs = []
		ignored_nodes = ''

		for node in self.nodelist:
			if (node in synctool_param.IGNORE_GROUPS and
				not node in explicit_includes):
				verbose('node %s is ignored' % node)

				if not ignored_nodes:
					ignored_nodes = node
				else:
					ignored_nodes = ignored_nodes + ',' + node
				continue

			groups = synctool_config.get_groups(node)
			do_continue = False

			for group in groups:
				if group in synctool_param.IGNORE_GROUPS:
					verbose('group %s is ignored' % group)

					if not ignored_nodes:
						ignored_nodes = node
					else:
						ignored_nodes = ignored_nodes + ',' + node

					do_continue = True
					break

			if do_continue:
				continue

			addr = synctool_config.get_node_ipaddress(node)
			self.namemap[addr] = node

			if not addr in addrs:	# make sure we do not have duplicates
				addrs.append(addr)

		# print message about ignored nodes
		if (ignored_nodes and not synctool_lib.QUIET and
			not synctool_lib.UNIX_CMD):
			if synctool_param.TERSE:
				synctool_lib.terse(synctool_lib.TERSE_WARNING,
									'ignored nodes')
			else:
				ignored_nodes = 'warning: ignored nodes: ' + ignored_nodes
				if len(ignored_nodes) < 80:
					print ignored_nodes
				else:
					print 'warning: some nodes are ignored'

		return addrs

	def get_nodename_from_address(self, addr):
		'''map the address back to a nodename'''

		if self.namemap.has_key(addr):
			return self.namemap[addr]

		return addr

# EOB
