#! /usr/bin/env python
#
#	synctool_core.py	WJ109
#
#	The core holds the 'overlay' function
#

import synctool_config
from synctool_lib import verbose,stdout,stderr

import os
import sys
import string


GROUPS = None
ALL_GROUPS = None


# this is an enum; return values for dir_has_group_ext()
DIR_EXT_NO_GROUP=1
DIR_EXT_IS_GROUP=2
DIR_EXT_INVALID_GROUP=3


def file_has_group_ext(filename):
	'''filter function; see if the group extension applies'''

	arr = string.split(filename, '.')

	if len(arr) < 2:
		stderr('no group extension on %s, skipped' % filename)
		return 0

	group = arr[-1]
	if group == 'post':
		return 0

	if group[0] != '_':
		stderr('no underscored group extension on %s, skipped' % filename)
		return 0

	group = group[1:]
	if not group:
		stderr('no group extension on %s, skipped' % filename)
		return 0

	if group in GROUPS:				# got a file for one of our groups
		return 1

	if not group in ALL_GROUPS:
		stderr('unknown group on file %s, skipped' % filename)
		return 0

	verbose('%s is not one of my groups, skipped' % filename)
	return 0


def dir_has_group_ext(dirname):
	'''see if the group extension on a directory applies'''
	'''NB. this is not a filter() function'''

	arr = string.split(dirname, '.')

	if len(arr) < 2:
		return DIR_EXT_NO_GROUP

	group = arr[-1]

	if group[0] != '_':
		return DIR_EXT_NO_GROUP

	group = group[1:]
	if not group:
		return DIR_EXT_NO_GROUP

	if group in GROUPS:				# got a directory for one of our groups
		return DIR_EXT_IS_GROUP

	if not group in ALL_GROUPS:
		stderr('unknown group on directory %s/, skipped' % dirname)
		return DIR_EXT_INVALID_GROUP

	verbose('%s/ is not one of my groups, skipped' % dirname)
	return DIR_EXT_INVALID_GROUP


def filter_overrides(files):
	'''return a dict with {base filename:extension}'''

	stripped = {}

	for filename in files:
		arr = string.split(filename, '.')

		if len(arr) < 2:
			raise RuntimeError, 'bug! There should have been a good valid extension on this filename: %s' % filename

		stripped_name = string.join(arr[:-1], '.')
		ext = arr[-1]

		if ext[0] != '_':
			raise RuntimeError, 'bug! The extension should have started with an underscore: %s' % filename

		ext = ext[1:]

		if not stripped.has_key(stripped_name):
			stripped[stripped_name] = ext
		else:
# choose most important group
# the most important group is the one that is listed earlier in the GROUPS array, so it has a smaller index
			a = GROUPS.index(ext)
			b = GROUPS.index(stripped[stripped_name])
			if a < b:
				verbose('%s._%s overrides %s._%s' % (stripped_name, ext, stripped_name, stripped[stripped_name]))
				stripped[stripped_name] = ext

	return stripped


def overlay_callback(src_dir, dest_dir, filename, ext):
	'''compare files and run post-script if needed'''

	src = os.path.join(src_dir, '%s._%s' % (filename, ext))
	dest = os.path.join(dest_dir, filename)

	print 'TD cmp %s <-> %s' % (src, dest)

	post_script = os.path.join(src_dir, '%s.post' % filename)
	if os.path.exists(post_script):
		print 'TD on_update', post_script


def treewalk(src_dir, dest_dir, callback):
	'''walk the repository tree, either under overlay/, delete/, or tasks/'''
	'''and call the callback function for relevant files'''

	try:
		files = os.listdir(src_dir)
	except OSError, err:
		stderr('error: %s' % err)
		return

	all_dirs = []
	group_ext_dirs = []

	n = 0
	while n < len(files):
		filename = files[n]
		full_path = os.path.join(src_dir, filename)

# do not follow symlinked directories
		if os.path.islink(full_path):
			n = n + 1
			continue

		if os.path.isdir(full_path):

# it's a directory

# remove all dirs from files[] and put them in all_dirs[] or group_ext_dirs[]

			files.remove(filename)

# check ignore_dotdirs
			if filename[0] == '.' and synctool_config.IGNORE_DOTDIRS:
				continue

			if string.find(filename, '_') >= 0:				# first a quick check for group extension
				ret = dir_has_group_ext(filename)

				if ret == DIR_EXT_NO_GROUP:
					all_dirs.append(filename)

				elif ret == DIR_EXT_IS_GROUP:
					group_ext_dirs.append(filename)

				elif ret == DIR_EXT_INVALID_GROUP:
					pass

				else:
					raise RuntimeError, 'bug: unknown return value %d from dir_has_group_ext()' % ret
			else:
				all_dirs.append(filename)

			continue

# check ignore_dotfiles
		else:
			if filename[0] == '.' and synctool_config.IGNORE_DOTFILES:
				files.remove(filename)
				continue

		n = n + 1

# handle all files with group extensions that apply
	files = filter(file_has_group_ext, files)

	if len(files) > 0:
		stripped = filter_overrides(files)

		for filename in stripped.keys():
			if filename in synctool_config.IGNORE_FILES:
				continue

			callback(src_dir, dest_dir, filename, stripped[filename])

# now handle directories

# recursively visit all directories
	for dirname in all_dirs:
		if dirname in synctool_config.IGNORE_FILES:
			continue

		new_src_dir = os.path.join(src_dir, dirname)
		new_dest_dir = os.path.join(dest_dir, dirname)
		treewalk(new_src_dir,  new_dest_dir, callback)

# visit all directories with group extensions that apply
	if len(group_ext_dirs) > 0:
		stripped = filter_overrides(group_ext_dirs)

		for dirname in stripped.keys():
			if dirname in synctool_config.IGNORE_FILES:
				continue

			new_src_dir = os.path.join(src_dir, '%s._%s' % (dirname, stripped[dirname]))
			new_dest_dir = os.path.join(dest_dir, dirname)
			treewalk(new_src_dir, new_dest_dir, callback)


def overlay():
	'''run the overlay function'''

	base_path = os.path.join(synctool_config.MASTERDIR, 'overlay')
	if not os.path.isdir(base_path):
		verbose('skipping %s/, no such directory' % base_path)
		base_path = None

	treewalk(base_path, '/', overlay_callback)


def read_config():
	global GROUPS, ALL_GROUPS

	synctool_config.read_config()
	synctool_config.add_myhostname()

	if synctool_config.NODENAME == None:
		stderr('unable to determine my nodename, please check %s' % synctool_config.CONF_FILE)
		sys.exit(1)

#	if synctool_config.NODENAME in synctool_config.IGNORE_GROUPS:
#		stderr('%s: node %s is disabled in the config file' % (synctool_config.CONF_FILE, synctool_config.NODENAME))
#		sys.exit(1)

	synctool_config.remove_ignored_groups()
	GROUPS = synctool_config.get_my_groups()
	print 'TD GROUPS ==', GROUPS
	ALL_GROUPS = synctool_config.make_all_groups()


if __name__ == '__main__':
	read_config()
	overlay()


# EOB
