#
#	synctool_overlay.py	WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool.overlay

	There are two ways of implementing an overlay procedure:
	1. foreach direntry split the extension; get the 'importance'
	   sort by importance
	   keep the first entry with 'name', discard others (less important)

	2. foreach direntry split the extension; get the 'importance'
	   put entry into dictionary with destination as key
	   If dictionary entry already exists, compare the importance, overrule

	synctool 5 uses method 2. Older synctool uses method 1.
	synctool 6 uses method 1 + 2.

	Consider this tree:
	 $overlay/all/etc/ntp.conf._n1
     $overlay/all/etc._n1/ntp.conf._all
	 $overlay/all/etc._n1/ntp.conf._n1
	 $overlay/n1/etc/ntp.conf._all
	 $overlay/n1/etc/ntp.conf._n1
	 $overlay/n1/etc._n1/ntp.conf._all
	 $overlay/n1/etc._n1/ntp.conf._n1

	Method 1 can not correctly resolve inter-directory duplicates.
	Method 2 works most of the time, but may encounter difficulty
	with inter-directory duplicates. The reason is that all of the
	above listed entries have the same importance: 0.
	Ideally synctool should select the final entry. This is only
	correctly resolved when both method 1 and 2 are combined.
'''

import os
import sys
import fnmatch

import synctool.lib
from synctool.lib import verbose, stderr, terse
import synctool.object
import synctool.param
import synctool.syncstat

# last index of MY_GROUPS
GROUP_ALL = 1000

# used with find() and _find_callback() function
_SEARCH = None
_FOUND = None
_POST_DICT = None

# used with _find_terse() and _find_terse_callback() function
_TERSE_ENDING = None
_TERSE_LEN = 0
_TERSE_MATCHES = None


class OverlayObject(object):
	'''structure that represents an entry in the overlay/ tree'''

	def __init__(self, src_name, dest_name, is_post=False, no_ext=False):
		'''src_name is simple filename without leading path
		dest_name is the src_name without group extension'''

		self.src_path = src_name
		self.dest_path = dest_name
		self.is_post = is_post
		self.no_ext = no_ext
		self.src_stat = self.dest_state = None

	def make(self, src_dir, dest_dir):
		'''make() fills in the full paths and stat structures'''

		self.src_path = os.path.join(src_dir, self.src_path)
		self.src_stat = synctool.syncstat.SyncStat(self.src_path)
		self.dest_path = os.path.join(dest_dir, self.dest_path)
		self.dest_stat = synctool.syncstat.SyncStat(self.dest_path)

	def print_src(self):
		'''pretty print my source path'''

		if self.src_stat and self.src_stat.is_dir():
			return synctool.lib.prettypath(self.src_path) + os.sep

		return synctool.lib.prettypath(self.src_path)

	def __repr__(self):
		return self.src_path


def _sort_by_importance(item1, item2):
	'''item is a tuple (x, importance)'''
	return cmp(item1[1], item2[1])


def _toplevel(overlay):
	'''Returns sorted list of fullpath directories under overlay/'''

	arr = []
	for entry in os.listdir(overlay):
		fullpath = os.path.join(overlay, entry)
		try:
			importance = synctool.param.MY_GROUPS.index(entry)
		except ValueError:
			verbose('%s/ is not one of my groups, skipping' %
					synctool.lib.prettypath(fullpath))
			continue

		arr.append((fullpath, importance))

	arr.sort(_sort_by_importance)

	# return list of only the directory names
	return [x[0] for x in arr]


def _split_extension(filename, src_dir):
	'''filename in the overlay tree, without leading path
	src_dir is passed for the purpose of printing error messages
	Returns tuple: OverlayObject, importance

	Prereq: GROUP_ALL must be set to len(MY_GROUPS)-1'''

	(name, ext) = os.path.splitext(filename)
	if not ext:
		return OverlayObject(filename, name, no_ext=True), GROUP_ALL

	if ext == '.post':
		# register generic .post script
		return OverlayObject(filename, name, is_post=True), GROUP_ALL

	if ext[:2] != '._':
		return OverlayObject(filename, filename, no_ext=True), GROUP_ALL

	ext = ext[2:]
	if not ext:
		return OverlayObject(filename, filename, no_ext=True), GROUP_ALL

	try:
		importance = synctool.param.MY_GROUPS.index(ext)
	except ValueError:
		if not ext in synctool.param.ALL_GROUPS:
			src_path = os.path.join(src_dir, filename)
			if synctool.param.TERSE:
				terse(synctool.lib.TERSE_ERROR, 'invalid group on %s' %
												src_path)
			else:
				stderr('unknown group on %s, skipped' %
						synctool.lib.prettypath(src_path))
			return None, -1

		# it is not one of my groups
		verbose('skipping %s, it is not one of my groups' %
				synctool.lib.prettypath(os.path.join(src_dir, filename)))
		return None, -1

	(name2, ext) = os.path.splitext(name)

	if ext == '.post':
		# register group-specific .post script
		return OverlayObject(filename, name2, is_post=True), importance

	return OverlayObject(filename, name), importance


def _sort_by_importance_post_first(item1, item2):
	'''sort by importance, but always put .post scripts first'''

	obj1, importance1 = item1
	obj2, importance2 = item2

	if obj1.is_post:
		if obj2.is_post:
			return cmp(importance1, importance2)

		return -1

	if obj2.is_post:
		return 1

	return cmp(importance1, importance2)


def _walk_subtree(src_dir, dest_dir, duplicates, post_dict, callback):
	'''walk subtree under overlay/group/
	duplicates is a set that keeps us from selecting any duplicate matches
	post_dict holds .post scripts with destination as key'''

#	verbose('_walk_subtree(%s)' % src_dir)

	arr = []
	for entry in os.listdir(src_dir):
		if entry in synctool.param.IGNORE_FILES:
			verbose('ignoring %s' %
					synctool.lib.prettypath(os.path.join(src_dir, entry)))
			continue

		# check any ignored files with wildcards
		# before any group extension is examined
		wildcard_match = False
		for wildcard_entry in synctool.param.IGNORE_FILES_WITH_WILDCARDS:
			if fnmatch.fnmatchcase(entry, wildcard_entry):
				wildcard_match = True
				verbose('ignoring %s (pattern match)' %
						synctool.lib.prettypath(os.path.join(src_dir, entry)))
				break

		if wildcard_match:
			continue

		obj, importance = _split_extension(entry, src_dir)
		if not obj:
			continue

		arr.append((obj, importance))

	# sort with .post scripts first
	# this ensures that post_dict will have the required script when needed
	arr.sort(_sort_by_importance_post_first)

	dir_changed = False

	for obj, importance in arr:
		obj.make(src_dir, dest_dir)

		if obj.is_post:
			if post_dict.has_key(obj.dest_path):
				continue

			post_dict[obj.dest_path] = obj.src_path
			continue

		if obj.src_stat.is_dir():
			if synctool.param.IGNORE_DOTDIRS:
				name = os.path.basename(obj.src_path)
				if name[0] == '.':
					verbose('ignoring dotdir %s' % obj.print_src())
					continue

			# if there is a .post script on this dir, pass it on
			subdir_post_dict = {}
			if post_dict.has_key(obj.dest_path):
				subdir_post_dict[obj.dest_path] = post_dict[obj.dest_path]

			if not _walk_subtree(obj.src_path, obj.dest_path, duplicates,
									subdir_post_dict, callback):
				# quick exit
				return False

			if obj.dest_path in duplicates:
				# there already was a more important source for this dir
				continue

			duplicates.add(obj.dest_path)

			# run callback on the directory itself
			sync_obj = synctool.object.SyncObject(obj.src_path, obj.dest_path,
											0, obj.src_stat, obj.dest_stat)
			ok, changed = callback(sync_obj, post_dict, dir_changed)
			if not ok:
				# quick exit
				return False

			continue

		if synctool.param.IGNORE_DOTFILES:
			name = os.path.basename(obj.src_path)
			if name[0] == '.':
				verbose('ignoring dotfile %s' % obj.print_src())
				continue

		if synctool.param.REQUIRE_EXTENSION and obj.no_ext:
			if synctool.param.TERSE:
				terse(synctool.lib.TERSE_ERROR, 'no group on %s' %
													obj.src_path)
			else:
				stderr('no group extension on %s, skipped' % obj.print_src())
			continue

		if obj.dest_path in duplicates:
			# there already was a more important source for this destination
			continue

		duplicates.add(obj.dest_path)

		sync_obj = synctool.object.SyncObject(obj.src_path, obj.dest_path,
										0, obj.src_stat, obj.dest_stat)
		ok, updated = callback(sync_obj, post_dict)
		if not ok:
			# quick exit
			return False

		dir_changed |= updated

	return True


def visit(overlay, callback):
	'''visit all entries in the overlay tree
	overlay is either synctool.param.OVERLAY_DIR or synctool.param.DELETE_DIR
	callback will called with arguments: (SyncObject, post_dict)
	callback must return a two booleans: ok, updated'''

	global GROUP_ALL

	GROUP_ALL = len(synctool.param.MY_GROUPS) - 1

	duplicates = set()

	for d in _toplevel(overlay):
		if not _walk_subtree(d, os.sep, duplicates, {}, callback):
			# quick exit
			break


def _find_callback(obj, post_dict, dir_changed=False):
	'''callback function used with find()'''

	global _FOUND, _POST_DICT

	if obj.dest_path == _SEARCH:
		_FOUND = obj
		_POST_DICT = post_dict
		return False, False		# signal quick exit

	return True, False


def find(overlay, dest_path):
	'''search repository for source of dest_path
	Returns two values: SyncObject, post_dict
	or None, None if not found'''

	global _SEARCH, _FOUND, _POST_DICT

	# TODO handle terse paths

	_SEARCH = dest_path
	_FOUND = None
	_POST_DICT = None

	visit(overlay, _find_callback)

	return _FOUND, _POST_DICT


def _find_terse_callback(obj, post_dict, dir_changed=False):
	'''callback function used with find_terse()'''

	global _POST_DICT

	l = len(obj.dest_path)
	if l > _TERSE_LEN:
		# first do a quick test
		if obj.dest_path[-1] != _TERSE_ENDING[-1]:
			return True, False

		# check the ending path
		if obj.dest_path[(l - _TERSE_LEN):] == _TERSE_ENDING:
			_TERSE_MATCHES.append(obj)
			_POST_DICT = post_dict
			# keep on scanning to find all matches

	return True, False


def find_terse(overlay, terse_path):
	'''find the full source and dest paths for a terse destination path
	Returns two values: SyncObject, post_dict
	or None, None if source does not exist
	or None, {} if multiple sources are possible'''

	global _TERSE_MATCHES, _TERSE_ENDING, _TERSE_LEN

	idx = terse_path.find('...')
	if idx == -1:
		if terse_path[:2] == '//':
			terse_path = os.path.join(synctool.param.VAR_DIR, terse_path[2:])

		# this is not really a terse path, return a regular find()
		return find(overlay, terse_path)

	_TERSE_ENDING = terse_path[(idx+3):]
	_TERSE_LEN = len(_TERSE_ENDING)
	_TERSE_MATCHES = []

	visit(overlay, _find_terse_callback)

	if not _TERSE_MATCHES:
		return None, None

	if len(_TERSE_MATCHES) > 1:
		stderr('There are multiple possible sources for this terse path.\n'
				'Pick one full destination path:')
		n = 1
		for obj in _TERSE_MATCHES:
			stderr('%2d. %s' % (n, obj.dest_path))
			n += 1

		return None, {}

	# good, there was only one match
	return _TERSE_MATCHES[0], _POST_DICT


# EOB
