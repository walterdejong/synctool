#
#	synctool_overlay.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_object
import synctool_param
import synctool_lib

from synctool_lib import verbose, stderr, terse

import os
import sys
import string
import fnmatch

import synctool.stat

# enums for designating trees
OV_OVERLAY = 0
OV_DELETE = 1

# error codes for split_extension()
OV_NOT_MY_GROUP = -1
OV_NO_GROUP_EXT = -2
OV_UNKNOWN_GROUP = -3

# error codes for find() and find_terse()
OV_FOUND = 0
OV_NOT_FOUND = 1
OV_FOUND_MULTIPLE = 2

GROUP_ALL = 0
OVERLAY_DICT = {}
OVERLAY_FILES = []		# sorted list, index to OVERLAY_DICT{}
OVERLAY_LOADED = False
POST_SCRIPTS = {}		# dict indexed by trigger: full source path
						# without final extension
DELETE_DICT = {}
DELETE_FILES = []
DELETE_LOADED = False


def split_extension(filename, require_extension):
	'''split a simple filename (without leading path)
	in a tuple: (name, group number, isPost)
	The importance is the index to MY_GROUPS[]
	or negative if it is not a relevant group
	The return parameter isPost is a boolean
	showing whether it is a .post script

	Prereq: GROUP_ALL must be set to MY_GROUPS.index('all')'''

	require_extension = require_extension and synctool_param.REQUIRE_EXTENSION

	(name, ext) = os.path.splitext(filename)

	if not ext:
		if require_extension:
			return (None, OV_NO_GROUP_EXT, False)

		return (filename, GROUP_ALL, False)

	if ext == '.post':
		# register generic .post script
		return (name, GROUP_ALL, True)

	if ext[:2] != '._':
		if require_extension:
			return (None, OV_NO_GROUP_EXT, False)

		return (filename, GROUP_ALL, False)

	ext = ext[2:]
	if not ext:
		if require_extension:
			return (None, OV_NO_GROUP_EXT, False)

		return (filename, GROUP_ALL, False)

	try:
		importance = synctool_param.MY_GROUPS.index(ext)
	except ValueError:
		if not ext in synctool_param.ALL_GROUPS:
			return (None, OV_UNKNOWN_GROUP, False)

		return (None, OV_NOT_MY_GROUP, False)

	(name2, ext) = os.path.splitext(name)

	if ext == '.post':
		# register group-specific .post script
		return (name2, importance, True)

	return (name, importance, False)


def ov_perror(errorcode, src_path):
	'''print error message for source path'''

	if errorcode >= 0:
		# this is not an error but a valid group number
		return

	if errorcode == OV_NOT_MY_GROUP:
		# this is not an error but a normal condition
		return

	if errorcode == OV_NO_GROUP_EXT:
		if synctool_param.TERSE:
			terse(synctool_lib.TERSE_ERROR, 'no group on %s' % src_path)
		else:
			stderr('no underscored group extension on %s, skipped' %
				synctool_lib.prettypath(src_path))

	elif errorcode == OV_UNKNOWN_GROUP:
		if synctool_param.TERSE:
			terse(synctool_lib.TERSE_ERROR, 'invalid group on %s' % src_path)
		else:
			stderr('unknown group on %s, skipped' %
				synctool_lib.prettypath(src_path))


def relevant_overlay_dirs(overlay_dir):
	'''return list of subdirs that are relevant groups
	Return value is an array of pairs: (fullpath to dir, importance)
	'''

	a = []

	for entry in os.listdir(overlay_dir):
		try:
			importance = synctool_param.MY_GROUPS.index(entry)
		except ValueError:
			continue

		if importance == -1:
			verbose('dir %s/ is not one of my groups, skipping' %
					entry)
			continue

		d = os.path.join(overlay_dir, entry)
		if os.path.isdir(d):
			a.append((d, importance))
			verbose('scanning %s/' % synctool_lib.prettypath(d))

	return a


def overlay_pass1(overlay_dir, filelist, dest_dir = os.path.sep,
	highest_importance = sys.maxint, handle_postscripts = True):
	'''do pass #1 of 2; create list of source and dest files
	Each element in the list is an instance of SyncObject'''

	global POST_SCRIPTS

