#
#	synctool_overlay.py	WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import sys
import fnmatch

import synctool.lib
from synctool.lib import verbose, stderr, terse
import synctool.object
import synctool.param
import synctool.syncstat

# enums for designating trees
OV_OVERLAY = 0
OV_DELETE = 1

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


class OverlayEntry(object):
	'''structure that describes a source file under $overlay/'''

	def __init__(self, name, importance, is_post):
		'''name is the 'basename' of the source file
		importance is the index to MY_GROUPS[] or
		negative if it is not a relevant group
		is_post is a boolean saying whether it is a .post script'''

		self.name = name
		self.importance = importance
		self.is_post = is_post


def _split_extension(src_path, filename, require_extension):
	'''split simple filename in name, extension
	Returns: instance of OverlayEntry or None
	on error or not one of my groups

	Prereq: GROUP_ALL must be set to MY_GROUPS.index('all')'''

	# src_path is only passed for printing error messages, really
	# I don't want to have to call os.path.basename() all the time
	# when it is unnecessary (see it as a peephole optimisation)

	require_extension = require_extension and synctool.param.REQUIRE_EXTENSION

	(name, ext) = os.path.splitext(filename)
	if not ext:
		if require_extension:
			_no_group_ext(src_path)
			return None

		return OverlayEntry(filename, GROUP_ALL, False)

	if ext == '.post':
		# register generic .post script
		return OverlayEntry(name, GROUP_ALL, True)

	if ext[:2] != '._':
		if require_extension:
			_no_group_ext(src_path)
			return None

		return OverlayEntry(filename, GROUP_ALL, False)

	ext = ext[2:]
	if not ext:
		if require_extension:
			_no_group_ext(src_path)
			return None

		return OverlayEntry(filename, GROUP_ALL, False)

	try:
		importance = synctool.param.MY_GROUPS.index(ext)
	except ValueError:
		if not ext in synctool.param.ALL_GROUPS:
			_unknown_group(src_path)
			return None

		# it is not one of my groups
		return None

	(name2, ext) = os.path.splitext(name)

	if ext == '.post':
		# register group-specific .post script
		return OverlayEntry(name2, importance, True)

	return OverlayEntry(name, importance, False)


def _no_group_ext(src_path):
	'''prints error message; group extension was required,
	but no group extension was found on the source filename'''

	if synctool.param.TERSE:
		terse(synctool.lib.TERSE_ERROR, 'no group on %s' % src_path)
	else:
		stderr('no underscored group extension on %s, skipped' %
			synctool.lib.prettypath(src_path))


def _unknown_group(src_path):
	'''prints error message; source has an unknown group as extension'''

	if synctool.param.TERSE:
		terse(synctool.lib.TERSE_ERROR, 'invalid group on %s' % src_path)
	else:
		stderr('unknown group on %s, skipped' %
				synctool.lib.prettypath(src_path))


def relevant_overlay_dirs(overlay_dir):
	'''return list of subdirs that are relevant groups
	Return value is an array of pairs: (fullpath to dir, importance)'''

	a = []

	for entry in os.listdir(overlay_dir):
		try:
			importance = synctool.param.MY_GROUPS.index(entry)
		except ValueError:
			continue

		if importance == -1:
			verbose('dir %s/ is not one of my groups, skipping' % entry)
			continue

		d = os.path.join(overlay_dir, entry)
		if os.path.isdir(d):
			a.append((d, importance))
			verbose('scanning %s/' % synctool.lib.prettypath(d))

	return a


def _overlay_pass1(overlay_dir, filelist, dest_dir=os.sep,
	highest_importance=sys.maxint):
	'''do pass #1 of 2; create list of source and dest files
	Each element in the list is an instance of SyncObject'''

#	verbose('overlay pass 1 %s/' % overlay_dir)

	for entry in os.listdir(overlay_dir):
		if entry in synctool.param.IGNORE_FILES:
			continue

		src_path = os.path.join(overlay_dir, entry)
		src_stat = synctool.syncstat.SyncStat(src_path)

		if src_stat.is_dir():
			if entry[0] == '.' and synctool.param.IGNORE_DOTDIRS:
				continue

			is_dir = True
		else:
			if entry[0] == '.' and synctool.param.IGNORE_DOTFILES:
				continue

			is_dir = False

		# check any ignored files with wildcards
		# before any group extension is examined
		wildcard_match = False
		for wildcard_entry in synctool.param.IGNORE_FILES_WITH_WILDCARDS:
			if fnmatch.fnmatchcase(entry, wildcard_entry):
				wildcard_match = True
				break

		if wildcard_match:
			continue

		ov_entry = _split_extension(src_path, entry, not is_dir)
		if not ov_entry:
			# either not a relevant group (skip it)
			# or an error occurred (error message already printed)
			continue

		if ov_entry.name in synctool.param.IGNORE_FILES:
			continue

		# inherit lower group level from parent directory
		if ov_entry.importance > highest_importance:
			ov_entry.importance = highest_importance

		if ov_entry.is_post:
			if not src_stat.is_exec():
				if synctool.param.TERSE:
					terse(synctool.lib.TERSE_WARNING, 'not exec %s' %
														src_path)
				else:
					stderr('warning: .post script %s is not executable, '
							'ignored' % synctool.lib.prettypath(src_path))
				continue

			# register .post script
			# trigger is the source file that would trigger
			# the .post script to run
			trigger = os.path.join(overlay_dir, ov_entry.name)

			if POST_SCRIPTS.has_key(trigger):
				if (ov_entry.importance >=
					POST_SCRIPTS[trigger].importance):
					continue

			POST_SCRIPTS[trigger] = synctool.object.SyncObject(src_path,
										dest_dir, ov_entry.importance,
										src_stat)
			continue

		dest_path = os.path.join(dest_dir, ov_entry.name)
		filelist.append(synctool.object.SyncObject(src_path, dest_path,
						ov_entry.importance, src_stat))

		if is_dir:
			# recurse into subdir
			_overlay_pass1(src_path, filelist, dest_path, ov_entry.importance)


