#
#	synctool_overlay.py	WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool.overlay maps the repository onto the root directory.

	Consider this tree:
	 $overlay/all/etc/ntp.conf._n1
     $overlay/all/etc._n1/ntp.conf._all
	 $overlay/all/etc._n1/ntp.conf._n1
	 $overlay/n1/etc/ntp.conf._all
	 $overlay/n1/etc/ntp.conf._n1
	 $overlay/n1/etc._n1/ntp.conf._all
	 $overlay/n1/etc._n1/ntp.conf._n1

	[Ideally] synctool selects the final entry. It accomplishes this with
	the following procedure:
	 1. foreach direntry split the extension; get the 'importance'
	 2. sort by importance
	 3. first come, first served; first encountered entry is best choice
	 4. register destination as 'already handled' (duplicate)
	 5. if already handled, skip this entry

	.post scripts are sorted in first so that a dictionary can be built
	before it needs to be consulted. This dictionary only contains .post
	scripts that are in the current directory. Additionally, if the current
	directory itself has a .post script (which is in the parent directory),
	then the .post script is passed in the dict as well.
'''

import os
import sys
import fnmatch
import subprocess

import synctool.lib
from synctool.lib import verbose, stderr, unix_out, terse
import synctool.object
from synctool.object import SyncObject
import synctool.param

# last index of MY_GROUPS
GROUP_ALL = 1000

# const enum object types
OV_REG = 0
OV_POST = 1
OV_TEMPLATE = 2
OV_TEMPLATE_POST = 3
OV_NO_EXT = 4

# used with find() and _find_callback() function
_SEARCH = None
_FOUND = None
_POST_DICT = None

# used with _find_terse() and _find_terse_callback() function
_TERSE_ENDING = None
_TERSE_LEN = 0
_TERSE_MATCHES = None


def generate_template(obj):
	'''run template .post script, generating a new file
	The script will run in the source dir (overlay tree) and
	it will run even in dry-run mode
	Returns: SyncObject of the new file or None on error'''

	verbose('generating template %s' % obj.print_src())

	src_dir = os.path.dirname(obj.src_path)
	newname = os.path.basename(obj.dest_path)
	template = newname + '._template'
	# add most important extension
	newname += '._' + synctool.param.NODENAME

	# chdir to source directory
	verbose('  os.chdir(%s)' % src_dir)
	unix_out('cd %s' % src_dir)

	cwd = os.getcwd()

	try:
		os.chdir(src_dir)
	except OSError, reason:
		stderr('error changing directory to %s: %s' % (src_dir, reason))
		return None

	# temporarily restore original umask
	# so the script runs with the umask set by the sysadmin
	os.umask(synctool.param.ORIG_UMASK)

	# run the script
	# pass template and newname as "$1" and "$2"
	cmd_arr = [obj.src_path, template, newname]
	verbose('  os.system(%s, %s, %s)' % (synctool.lib.prettypath(cmd_arr[0]),
				cmd_arr[1], cmd_arr[2]))
	unix_out('# run command %s' % os.path.basename(cmd_arr[0]))
	unix_out('%s "%s" "%s"' % (cmd_arr[0], cmd_arr[1], cmd_arr[2]))

	sys.stdout.flush()
	sys.stderr.flush()

	err = False
	try:
		subprocess.call(cmd_arr, shell=False)
	except OSError, reason:
		stderr("failed to run shell command '%s' : %s" %
				(synctool.lib.prettypath(cmd_arr[0]), reason))
		err = True

	sys.stdout.flush()
	sys.stderr.flush()

	if not os.path.exists(newname):
		verbose('warning: expected output %s was not generated' % newname)
		err = True
	else:
		verbose('found generated output %s' % newname)

	os.umask(077)

	# chdir back to original location
	# chdir to source directory
	verbose('  os.chdir(%s)' % cwd)
	unix_out('cd %s' % cwd)
	try:
		os.chdir(cwd)
	except OSError, reason:
		stderr('error changing directory to %s: %s' % (cwd, reason))
		return None

	if err:
		return None

	# this will return the new file as an object
	obj, importance = _split_extension(newname, src_dir)
	return obj


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
	Returns tuple: SyncObject, importance

	Prereq: GROUP_ALL must be set to len(MY_GROUPS)-1'''

	(name, ext) = os.path.splitext(filename)
	if not ext:
		return SyncObject(filename, name, OV_NO_EXT), GROUP_ALL

	if ext == '.post':
		(name2, ext) = os.path.splitext(name)
		if ext == '._template':
			# it's a generic template generator
			return (SyncObject(filename, name2, OV_TEMPLATE_POST), GROUP_ALL)

		# it's a generic .post script
		return SyncObject(filename, name, OV_POST), GROUP_ALL

	if ext[:2] != '._':
		return SyncObject(filename, filename, OV_NO_EXT), GROUP_ALL

	ext = ext[2:]
	if not ext:
		return SyncObject(filename, filename, OV_NO_EXT), GROUP_ALL

	if ext == 'template':
		return SyncObject(filename, name, OV_TEMPLATE), GROUP_ALL

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
		(name3, ext) = os.path.splitext(name)
		if ext == '._template':
			# it's a group-specific template generator
			return (SyncObject(filename, name3, OV_TEMPLATE_POST), importance)

		# register group-specific .post script
		return SyncObject(filename, name2, OV_POST), importance

	elif ext == '._template':
		stderr('warning: template %s can not have a group extension' %
				synctool.lib.prettypath(os.path.join(src_dir, filename)))
		return None, -1

	return SyncObject(filename, name), importance


def _sort_by_importance_post_first(item1, item2):
	'''sort by importance, but always put .post scripts first'''

	# after the .post scripts come ._template.post scripts
	# then come regular files
	# This order is important

	obj1, importance1 = item1
	obj2, importance2 = item2

	if obj1.ov_type == OV_POST:
		if obj2.ov_type == OV_POST:
			return cmp(importance1, importance2)

		return -1

	if obj2.ov_type == OV_POST:
		return 1

	if obj1.ov_type == OV_TEMPLATE_POST:
		if obj2.ov_type == OV_TEMPLATE_POST:
			return cmp(importance1, importance2)

		return -1

	if obj2.ov_type == OV_TEMPLATE_POST:
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

		if obj.ov_type == OV_TEMPLATE:
			# completely ignore templates
			verbose('skimming over template %s' % obj.print_src())
			continue

		arr.append((obj, importance))

	# sort with .post scripts first
	# this ensures that post_dict will have the required script when needed
	arr.sort(_sort_by_importance_post_first)

	dir_changed = False

	for obj, importance in arr:
		obj.make(src_dir, dest_dir)

		if obj.ov_type == OV_POST:
			# register the .post script and continue
			if post_dict.has_key(obj.dest_path):
				continue

			post_dict[obj.dest_path] = obj.src_path
			continue

		if obj.ov_type == OV_TEMPLATE_POST:
			# it's a template generator. So generate
			obj = generate_template(obj)
			if not obj:
				# failed
				continue

			# we generated a new file, represented by obj
			# so continue with the new obj
			obj.make(src_dir, dest_dir)

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
			ok, changed = callback(obj, post_dict, dir_changed)
			if not ok:
				# quick exit
				return False

			continue

		if synctool.param.IGNORE_DOTFILES:
			name = os.path.basename(obj.src_path)
			if name[0] == '.':
				verbose('ignoring dotfile %s' % obj.print_src())
				continue

		if synctool.param.REQUIRE_EXTENSION and obj.ov_type == OV_NO_EXT:
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

		ok, updated = callback(obj, post_dict)
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
