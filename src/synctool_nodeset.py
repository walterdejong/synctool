#
#	synctool_nodeset.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_lib

from synctool_lib import verbose,stderr

import synctool_config

import string

#
# The nodeset helps making a set of nodes from command-line arguments
# It is used by synctool-master, dsh, dcp, dsh-ping
#
# usage: first make an instance of NodeSet
#        then add nodes, groups, excluded nodes/groups
#        call synctool_config.read_config()
#        call nodeset.interfaces(), which will return a list of interfaces
#        use the interface list to contact the nodes
#        use nodeset.get_nodename_from_interface() to get a nodename
#

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
		nodes = string.split(nodelist)
		for node in nodes:
			if not node in self.exclude_nodes:
				self.exclude_nodes.append(node)
	
	def exclude_group(self, grouplist):
		groups = string.split(grouplist)
		for group in groups:
			if not group in self.exclude_groups:
				self.exclude_groups.append(group)
	
	def interfaces(self):
		'''return list of interfaces of relevant nodes'''
		
		explicit_includes = self.nodelist[:]
		
		# by default, work on all nodes
		if not self.nodelist and not self.grouplist:
			self.nodelist = synctool_config.get_all_nodes()
		
		# check if the nodes exist at all; the user could have given bogus names
		all_nodes = synctool_config.get_all_nodes()
		for node in self.nodelist:
			if not node in all_nodes:
				stderr("no such node '%s'" % node)
				return None
		
		if self.grouplist:
			# check if the groups exist at all
			all_groups = synctool_config.make_all_groups()
			for group in self.grouplist:
				if not group in all_groups:
					stderr("no such group '%s'" % group)
					return None
			
			self.nodelist.extend(synctool_config.get_nodes_in_groups(self.grouplist))
		
		if self.exclude_groups:
			self.exclude_nodes.extend(synctool_config.get_nodes_in_groups(self.exclude_groups))
		
		for node in self.exclude_nodes:
			# remove excluded nodes, if not explicitly included
			if node in self.nodelist and not node in explicit_includes:
				self.nodelist.remove(node)
		
		if len(self.nodelist) <= 0:
			return []
		
		ifaces = []
		ignored_nodes = ''
		
		for node in self.nodelist:
			if node in synctool_param.IGNORE_GROUPS and not node in explicit_includes:
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
			
			iface = synctool_config.get_node_interface(node)
			self.namemap[iface] = node
			
			if not iface in ifaces:		# make sure we do not have duplicates
				ifaces.append(iface)
		
		# print message about ignored nodes
		if ignored_nodes and not synctool_lib.QUIET and not synctool_lib.UNIX_CMD:
			if synctool_param.TERSE:
				synctool_lib.terse(synctool_lib.TERSE_WARNING, 'ignored nodes')
			else:
				ignored_nodes = 'warning: ignored nodes: ' + ignored_nodes
				if len(ignored_nodes < 80):
					print ignored_nodes
				else:
					print 'warning: some nodes are ignored'
		
		return ifaces
	
	def get_nodename_from_interface(self, iface):
		'''map the interface back to a nodename'''
		
		if self.namemap.has_key(iface):
			return self.namemap[iface]
		
		return iface

# EOB
