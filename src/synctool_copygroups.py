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


class MemDir:
	'''class for having an in-memory representation of a collapsed view
	of multiple copygroups/ filesystem trees'''

	def __init__(self, dirname = '', parentnode = None, group = 'all'):
		self.name = dirname
		self.parent = parentnode
		self.files = {}
		self.subdirs = []
		self.copygroup = group
	
	def __repr__(self):
		return '<MemDir>: ' + self.name
	
	def listdir(self, pathname, copygroup):
		'''list contents of on-disk pathname, loading it into MemDir structure'''
		
		for entry in os.listdir(pathname):
			if entry in synctool_config.IGNORE_FILES:
				continue
			
			fullpath = os.path.join(pathname, entry)
			
			if synctool.path_isdir(fullpath):
				if entry[0] == '.' and synctool_config.IGNORE_DOTDIRS:
					continue
				
#				# check for type change
#				if entry in self.files:
#					stderr('warning: %s is a file in copygroup/%s and a directory in copygroup/%s' % (fullpath, self.files[entry], copygroup))
#					del self.files[entry]
				
				found = False
				for d in self.subdirs:
					if d.name == entry:
						print 'TD dir %s exists, setting group %s' % (entry, copygroup)
						d.copygroup = copygroup
						found = True
						break
				
				if not found:
					self.subdirs.append(MemDir(entry, self, copygroup))
				
			else:
				# it is a file
				if entry[0] == '.' and synctool_config.IGNORE_DOTFILES:
					continue
				
				if self.files.has_key(entry):
					print 'TD file %s exists, setting group %s' % (entry, copygroup)
				
#				# check for type change
#				for d in self.subdirs:
#					if d.name == entry:
#						stderr('warning: %s is a directory in copygroup/%s and a file in copygroup/%s' % (fullpath, d.copygroup, copygroup))
#						self.subdirs.remove(d)
#						break
				
				self.files[entry] = copygroup
	
	def loaddir(self, pathname, copygroup):
		'''recursively load disk tree into MemDir structure'''
		
		self.listdir(pathname, copygroup)
		
		for d in self.subdirs:
			if d.copygroup == copygroup:		# otherwise, dir does not exist for this group
				d.loaddir(pathname + '/' + d.name, copygroup)
	
	def load_copygroups(self, group):
		'''load all copygroups and merge them together in this MemDir tree'''
		
		copygroups_dir = os.path.join(synctool_config.MASTERDIR, 'copygroups')
		if os.path.isdir(copygroups_dir):
			existing_copygroups = os.listdir(copygroups_dir)
			
			# TODO change this; for copygroup in reversed MY_GROUPS[]
			for copygroup in existing_copygroups:
				self.loaddir(os.path.join(copygroups_dir, copygroup), copygroup)
			
	
	def walk(self, pathname, callback):
		'''walk the tree, calling the callback function on each entry'''
		'''The callback takes two arguments: the pathname, the copygroup'''
		
		path = pathname + '/' + self.name
		callback(path, self.copygroup)
		
		if path == '/':
			path = ''
		
		for f in self.files:
			filename = path + '/' + f
			callback(filename, self.files[f])
		
		for d in self.subdirs:
			d.walk(path, callback)


def memdir_walk_callback(path, copygroup):
	print 'TD: walking group %s: %s' % (copygroup, path)


def test_copygroups():
	root = MemDir()
	root.loaddir('/Users/walter/src', 'src')
	root.loaddir('/Users/walter/src/python', 'python')
	
	root.walk('', memdir_walk_callback)


if __name__ == '__main__':
	test_copygroups()


# EOB
