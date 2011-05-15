#! /usr/bin/env python
#
#	synctool_overlay.py	WJ111
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

# enums for designating trees
OV_OVERLAY = 0
OV_DELETE = 1
OV_TASKS = 2

GROUP_ALL = 0
OVERLAY_DICT = {}
OVERLAY_FILES = []		# sorted list, index to OVERLAY_DICT{}
OVERLAY_LOADED = False
POST_SCRIPTS = {}

DELETE_DICT = {}
DELETE_FILES = []
DELETE_LOADED = False

TASKS_DICT = {}
TASKS_FILES = []
TASKS_LOADED = False


class OverlayEntry:
	def __init__(self, src, dest, groupnum):
		self.src_path = src
		self.dest_path = dest
		self.groupnum = groupnum
	
	def __repr__(self):
		return '[<OverlayEntry> %d (%s) (%s)]' % (self.groupnum, self.src_path, self.dest_path)


def split_extension(entryname):
	'''split a simple filename (without leading path) in a tuple: (name, group number, isPost)
	The group number is the index to MY_GROUPS[] or negative if it is not a relevant group
	The return parameter isPost is a boolean showing whether it is a .post script'''
	
	arr = string.split(entryname, '.')
	if len(arr) <= 1:
		return (entryname, GROUP_ALL+1, False)
	
	ext = arr.pop()
	if ext == 'post':
		# register generic .post script
		return (string.join(arr, '.'), GROUP_ALL+1, True)
	
	if ext[0] != '_':
		return (entryname, GROUP_ALL+1, False)
	
	ext = ext[1:]
	if not ext:
		return (entryname, GROUP_ALL+1, False)
	
	try:
		groupnum = synctool_config.MY_GROUPS.index(ext)
	except ValueError:
		return (None, -1, False)
	
	if len(arr) > 1 and arr[-1] == 'post':
		# register group-specific .post script
		arr.pop()
		return (string.join(arr, '.'), groupnum, True)
	
	return (string.join(arr, '.'), groupnum, False)


def overlay_pass1(overlay_dir, filelist, dest_dir = '/', highest_groupnum = sys.maxint):
	'''do pass #1 of 2; create list of source and dest files
	Each element in the list in a tuple: (src, dest, groupnum)'''
	
	global POST_SCRIPTS
	
	for entry in os.listdir(overlay_dir):
		(name, groupnum, isPost) = split_extension(entry)
		if groupnum < 0:				# not a relevant group
			continue
		
		src_path = os.path.join(overlay_dir, entry)
		dest_path = os.path.join(dest_dir, name)
		
		if isPost:
			# register .post script
			if POST_SCRIPTS.has_key(dest_path):
				if groupnum >= POST_SCRIPTS[dest_path].groupnum:
					continue
			
			POST_SCRIPTS[dest_path] = OverlayEntry(src_path, dest_path, groupnum)
			continue
		
		# inherit lower group level from parent directory
		if groupnum > highest_groupnum:
			groupnum = highest_groupnum
		
		filelist.append(OverlayEntry(src_path, dest_path, groupnum))
		
		if synctool.path_isdir(src_path):
			# recurse into subdir
			overlay_pass1(src_path, filelist, dest_path, groupnum)


def overlay_pass1_without_post_scripts(overlay_dir, filelist, dest_dir = '/', highest_groupnum = sys.maxint):
	'''do pass #1 of 2; create list of source and dest files
	Each element in the list in a tuple: (src, dest, groupnum)
	Do not handle .post scripts'''
	
	for entry in os.listdir(overlay_dir):
		(name, groupnum, isPost) = split_extension(entry)
		if groupnum < 0:				# not a relevant group
			continue
		
		src_path = os.path.join(overlay_dir, entry)
		dest_path = os.path.join(dest_dir, name)
		
		if isPost:
			# unfortunately, the name has been messed up already
			# so therefore just ignore the file and issue a warning
			stderr('warning: ignoring .post script %s' % src_path)
			continue
		
		# inherit lower group level from parent directory
		if groupnum > highest_groupnum:
			groupnum = highest_groupnum
		
		filelist.append(OverlayEntry(src_path, dest_path, groupnum))
		
		if synctool.path_isdir(src_path):
			# recurse into subdir
			overlay_pass1_without_post_scripts(src_path, filelist, dest_path, groupnum)


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


def find_synctree(subdir, pathname):
	'''find the source of a full destination path'''
	
	if subdir == 'overlay':
		if not OVERLAY_LOADED:		# 'demand loading'
			load_overlay_tree()
		
		dict = OVERLAY_DICT
	
	elif subdir == 'delete':
		if not DELETE_LOADED:
			load_delete_tree()
		
		dict = DELETE_DICT
	
	elif subdir == 'tasks':
		if not TASKS_LOADED:
			load_tasks_tree()
		
		dict = TASKS_DICT

	if not dict.has_key(pathname):
		return None
	
	return dict[pathname].src_path


