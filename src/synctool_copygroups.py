#! /usr/bin/env python
#
#	synctool_copygroups.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_config
import synctool_lib
import synctool

from synctool_lib import verbose,stdout,stderr

import os
import sys
import string


class MemDirEntry:
	'''in-memory direntry, which can be a file or directory, and have a group
	extension. The group is denoted by a number rather than groupname.
	The group number is the index to MY_GROUPS[]'''
	# so, if the group number is smaller, than the group is more important
	# group number < 0 denotes irrelevant/invalid group
	
	def __init__(self, name, num, memdir = None):
		self.dname = name
		self.groupnum = num
		self.subdir = memdir		# pointer to MemDir if it is a directory

	def __repr__(self):
		return '<MemDirEntry>: [%s, %d]' % (self.dname, self.groupnum)


class MemDir:
	'''class for having an in-memory representation of a collapsed view
	of multiple copygroups/ filesystem trees'''

	def __init__(self, parentnode = None):
		self.parent = parentnode
		self.entries = []			# array of MemDirEntrys
	
	def __repr__(self):
		return '<MemDir>: ' + self.name
	
	def walk(self, path, callback):
		'''walk the tree, calling the callback function on each entry'''
		'''The callback takes two arguments: the pathname, the copygroup'''
		
		for entry in self.entries:
			pathname = path + '/' + entry.dname
			callback(pathname, entry)
			
			if entry.subdir != None:
				entry.subdir.walk(pathname, callback)
	
	def entryindex(self, name):
		'''see if name is present in this directory
		If so, return the index'''
		
		n = 0
		for direntry in self.entries:
			if direntry.dname == name:
				return n
			
			n = n + 1
		
		return -1
	
	def overlay(self, overlay_dir, highest_groupnum = sys.maxint):
		'''lay contents of on-disk overlay_dir over the MemDir'''
		
		for entry in os.listdir(overlay_dir):
			(name, groupnum) = split_extension(entry)
			if groupnum < 0:				# not a relevant group
				continue
			
			# inherit lower group level from parent directory
			if groupnum > highest_groupnum:
				groupnum = highest_groupnum
			
			# see if we already had this name in the tree
			n = self.entryindex(name)
			if n >= 0:
				direntry = self.entries[n]
				# yes, see if this group is more important
				if groupnum < direntry.groupnum:
					direntry.groupnum = groupnum
				
				if direntry.subdir != None:
					# recurse into subdir
					direntry.subdir.overlay(os.path.join(overlay_dir, entry), groupnum)
				#endif
			else:
				# it's a new entry in the MemDir tree
				# see if it's a directory or a file entry
				pathname = os.path.join(overlay_dir, entry)
				if synctool.path_isdir(pathname):
					memdir = MemDir(self)
					self.entries.append(MemDirEntry(name, groupnum, memdir))
					memdir.overlay(pathname, groupnum)	# recurse into directory
				else:
					self.entries.append(MemDirEntry(name, groupnum))
	
	def getnode(self, path):
		'''return the MemDir node pointed to by path
		raises RuntimeError if path is not a dir under this MemDir node'''
		
		node = self
		for elem in string.split(path, '/'):
			found = False
			for direntry in node.entries:
				if elem == direntry.dname:
					node = direntry.subdir
					if node == None:
						raise RuntimeError, 'MemDir::getnode(%s): element %s is not a directory' % (path, elem)
					
					found = True
					break
			
			if not found:
				raise RuntimeError, 'MemDir::getnode(%s): path %s not found' % (path, elem)
		
		return node


def split_extension(entryname):
	'''split a simple filename (without leading path) in a tuple: (name, group number)
	The group number is the index to MY_GROUPS[] or negative
	if it is not a relevant group'''
	
	group_all = synctool_config.MY_GROUPS.index('all')
	
	arr = string.split(entryname, '.')
	if len(arr) <= 1:
		return (entryname, group_all)
	
	ext = arr.pop()
	if ext == 'post':
		# TODO register .post script
		return (None, -1)
	
	if ext[0] != '_':
		return (entryname, group_all)
	
	ext = ext[1:]
	if not ext:
		return (entryname, group_all)
	
	try:
		groupnum = synctool_config.MY_GROUPS.index(ext)
	except ValueError:
		return (None, -1)
	
	if len(arr) > 1 and arr[-1] == 'post':
		# TODO register group-specific .post script
		return (None, -1)
	
	return (string.join(arr, '.'), groupnum)


def memdir_walk_callback(path, direntry):
	if direntry.subdir != None:
		print 'D', direntry.groupnum, path
	else:
		print ' ', direntry.groupnum, path



if __name__ == '__main__':
	## test program ##
	
	synctool_config.MY_GROUPS = ['node1', 'group1', 'group2', 'all']
	
	root = MemDir()
#	root.overlay('/Users/walter/src')
#	pythondir = root.getnode('python')
#	pythondir.overlay('/Users/walter/src/python')

	root.overlay('/Users/walter/src/python/synctool-test/overlay')
	
	root.walk('', memdir_walk_callback)


# EOB