#	verbose('overlay pass 1 %s/' % overlay_dir)

	for entry in os.listdir(overlay_dir):
		if entry in synctool_param.IGNORE_FILES:
			continue

		src_path = os.path.join(overlay_dir, entry)
		src_statbuf = synctool.stat.SyncStat(src_path)

		if src_statbuf.isDir():
			if synctool_param.IGNORE_DOTDIRS and entry[0] == '.':
				continue

			isDir = True
		else:
			if synctool_param.IGNORE_DOTFILES and entry[0] == '.':
				continue

			isDir = False

		# check any ignored files with wildcards
		# before any group extension is examined
		wildcard_match = False
		for wildcard_entry in synctool_param.IGNORE_FILES_WITH_WILDCARDS:
			if fnmatch.fnmatchcase(entry, wildcard_entry):
				wildcard_match = True
				break

		if wildcard_match:
			continue

		(name, importance, isPost) = split_extension(entry, not isDir)

		if importance < 0:
			# not a relevant group, so skip it
			# This also prunes trees if you have group-specific subdirs

			if importance != OV_NOT_MY_GROUP:
				# "not my group" is a rather normal error code, but if it is
				# something else, it's a serious error that we should report
				ov_perror(importance, os.path.join(overlay_dir, entry))

			continue

		if name in synctool_param.IGNORE_FILES:
			continue

		# inherit lower group level from parent directory
		if importance > highest_importance:
			importance = highest_importance

		if isPost:
			if handle_postscripts:
				if not src_statbuf.isExec():
					stderr('warning: .post script %s is not executable, '
						'ignored' % synctool_lib.prettypath(src_path))
					continue

				# register .post script
				# trigger is the source file that would trigger
				# the .post script to run
				trigger = os.path.join(overlay_dir, name)

				if POST_SCRIPTS.has_key(trigger):
					if importance >= POST_SCRIPTS[trigger].importance:
						continue

				POST_SCRIPTS[trigger] = synctool_object.SyncObject(src_path,
										dest_dir, importance, src_statbuf)
			else:
				# unfortunately, the name has been messed up already
				# so therefore just ignore the file and issue a warning
				if synctool_param.TERSE:
					terse(synctool_lib.TERSE_WARNING, 'ignoring %s' %
														src_path)
				else:
					stderr('warning: ignoring .post script %s' %
						synctool_lib.prettypath(src_path))

			continue

		dest_path = os.path.join(dest_dir, name)

		filelist.append(synctool_object.SyncObject(src_path, dest_path,
						importance, src_statbuf))

		if isDir:
			# recurse into subdir
			overlay_pass1(src_path, filelist, dest_path, importance,
				handle_postscripts)


def overlay_pass2(filelist, filedict):
	'''do pass #2 of 2; create dictionary of destination paths from list
	Each element in the dictionary is an instance of OverlayEntry'''

#	verbose('overlay pass 2')

	for entry in filelist:
		if filedict.has_key(entry.dest_path):
			entry2 = filedict[entry.dest_path]

			if entry.importance < entry2.importance:
				# this group is more important, so override it
				del filedict[entry.dest_path]
				entry2 = None

			# duplicate paths are a problem, unless they are directories
			# They are easy to fix however, just assign the right extension
			elif ((not (entry.src_isDir() and entry2.src_isDir())) and
				entry.importance == entry2.importance):

				if synctool_param.TERSE:
					synctool_lib.terse(synctool_lib.TERSE_ERROR,
						'duplicate source paths in repository for:')
					synctool_lib.terse(synctool_lib.TERSE_ERROR,
						entry.src_path)
					synctool_lib.terse(synctool_lib.TERSE_ERROR,
						entry2.src_path)
				else:
					stderr('error: duplicate source paths in repository '
							'for:\n'
							'error: %s\n'
							'error: %s\n' %
							(synctool_lib.prettypath(entry.src_path),
							synctool_lib.prettypath(entry2.src_path)))

				continue

			else:
				# this group is less important, skip it
				continue

		# add or update filedict
		filedict[entry.dest_path] = entry


def load_overlay_tree():
	'''scans all overlay dirs in and loads them into OVERLAY_DICT
	which is a dict indexed by destination path, and every element
	in OVERLAY_DICT is an instance of OverlayEntry
	This also prepares POST_SCRIPTS'''

	global OVERLAY_DICT, OVERLAY_FILES, OVERLAY_LOADED, POST_SCRIPTS
	global GROUP_ALL

	if OVERLAY_LOADED:
		return

	OVERLAY_DICT = {}
	POST_SCRIPTS = {}

	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = len(synctool_param.MY_GROUPS) - 1

	filelist = []

	# do pass #1 for multiple overlay dirs: load them into filelist
	for (d, importance) in relevant_overlay_dirs(synctool_param.OVERLAY_DIR):
		overlay_pass1(d, filelist, os.path.sep, importance)

	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	overlay_pass2(filelist, OVERLAY_DICT)

	# sort the filelist
	OVERLAY_FILES = OVERLAY_DICT.keys()
	OVERLAY_FILES.sort()

	OVERLAY_LOADED = True