def load_overlay_tree():
	'''scans all overlay dirs in and loads them into OVERLAY_DICT
	which is a dict indexed by destination path, and every element
	in OVERLAY_DICT is an OverlayEntry
	This also prepares POST_SCRIPTS'''
	
	global OVERLAY_DICT, OVERLAY_FILES, OVERLAY_LOADED, POST_SCRIPTS, GROUP_ALL
	
	if OVERLAY_LOADED:
		return
	
	OVERLAY_DICT = {}
	POST_SCRIPTS = {}
	
	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = synctool_config.MY_GROUPS.index('all')
	
	filelist = []
	
	# do pass #1 for multiple overlay dirs: load them into filelist
	for overlay_dir in synctool_config.OVERLAY_DIRS:
		overlay_pass1(overlay_dir, filelist)
	
	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	overlay_pass2(filelist, OVERLAY_DICT)
	
	# sort the filelist
	OVERLAY_FILES = OVERLAY_DICT.keys()
	OVERLAY_FILES.sort()
	
	OVERLAY_LOADED = True


def load_delete_tree():
	'''scans all delete dirs in and loads them into DELETE_DICT
	which is a dict indexed by destination path, and every element
	in DELETE_DICT is an OverlayEntry'''
	
	global DELETE_DICT, DELETE_FILES, DELETE_LOADED, GROUP_ALL
	
	if DELETE_LOADED:
		return
	
	DELETE_DICT = {}
	
	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = synctool_config.MY_GROUPS.index('all')
	
	filelist = []
	
	# do pass #1 for multiple delete dirs: load them into filelist
	for delete_dir in synctool_config.DELETE_DIRS:
		overlay_pass1_without_post_scripts(delete_dir, filelist)
	
	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	overlay_pass2(filelist, DELETE_DICT)
	
	# sort the filelist
	DELETE_FILES = DELETE_DICT.keys()
	DELETE_FILES.sort()
	
	DELETE_LOADED = True


def load_tasks_tree():
	'''scans all tasks dirs in and loads them into TASKS_DICT
	which is a dict indexed by destination path, and every element
	in TASKS_DICT is an OverlayEntry'''
	
	# tasks/ is usually a very 'flat' directory with no complex structure at all
	# However, because it is treated in the same way as overlay/ and delete/,
	# complex structure is possible
	# Still, there is not really a 'destination' for a task script, other than
	# that you can call it with its destination name
	
	global TASKS_DICT, TASKS_FILES, TASKS_LOADED, GROUP_ALL
	
	if TASKS_LOADED:
		return
	
	TASKS_DICT = {}
	
	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = synctool_config.MY_GROUPS.index('all')
	
	filelist = []
	
	# do pass #1 for multiple overlay dirs: load them into filelist
	for tasks_dir in synctool_config.TASKS_DIRS:
		overlay_pass1_with_post_scripts(overlay_dir, filelist)
	
	# run pass #2 : 'squash' filelist into TASKS_DICT
	overlay_pass2(filelist, TASKS_DICT)
	
	# sort the filelist
	TASKS_FILES = TASKS_DICT.keys()
	TASKS_FILES.sort()
	
	TASKS_LOADED = True


def postscript_for_path(path):
	'''return the .post script for a given destination path'''
	
	if not OVERLAY_LOADED:
		load_overlay_tree()
	
	if POST_SCRIPTS.has_key(path):
		return POST_SCRIPTS[path].src_path

	return None


def visit(treedef, callback):
	'''call the callback function on every entry in the tree
	callback will called with two arguments: src_path, dest_path'''
	
	if treedef == OV_OVERLAY:
		load_overlay_tree()
		dict = OVERLAY_DICT
		filelist = OVERLAY_FILES
	
	elif treedef == OV_DELETE:
		load_overlay_tree()			# is needed for .post scripts on directories that change
		load_delete_tree()
		dict = DELETE_DICT
		filelist = DELETE_FILES
	
	elif treedef == OV_TASKS:
		load_tasks_tree()
		dict = TASKS_DICT
		filelist = TASKS_FILES
	
	else:
		raise RuntimeError, 'unknown treedef %d' % treedef
	
	# now call the callback function
	for dest_path in filelist:
		callback(dict[dest_path].src_path, dest_path)


if __name__ == '__main__':
	## test program ##
	
	synctool_config.CONF_FILE = '../../synctool-test/synctool.conf'
	synctool_config.read_config()
	synctool_config.MY_GROUPS = ['node1', 'group1', 'group2', 'all']
	
	load_overlay_tree()
	
	for dest_path in OVERLAY_FILES:
		print 'dest', dest_path
		entry = OVERLAY_DICT[dest_path]
		print 'src %d %s' % (entry.groupnum, entry.src_path)
		
		# check for .post script
		if POST_SCRIPTS.has_key(dest_path):
			post_script = POST_SCRIPTS[dest_path]
			print 'post %d %s' % (post_script.groupnum, post_script.src_path)

	print
	print 'find_synctree() test:', find_synctree('overlay', '/Users/walter/src/python/synctool-test/testroot/etc/hosts.allow')


# EOB
