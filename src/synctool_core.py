#! /usr/bin/env python
#
#	synctool_core.py	WJ109
#
#	The core holds the 'treewalk' function and determines what file is for what group of a node
#	It also determines what .post script is available to run for the file
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2010
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_config
import synctool_lib

from synctool_lib import verbose,stdout,stderr

import os
import sys
import string


# treewalk() sets the current source dir (used for error reporting from filter() functions)
CURR_DIR = None

# dict of .post scripts in current dir
# the format is {dest filename: (.post script filename, .post script group extension)}
POST_SCRIPTS = {}

# this is an enum; return values for dir_has_group_ext()
DIR_EXT_NO_GROUP = 1
DIR_EXT_IS_GROUP = 2
DIR_EXT_INVALID_GROUP = 3

# used for find_synctree()
FIND_SYNCTREE = None
FOUND_SYNCTREE = None

# treewalk() may flag this when a file in the dir is updated
DIR_CHANGED = False


def add_post_script(base_filename, scriptname, group=None):
	'''set the .post script to execute for the dest filename with name 'base_filename'

	the global var POST_SCRIPTS is a dict that holds (fullpath script, group ext) indexed by base filename
	so you can do script_to_execute = POST_SCRIPTS[base_filename][0]
	The group is stored so that add_post_script() can determine which script is more important, when
	multiple .post scripts are possible
	'''

	global POST_SCRIPTS

	if not POST_SCRIPTS.has_key(base_filename):
		POST_SCRIPTS[base_filename] = (scriptname, group)
		return

	if not group:
# apparently, group-specific .post script is already set, so just return here
		return

	(script_b, group_b) = POST_SCRIPTS[base_filename]
	if not group_b:
		POST_SCRIPTS[base_filename] = (scriptname, group)
		return

# determine which group is more important
	a = synctool_config.MY_GROUPS.index(group)
	b = synctool_config.MY_GROUPS.index(group_b)
	if a < b:
		POST_SCRIPTS[base_filename] = (scriptname, group)


