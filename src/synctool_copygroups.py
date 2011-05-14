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

# the group number of group 'all'
GROUP_ALL = 0


class MemDirEntry:
	'''in-memory direntry, which can be a file or directory, and have a group
	extension. The group is denoted by a number rather than groupname.
	The group number is the index to MY_GROUPS[]'''
	# so, if the group number is smaller, than the group is more important
	# group number < 0 denotes irrelevant/invalid group
	
	def __init__(self, src_name, dest_name, num, memdir = None):
		self.src_name = src_name
		self.dest_name = dest_name
		self.groupnum = num
		self.subdir = memdir		# pointer to MemDir if it is a directory
		
		# when a file MemDirEntry gets overridden, it is removed, BUT
		# it is not OK to remove subdir entries ... so flag those
		self.overridden = False
	
	def __repr__(self):
		return '<MemDirEntry>: [%s, %d]' % (self.dname, self.groupnum)


class MemDir:
	'''class for having an in-memory representation of a collapsed view
	of multiple copygroups/ filesystem trees'''

	def __init__(self, parentnode = None):
		self.parent = parentnode	# pointer to parent dir
		self.ref_entry = None		# reference back to my MemDirEntry
		self.entries = []			# array of MemDirEntrys
	
	def __repr__(self):
		return '<MemDir>: ' + self.name
	
	def walk(self, callback, arg = None):
		'''walk the tree, calling the callback function on each entry'''
		'''The callback takes three arguments: the pathname, the copygroup, and arg
		So, 'arg' can be some var you like to pass along'''
		
		for entry in self.entries:
			callback(self, entry, arg)
			
			if entry.subdir != None:
				entry.subdir.walk(callback, arg)
	
	def sourceindex(self, name):
		'''see if source name is present in this directory
		If so, return the index'''
		
		n = 0
		for direntry in self.entries:
			if direntry.src_name == name:
				return n
			
			n = n + 1
		
		return -1
	
	def destindex(self, name):
		'''see if destination name is present in this directory
		If so, return the index'''
		
		n = 0
		for direntry in self.entries:
			if direntry.dest_name == name:
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
			
			pathname = os.path.join(overlay_dir, entry)
			
			present = self.sourceindex(entry)
			if present >= 0:
				print 'warning: %s is present in multiple overlay trees' % pathname
			
			if synctool.path_isdir(pathname):
				if present >= 0:
					if self.entries[present].subdir == None:
						print 'error: %s is a directory, but it is a file in another overlay tree' % pathname
						continue
					
					self.entries[present].subdir.overlay(pathname, groupnum)	# recurse
				else:
					# it's a new subdir entry
					memdir = MemDir(self)
					memdir.ref_entry = MemDirEntry(entry, name, groupnum, memdir)
					self.entries.append(memdir.ref_entry)
					memdir.overlay(pathname, groupnum)		# recurse into directory
			else:
				# it's a file
				if present >= 0:
					if self.entries[present].subdir == None:
						print 'error: %s is a file, but it is a directory in another overlay tree' % pathname
						continue
					
				else:
					present = self.destindex(entry)
					if present >= 0:
						direntry = self.entries[present]
						if direntry.subdir != None:
							print 'error: %s is a file, but it is a directory for a different group' % pathname
							continue
						
						if groupnum < direntry.groupnum:
							# this group is more important, take over
							direntry.groupnum = groupnum
							direntry.src_name = entry
					else:
						self.entries.append(MemDirEntry(entry, name, groupnum))
	
	
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
	
	def src_path(self, name):
		'''compose full source overlay-path for this node'''
		
		path = name
		
		node = self
		while node != None and node.ref_entry != None:
			direntry = node.ref_entry
			path = direntry.src_name + '/' + path
			node = node.parent
		
		return path
	
	def dest_path(self, name):
		'''compose full destination path for this node'''
		
		path = name
		
		node = self
		while node != None and node.ref_entry != None:
			direntry = node.ref_entry
			path = direntry.dest_name + '/' + path
			node = node.parent
		
		return path


def split_extension(entryname):
	'''split a simple filename (without leading path) in a tuple: (name, group number)
	The group number is the index to MY_GROUPS[] or negative
	if it is not a relevant group'''
	
	arr = string.split(entryname, '.')
	if len(arr) <= 1:
		return (entryname, GROUP_ALL+1)
	
	ext = arr.pop()
	if ext == 'post':
		# TODO register .post script
		return (None, -1)
	
	if ext[0] != '_':
		return (entryname, GROUP_ALL+1)
	
	ext = ext[1:]
	if not ext:
		return (entryname, GROUP_ALL+1)
	
	try:
		groupnum = synctool_config.MY_GROUPS.index(ext)
	except ValueError:
		return (None, -1)
	
	if len(arr) > 1 and arr[-1] == 'post':
		# TODO register group-specific .post script
		return (None, -1)
	
	return (string.join(arr, '.'), groupnum)


def memdir_walk_callback(memdir, direntry, arg = None):
	print 'TD', direntry.groupnum, 'src_path', memdir.src_path(direntry.src_name)
	print 'TD', direntry.groupnum, 'dest_path', memdir.dest_path(direntry.dest_name)


def squash_tree(memdir, direntry, dict):
	'''callback function that constructs a dictionary of destination paths
	Each dictionary element holds a tuple: (source path, groupnum, isdir)'''
	
	dest_path = memdir.dest_path(direntry.dest_name)
	
	if dict.has_key(dest_path):
		(src_path, groupnum, isdir) = dict[dest_path]
		if direntry.groupnum > groupnum:
			return		# do not override
	
	isdir = (direntry.subdir != None)
	
	dict[dest_path] = (memdir.src_path(direntry.src_name), direntry.groupnum, isdir)


if __name__ == '__main__':
	## test program ##
	
	synctool_config.MY_GROUPS = ['node1', 'group1', 'group2', 'all']
	GROUP_ALL = synctool_config.MY_GROUPS.index('all')
	
	root = MemDir()
#	root.overlay('/Users/walter/src')
#	pythondir = root.getnode('python')
#	pythondir.overlay('/Users/walter/src/python')

	root.overlay('/Users/walter/src/python/synctool-test/overlay')
	
#	root.walk(memdir_walk_callback)
	
	squashed_tree = {}
	root.walk(squash_tree, squashed_tree)
	
	for dest_path in squashed_tree.keys():
		(source_path, groupnum, isdir) = squashed_tree[dest_path]
		
		if isdir:
			print 'src  D', source_path
			print 'dest D', dest_path
		else:
			print 'src   ', source_path
			print 'dest  ', dest_path

# EOB