def _overlay_pass2(filelist, filedict):
	'''do pass #2 of 2; create dictionary of destination paths from list
	Each element in the dictionary is an instance of SyncObject'''

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
			elif ((not (entry.src_stat.is_dir() and
				entry2.src_stat.is_dir())) and
				entry.importance == entry2.importance):

				if synctool.param.TERSE:
					synctool.lib.terse(synctool.lib.TERSE_ERROR,
								'duplicate source paths in repository for:')
					synctool.lib.terse(synctool.lib.TERSE_ERROR,
										entry.src_path)
					synctool.lib.terse(synctool.lib.TERSE_ERROR,
										entry2.src_path)
				else:
					stderr('error: duplicate source paths in repository '
							'for:\n'
							'error: %s\n'
							'error: %s\n' % (entry.print_src(),
											entry2.print_src()))
				continue

			else:
				# this group is less important, skip it
				continue

		# add or update filedict
		filedict[entry.dest_path] = entry


def _load_overlay_tree():
	'''scans all overlay dirs in and loads them into OVERLAY_DICT
	which is a dict indexed by destination path, and every element
	in OVERLAY_DICT is an instance of SyncObject
	This also prepares POST_SCRIPTS'''

	global OVERLAY_DICT, OVERLAY_FILES, OVERLAY_LOADED, POST_SCRIPTS
	global GROUP_ALL

	if OVERLAY_LOADED:
		return

	OVERLAY_DICT = {}
	POST_SCRIPTS = {}

	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = len(synctool.param.MY_GROUPS) - 1

	filelist = []

	# do pass #1 for multiple overlay dirs: load them into filelist
	for (d, importance) in relevant_overlay_dirs(synctool.param.OVERLAY_DIR):
		_overlay_pass1(d, filelist, os.sep, importance)

	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	_overlay_pass2(filelist, OVERLAY_DICT)

	# sort the filelist
	OVERLAY_FILES = OVERLAY_DICT.keys()
	OVERLAY_FILES.sort()

	OVERLAY_LOADED = True


def _load_delete_tree():
	'''scans all delete dirs in and loads them into DELETE_DICT
	which is a dict indexed by destination path, and every element
	in DELETE_DICT is an instance of SyncObject
	This also prepares POST_SCRIPTS that may be in the delete/ tree'''

	global DELETE_DICT, DELETE_FILES, DELETE_LOADED, GROUP_ALL

	if DELETE_LOADED:
		return

	DELETE_DICT = {}

	# ensure that GROUP_ALL is set correctly
	GROUP_ALL = len(synctool.param.MY_GROUPS) - 1

	filelist = []

	# do pass #1 for multiple delete dirs: load them into filelist
	for (d, importance) in relevant_overlay_dirs(synctool.param.DELETE_DIR):
		_overlay_pass1(d, filelist, os.sep, importance)

	# run pass #2 : 'squash' filelist into OVERLAY_DICT
	_overlay_pass2(filelist, DELETE_DICT)

	# sort the filelist
	DELETE_FILES = DELETE_DICT.keys()
	DELETE_FILES.sort()

	DELETE_LOADED = True


def postscript_for_path(src, dest):
	'''return the .post script for a given source and destination path'''

	if not OVERLAY_LOADED:
		_load_overlay_tree()

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


def _select_tree(treedef):
	'''Returns (dict, filelist) for the corresponding treedef number'''

	if treedef == OV_OVERLAY:
		_load_overlay_tree()
		return (OVERLAY_DICT, OVERLAY_FILES)

	elif treedef == OV_DELETE:
		# overlay_tree is needed for .post scripts on dirs that change
		_load_overlay_tree()
		_load_delete_tree()
		return (DELETE_DICT, DELETE_FILES)

	raise RuntimeError, 'unknown treedef %d' % treedef


def find(treedef, dest_path):
	'''find the source for a full destination path
	Return value is a tuple: (SyncObject, OV_FOUND)
	Return value is (None, OV_NOT_FOUND) if source does not exist'''

	(tree_dict, filelist) = _select_tree(treedef)

	if not tree_dict.has_key(dest_path):
		return (None, OV_NOT_FOUND)

	return (tree_dict[dest_path], OV_FOUND)


def find_terse(treedef, terse_path):
	'''find the full source and dest paths for a terse destination path
	Return value is a tuple (SyncObject, OV_FOUND)
	Return value is (None, OV_NOT_FOUND) if source does not exist
	Return value is (None, OV_FOUND_MULTIPLE) if multiple sources
	are possible'''

	(tree_dict, filelist) = _select_tree(treedef)

	idx = terse_path.find('...')
	if idx == -1:
		if terse_path[:2] == '//':
			terse_path = os.path.join(synctool.param.VAR_DIR,
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
		overlay_entry = tree_dict[entry]

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

	(tree_dict, filelist) = _select_tree(treedef)

	# now call the callback function
	#
	# note that the order is important, so do not use
	# "for obj in tree_dict: callback(obj)"

	for dest_path in filelist:
		callback(tree_dict[dest_path])


# EOB