def file_has_group_ext(filename):
	'''filter function; see if the group extension applies'''

	if filename in synctool_config.IGNORE_FILES:
		return False

	arr = string.split(filename, '.')

	if len(arr) < 2:
		stderr('no group extension on $masterdir/%s/%s, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], filename))
		return False

	group = arr[-1]

# check for .post script; keep it for now
# .post scripts are processed in overlay_callback()
	if group == 'post':
		add_post_script(string.join(arr[:-1], '.'), filename, None)
		return False

	if group[0] != '_':
		stderr('no underscored group extension on $masterdir/%s/%s, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], filename))
		return False

	group = group[1:]
	if not group:
		stderr('no group extension on $masterdir/%s/%s, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], filename))
		return False

	if group in synctool_config.MY_GROUPS:			# got a file for one of our groups
		if len(arr) > 2 and arr[-2] == 'post':		# it's a group-specific .post script
			add_post_script(string.join(arr[:-2], '.'), filename, group)
			return False

		return True

	if not group in synctool_config.ALL_GROUPS:
		stderr('unknown group on file $masterdir/%s/%s, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], filename))
		return False

	verbose('$masterdir/%s/%s is not one of my groups, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], filename))
	return False


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

	if group in synctool_config.MY_GROUPS:				# got a directory for one of our groups
		return DIR_EXT_IS_GROUP

	if not group in synctool_config.ALL_GROUPS:
		stderr('unknown group on directory $masterdir/%s/%s/, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], dirname))
		return DIR_EXT_INVALID_GROUP

	verbose('$masterdir/%s/%s/ is not one of my groups, skipped' % (CURR_DIR[synctool_config.MASTER_LEN:], dirname))
	return DIR_EXT_INVALID_GROUP


def filter_overrides(files):
	'''return a dict with {base filename:extension}'''

	stripped = {}

	for filename in files:
		arr = string.split(filename, '.')

		if len(arr) < 2:
# no extension on this filename; this is accepted for directories
			if not stripped.has_key(filename):
				stripped[filename] = None

			continue

		stripped_name = string.join(arr[:-1], '.')
		ext = arr[-1]

		if ext[0] != '_':
# no group extension on this filename; this is accepted for directories
			if not stripped.has_key(filename):
				stripped[filename] = None

			continue

		ext = ext[1:]

		if not stripped.has_key(stripped_name):
			stripped[stripped_name] = ext
		else:
# choose most important group
# the most important group is the one that is listed earlier in the MY_GROUPS array, so it has a smaller index
			a = synctool_config.MY_GROUPS.index(ext)

			ext2 = stripped[stripped_name]
			if not ext2:
				b = a + 1
				dest = stripped_name
			else:
				b = synctool_config.MY_GROUPS.index(ext2)
				dest = '%s._%s' % (stripped_name, ext2)

			if a < b:
				if not ext2:
					verbose('$masterdir/%s/%s._%s complements %s/' % (CURR_DIR[synctool_config.MASTER_LEN:], stripped_name, ext, dest))
				else:
					verbose('$masterdir/%s/%s._%s overrides %s' % (CURR_DIR[synctool_config.MASTER_LEN:], stripped_name, ext, dest))

				stripped[stripped_name] = ext
			else:
				verbose('$masterdir/%s/%s overrides %s._%s' % (CURR_DIR[synctool_config.MASTER_LEN:], dest, stripped_name, ext))

	return stripped


def treewalk(src_dir, dest_dir, callback, dir_updated=None, visit_subdirs=True):
	'''walk the repository tree, either under overlay/, delete/, or tasks/
	and call the callback function for relevant files
	* if callback is None, no callback function is called
	* dir_updated is a callback function for directories that have updates in them
	* if visit_subdirs is False, no treewalk is performed; only the src_dir is scanned
	'''

	global CURR_DIR, POST_SCRIPTS, DIR_CHANGED

	CURR_DIR = src_dir				# stupid global for filter() functions
	POST_SCRIPTS = {}
	DIR_CHANGED = False

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
# this also adds .post scripts to the dict POST_SCRIPTS
# and it filters any files/dirs that are ignored by name
	files = filter(file_has_group_ext, files)

	if len(files) > 0 and callback != None:
		stripped = filter_overrides(files)

		for filename in stripped.keys():
			if filename in synctool_config.IGNORE_FILES:
				continue

			if not callback(src_dir, dest_dir, filename, stripped[filename]):
				return

# now handle directories

	if not visit_subdirs:
		return

# make a local copy of the POST_SCRIPTS dict
# it's quite messy to use a global var in a recursive function, but it's also being used by a filter() function, so hey ...
	copy_post_scripts = POST_SCRIPTS.copy()
	copy_dir_changed = DIR_CHANGED

# recursively visit all directories
	for dirname in all_dirs:
		if dirname in synctool_config.IGNORE_FILES:
			continue

		if not callback(src_dir, dest_dir, dirname, None):
			return

		new_src_dir = os.path.join(src_dir, dirname)
		new_dest_dir = os.path.join(dest_dir, dirname)
		treewalk(new_src_dir,  new_dest_dir, callback, dir_updated)

# after recursing the treewalk, reset pointer POST_SCRIPTS to the current level
		POST_SCRIPTS = copy_post_scripts

# the callback may set a flag that this directory triggered an update
		if DIR_CHANGED and dir_updated != None:
			dir_updated(new_src_dir, new_dest_dir)
			DIR_CHANGED = copy_dir_changed

# visit all directories with group extensions that apply
	if len(group_ext_dirs) > 0:
		stripped = filter_overrides(group_ext_dirs)

		for dirname in stripped.keys():
			if dirname in synctool_config.IGNORE_FILES:
				continue

			if not callback(src_dir, dest_dir, dirname, stripped[dirname]):
				return

			new_src_dir = os.path.join(src_dir, '%s._%s' % (dirname, stripped[dirname]))
			new_dest_dir = os.path.join(dest_dir, dirname)
			treewalk(new_src_dir, new_dest_dir, callback, dir_updated)

# after recursing the treewalk, reset pointer POST_SCRIPTS to the current level
			POST_SCRIPTS = copy_post_scripts

# the callback may set a flag that this directory triggered an update
			if DIR_CHANGED and dir_updated != None:
				dir_updated(new_src_dir, new_dest_dir)
				DIR_CHANGED = copy_dir_changed


def find_callback(src_dir, dest_dir, filename, ext):
	'''callback function for find_synctree()'''

	global FOUND_SYNCTREE

	dest = os.path.join(dest_dir, filename)

	if dest == FIND_SYNCTREE:
		if not ext:				# directories have no extension
			FOUND_SYNCTREE = os.path.join(src_dir, filename)
		else:
			FOUND_SYNCTREE = os.path.join(src_dir, '%s._%s' % (filename, ext))
		return False			# terminate the treewalk()

	return True


def find_synctree(subdir, pathname):
	'''find the source of a full destination path'''

	global FIND_SYNCTREE, FOUND_SYNCTREE

	base_path = os.path.join(synctool_config.MASTERDIR, subdir)
	if not os.path.isdir(base_path):
		stderr('error: $masterdir/%s/ not found' % subdir)
		return

	FIND_SYNCTREE = pathname
	FOUND_SYNCTREE = None

	treewalk(base_path, '/', find_callback)

	return FOUND_SYNCTREE


if __name__ == '__main__':
# for testing purposes only!
	synctool_config.read_config()

	synctool_lib.VERBOSE = True

	overlay_files()

	print
	find_synctree('overlay', '/etc/ntp.conf')
	find_synctree('tasks', '/scr1')


# EOB