def load_delete_tree():
	'''scans all delete dirs in and loads them into DELETE_DICT
	which is a dict indexed by destination path, and every element
	in DELETE_DICT is an instance of OverlayEntry
	This also prepares POST_SCRIPTS that may be in the delete/ tree'''

	global DELETE_DICT, DELETE_FILES, DELETE_LOADED, GROUP_ALL

	if DELETE_LOADED:
		return

	DELETE_DICT = {}

	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = len(synctool_param.MY_GROUPS) - 1

	filelist = []

	# do pass #1 for multiple delete dirs: load them into filelist
	for (d, importance) in relevant_overlay_dirs(synctool_param.DELETE_DIR):
		overlay_pass1(d, filelist, os.path.sep, importance)

	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	overlay_pass2(filelist, DELETE_DICT)

	# sort the filelist
	DELETE_FILES = DELETE_DICT.keys()
	DELETE_FILES.sort()

	DELETE_LOADED = True


def postscript_for_path(src, dest):
	'''return the .post script for a given source and destination path'''

	if not OVERLAY_LOADED:
		load_overlay_tree()

	# the trigger for .post scripts is the source path of
	# the script with the .post and group extensions stripped off
	# -- which is the same as taking the source dir and appending
	# the dest basename
	# This ensures that the .post script that is chosen, is always
	# the one that is next to the source file in the overlay tree
	# This is important; otherwise having multiple overlay trees
	# could lead to ambiguity regarding what .post script to run

	trigger = os.path.join(os.path.dirname(src), os.path.basename(dest))

	if POST_SCRIPTS.has_key(trigger):
		return POST_SCRIPTS[trigger].src_path

	return None


def select_tree(treedef):
	'''Returns (dict, filelist) for the corresponding treedef number'''

	if treedef == OV_OVERLAY:
		load_overlay_tree()
		return (OVERLAY_DICT, OVERLAY_FILES)

	elif treedef == OV_DELETE:
		# overlay_tree is needed for .post scripts on dirs that change
		load_overlay_tree()
		load_delete_tree()
		return (DELETE_DICT, DELETE_FILES)

	raise RuntimeError, 'unknown treedef %d' % treedef


def find(treedef, dest_path):
	'''find the source for a full destination path
	Return value is a tuple: (SyncObject, OV_FOUND)
	Return value is (None, OV_NOT_FOUND) if source does not exist'''

	(dict, filelist) = select_tree(treedef)

	if not dict.has_key(dest_path):
		return (None, OV_NOT_FOUND)

	return (dict[dest_path], OV_FOUND)


def find_terse(treedef, terse_path):
	'''find the full source and dest paths for a terse destination path
	Return value is a tuple (SyncObject, OV_FOUND)
	Return value is (None, OV_NOT_FOUND) if source does not exist
	Return value is (None, OV_FOUND_MULTIPLE) if multiple sources
	are possible'''

	(dict, filelist) = select_tree(treedef)

	idx = string.find(terse_path, '...')
	if idx == -1:
		if terse_path[:2] == '//':
			terse_path = os.path.join(synctool_param.MASTERDIR,
				terse_path[2:])

		# this is not really a terse path, return a regular find()
		return find(treedef, terse_path)

	ending = terse_path[(idx+3):]

	matches = []
	len_ending = len(ending)

	# do a stupid linear search and find all matches, which means
	# keep on scanning even though you've already found a match ...
	# but it must be done because we want to be sure that we have found
	# the one perfect match
	#
	# A possibility to improve on the linear search would be to break
	# the paths down into a in-memory directory tree and walk it from the
	# leaves up to the root rather than from the root down to the leaves
	# Yeah, well ...
	#
	for entry in filelist:
		overlay_entry = dict[entry]

		l = len(overlay_entry.dest_path)
		if l > len_ending:
			# first do a quick test
			if overlay_entry.dest_path[-1] != ending[-1]:
				continue

			# check the ending path
			if overlay_entry.dest_path[(l - len_ending):] == ending:
				matches.append(overlay_entry)

	if not matches:
		return (None, OV_NOT_FOUND)

	if len(matches) > 1:
		stderr('There are multiple possible sources for this terse path. '
				'Pick one:')

		n = 0
		for overlay_entry in matches:
			stderr('%2d. %s' % (n, overlay_entry.dest_path))
			n += 1

		return (None, OV_FOUND_MULTIPLE)

	# good, there was only one match

	return (matches[0], OV_FOUND)


def visit(treedef, callback):
	'''call the callback function on every entry in the tree
	callback will called with one argument: the SyncObject'''

	(dict, filelist) = select_tree(treedef)

	# now call the callback function
	#
	# note that the order is important, so do not use
	# "for obj in dict: callback(obj)"
	#
	for dest_path in filelist:
		callback(dict[dest_path])


# EOB
