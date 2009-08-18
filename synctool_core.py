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

# ugly global, but it is much faster than passing it around as an argument
MASTER_LEN = 0


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


def overlay_callback(dir, filename, ext):
	'''compare files and run post-script if needed'''

	src = os.path.join(dir, '%s._%s' % (filename, ext))

# TODO dest = compose_path(src[MASTER_LEN:])
#
#	NB. een higher-performing oplossing kan zijn:
#
#	if string.find(dir, '_') >= 0:
#		dest = compose_path(src[MASTER_LEN:])
#	else:
#		dest = src[MASTER_LEN:]
#
#	een andere oplossing kan zijn om het dest full_path ten alle tijde al bij te houden
#

	dest = src[MASTER_LEN:]

	print 'TD cmp %s <-> %s' % (src, dest)

	post_script = os.path.join(dir, '%s.post' % filename)
	if os.path.exists(post_script):
		print 'TD on_update', post_script


def treewalk(callback, dir, files):
	'''walk the repository tree, either under overlay/, delete/, or tasks/'''
	'''and call the callback function for relevant files'''

	all_files = []

	for file in files:
		full_path = os.path.join(dir, file)
		if os.path.isdir(full_path):
# TODO filter dirs that are not my group
# first, remove all underscored dirs from files[] and put them in kept_dirs[]
			continue

		all_files.append(file)

# TODO stripped_dirs[] = filter_dir_overrides(kept_dirs)
# extend stripped_dirs[] to files[], as os.path.treewalk() uses this

	my_files = filter(file_has_group_ext, all_files)

	if not my_files:
		return

	stripped = filter_overrides(my_files)

	for filename in stripped.keys():
		callback(dir, filename, stripped[filename])


def overlay():
	'''run the overlay function'''

	global MASTER_LEN

	base_path = os.path.join(synctool_config.MASTERDIR, 'overlay')
	if not os.path.isdir(base_path):
		verbose('skipping %s, no such directory' % base_path)
		base_path = None

	MASTER_LEN = len(base_path)

	if base_path:
		os.path.walk(base_path, treewalk, overlay_callback)


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
