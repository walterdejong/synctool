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


class OverlayEntry:
	def __init__(self, src, dest, groupnum):
		self.src_path = src
		self.dest_path = dest
		self.groupnum = groupnum
	
	def __repr__(self):
		return '[<OverlayEntry> %d (%s) (%s)]' % (self.groupnum, self.src_path, self.dest_path)


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


def overlay_pass1(overlay_dir, filelist, dest_dir = '/', highest_groupnum = sys.maxint):
	'''do pass #1 of 2; create list of source and dest files
	Each element in the list in a tuple: (src, dest, groupnum)'''
	
	for entry in os.listdir(overlay_dir):
		(name, groupnum) = split_extension(entry)
		if groupnum < 0:				# not a relevant group
			continue
		
		# inherit lower group level from parent directory
		if groupnum > highest_groupnum:
			groupnum = highest_groupnum
		
		src_path = os.path.join(overlay_dir, entry)
		dest_path = os.path.join(dest_dir, name)
		
		filelist.append(OverlayEntry(src_path, dest_path, groupnum))
		
		if synctool.path_isdir(src_path):
			# recurse into subdir
			overlay_pass1(src_path, filelist, dest_path, groupnum)
	

def overlay_pass2(filelist, filedict):
	'''do pass #2 of 2; create dictionary of destination paths from list
	Each element in the dictionary is a tuple: (src_path, dest_path, groupnum)'''
	
	for entry in filelist:
		if filedict.has_key(entry.dest_path):
			entry2 = filedict[entry.dest_path]
			if entry.groupnum < entry2.groupnum:
				del filedict[entry.dest_path]
				entry2 = None
			else:
				continue
		
		filedict[entry.dest_path] = entry


if __name__ == '__main__':
	## test program ##
	
	synctool_config.MY_GROUPS = ['node1', 'group1', 'group2', 'all']
	GROUP_ALL = synctool_config.MY_GROUPS.index('all')
	
	filelist = []
	overlay_pass1('/Users/walter/src/python/synctool-test/overlay', filelist)
	
	# dump filelist
#	for entry in filelist:
#		print entry
	
	filedict = {}
	overlay_pass2(filelist, filedict)
	
	all_destinations = filedict.keys()
	all_destinations.sort()
	for dest_path in all_destinations:
		print 'dest', dest_path
		entry = filedict[dest_path]
		print 'src %d %s' % (entry.groupnum, entry.src_path)

# EOB
