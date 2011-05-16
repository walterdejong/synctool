#! /usr/bin/env python
#
#	synctool	WJ103
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_config
import synctool_lib
import synctool_overlay

from synctool_lib import verbose,stdout,stderr,unix_out

import sys
import os
import os.path
import string
import socket
import getopt
import stat
import errno
import shutil
import pwd
import grp
import time
import shlex

try:
	import hashlib
	use_hashlib = True
except ImportError:
	import md5
	use_hashlib = False

try:
	import subprocess
	use_subprocess = True
except ImportError:
	use_subprocess = False

# get_options() returns these action codes
ACTION_DEFAULT = 0
ACTION_DIFF = 1
ACTION_RUN_TASKS = 3
ACTION_REFERENCE = 4
ACTION_VERSION = 5

# blocksize for doing I/O while checksumming files
BLOCKSIZE = 16 * 1024

SINGLE_FILES = []

# list of changed directories
# This is for running .post scripts on changed directories
# every element is a tuple: (src_path, dest_path)
DIR_CHANGED = []


def ascii_uid(uid):
	'''get the name for this uid'''

	try:
		entry = pwd.getpwuid(uid)
		return entry[0]

	except KeyError:
		pass

	return "%d" % uid


def ascii_gid(gid):
	'''get the name for this gid'''

	try:
		entry = grp.getgrgid(gid)
		return entry[0]

	except KeyError:
		pass

	return "%d" % gid


def checksum_files(file1, file2):
	'''do a quick checksum of 2 files'''

	err = None
	reason = None
	try:
		f1 = open(file1, 'r')
	except IOError(err, reason):
		stderr('error: failed to open %s : %s' % (file1, reason))
		raise

	try:
		f2 = open(file2, 'r')
	except IOError(err, reason):
		stderr('error: failed to open %s : %s' % (file2, reason))
		raise

	if use_hashlib:
		sum1 = hashlib.md5()
		sum2 = hashlib.md5()
	else:
		sum1 = md5.new()
		sum2 = md5.new()

	len1 = len2 = 0
	ended = False
	while len1 == len2 and sum1.digest() == sum2.digest() and not ended:
		data1 = f1.read(BLOCKSIZE)
		if not data1:
			ended = True
		else:
			len1 = len1 + len(data1)
			sum1.update(data1)

		data2 = f2.read(BLOCKSIZE)
		if not data2:
			ended = True
		else:
			len2 = len2 + len(data2)
			sum2.update(data2)

		if sum1.digest() != sum2.digest():
			# checksum mismatch; early exit
			break

	f1.close()
	f2.close()
	return sum1.digest(), sum2.digest()


def stat_islink(stat_struct):
	'''returns whether a file is a symbolic link or not'''
	'''this function is needed because os.path.islink() returns False for dead symlinks, which is not what I want ...'''

	if not stat_struct:
		return 0

	return stat.S_ISLNK(stat_struct[stat.ST_MODE])


def stat_isdir(stat_struct):
	'''returns whether a file is a directory or not'''
	'''this function is needed because os.path.isdir() returns True for symlinks to directories ...'''

	if not stat_struct:
		return 0

	return stat.S_ISDIR(stat_struct[stat.ST_MODE])


def stat_isfile(stat_struct):
	'''returns whether a file is a regular file or not'''
	'''this function is needed because os.path.isfile() returns True for symlinks to files ...'''

	if not stat_struct:
		return 0

	return stat.S_ISREG(stat_struct[stat.ST_MODE])


def stat_exists(stat_struct):
	'''returns if a path exists'''

	if not stat_struct:
		return 0

	return 1


def stat_path(path):
	'''lstat() a path'''

	try:
		stat_struct = os.lstat(path)
	except OSError, (err, reason):
		if err != errno.ENOENT:
			stderr("lstat('%s') failed: %s" % (path, reason))
			return 0

		stat_struct = None

	return stat_struct


def path_islink(path):
	return stat_islink(stat_path(path))


def path_isdir(path):
	return stat_isdir(stat_path(path))


def path_isfile(path):
	return stat_isfile(stat_path(path))


def path_exists(path):
	return stat_exists(stat_path(path))


def path_isexec(path):
	'''returns whether a file is executable or not'''
	'''Mind that this function follows symlinks'''

	try:
		stat_struct = os.stat(path)
	except OSError, (err, reason):
		stderr("stat('%s') failed: %s" % (path, reason))
		return False

	if stat_struct[stat.ST_MODE] & 0111:
		return True

	return False


def compare_files(src_path, dest_path):
	'''see what the differences are between src and dest, and fix it if not a dry run

	src_path is the file in the synctool/overlay tree
	dest_path is the file in the system

	done is a local boolean saying if a path has been checked
	need_update is a local boolean saying if a path needs to be updated

	return value is 0 when file is not changed, 1 when file is updated

--
	The structure of this long function is as follows;

		stat(src)		this stat is 'sacred' and dest should be set accordingly
		stat(dest)

		if src is symlink:
			check if dest exists
			check if dest is symlink
			check if dest is dir
			treat dest as file
			fix if needed

		if src is directory:
			check if dest exists
			check if dest is symlink
			check if dest is dir
			treat dest as file
			fix if needed

		if src is file:
			check if dest exists
			check if dest is symlink
			check if dest is dir
			treat dest as file
			check filesize
			do md5 checksum
			fix if needed

		don't know what type src is

		check ownership
		check permissions
		return 0
'''

	src_stat = stat_path(src_path)
	if not src_stat:
		return False

	dest_stat = stat_path(dest_path)
#	if not dest_path:
#		pass					# destination does not exist

	done = False
	need_update = False

	#
	# if source is a symbolic link ...
	#
	if not done and stat_islink(src_stat):
		need_update = False
		try:
			src_link = os.readlink(src_path)
		except OSError, reason:
			stderr('failed to readlink %s : %s' % (src_path, reason))
			return False

		if not stat_exists(dest_stat):
			done = True
			stdout('symbolic link %s does not exist' % dest_path)
			unix_out('# create symbolic link %s' % dest_path)
			need_update = True

		if stat_islink(dest_stat):
			done = True
			try:
				dest_link = os.readlink(dest_path)
			except OSError, reason:
				stderr('failed to readlink %s : %s (but ignoring this error)' % (src_path, reason))
				dest_link = None

			if src_link != dest_link:
				stdout('%s should point to %s, but points to %s' % (dest_path, src_link, dest_link))
				unix_out('# relink symbolic link %s' % dest_path)
				delete_file(dest_path)
				need_update = True

			if (dest_stat[stat.ST_MODE] & 07777) != synctool_param.SYMLINK_MODE:
				stdout('%s should have mode %04o (symlink), but has %04o' % (dest_path, synctool_param.SYMLINK_MODE, dest_stat[stat.ST_MODE] & 07777))
				unix_out('# fix permissions of symbolic link %s' % dest_path)
				need_update = True

		elif stat_isdir(dest_stat):
			done = True
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			move_dir(dest_path)
			need_update = True

		#
		# treat as file ...
		#
		if not done:
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			delete_file(dest_path)
			need_update = True

		#
		# (re)create the symbolic link
		#
		if need_update:
			symlink_file(src_link, dest_path)
			unix_out('')
			return True

		done = True

	#
	# if the source is a directory ...
	#
	if not done and stat_isdir(src_stat):
		if not stat_exists(dest_stat):
			done = True
			stdout('%s/ does not exist' % dest_path)
			unix_out('# make directory %s' % dest_path)
			need_update = True

		if stat_islink(dest_stat):
			done = True
			stdout('%s is a symbolic link, but should be a directory' % dest_path)
			unix_out('# target should be a directory instead of a symbolic link')
			delete_file(dest_path)
			need_update = True

		#
		# treat as a regular file
		#
		if not done and not stat_isdir(dest_stat):
			done = True
			stdout('%s should be a directory' % dest_path)
			unix_out('# target should be a directory')
			delete_file(dest_path)
			need_update = True

		#
		# make the directory
		#
		if need_update:
			make_dir(dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])
			unix_out('')
			return True

		done = True

	#
	# if source is a file ...
	#
	if not done and stat_isfile(src_stat):
		if not stat_exists(dest_stat):
			done = True
			stdout('%s does not exist' % dest_path)
			unix_out('# copy file %s' % dest_path)
			need_update = True

		if stat_islink(dest_stat):
			done = True
			stdout('%s is a symbolic link, but should not be' % dest_path)
			unix_out('# target should be a file instead of a symbolic link')
			delete_file(dest_path)
			need_update = True

		if stat_isdir(dest_stat):
			done = True
			stdout('%s is a directory, but should not be' % dest_path)
			unix_out('# target should be a file instead of a directory')
			move_dir(dest_path)
			need_update = True

		#
		# check file size
		#
		if stat_isfile(dest_stat):
			if src_stat[stat.ST_SIZE] != dest_stat[stat.ST_SIZE]:
				done = True
				if synctool_lib.DRY_RUN:
					stdout('%s mismatch (file size)' % dest_path)
				else:
					stdout('%s updated (file size mismatch)' % dest_path)
				unix_out('# updating file %s' % dest_path)
				need_update = True
			else:
				#
				# check file contents (SHA1 or MD5 checksum)
				#
				try:
					src_sum, dest_sum = checksum_files(src_path, dest_path)
				except IOError, (err, reason):
#	error was already printed				stderr('error: %s' % reason)
					return False

				if src_sum != dest_sum:
					done = True
					if synctool_lib.DRY_RUN:
#						stdout('%s mismatch (SHA1 checksum)' % dest_path)
						stdout('%s mismatch (MD5 checksum)' % dest_path)
					else:
#						stdout('%s updated (SHA1 mismatch)' % dest_path)
						stdout('%s updated (MD5 mismatch)' % dest_path)

					unix_out('# updating file %s' % dest_path)
					need_update = True

		elif not done:
			done = True
			stdout('%s should be a regular file' % dest_path)
			unix_out('# target should be a regular file')
			need_update = True

		if need_update:
			copy_file(src_path, dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])
			unix_out('')
			return True

		done = True

	elif not done:
		#
		# source is not a symbolic link, not a directory, and not a regular file
		#
		stderr("be advised: don't know how to handle %s" % src_path)

		if not stat_exists(dest_stat):
			return False

		if stat_islink(dest_stat):
			stdout('%s should not be a symbolic link' % dest_path)
		else:
			if stat_isdir(dest_stat):
				stdout('%s should not be a directory' % dest_path)
			else:
				if stat_isfile(dest_stat):
					stdout('%s should not be a regular file' % dest_path)
				else:
					stderr("don't know how to handle %s" % dest_path)

	#
	# check mode and owner/group of files and/or directories
	#
	# os.chmod() and os.chown() don't work well with symbolic links as they work
	# on the destination rather than the symlink itself
	# python lacks an os.lchmod() and os.lchown() as they are not portable
	# anyway, symbolic links have been dealt with already ...
	#
	if stat_exists(dest_stat) and not stat_islink(dest_stat):
		if src_stat[stat.ST_UID] != dest_stat[stat.ST_UID] or src_stat[stat.ST_GID] != dest_stat[stat.ST_GID]:
			stdout('%s should have owner %s.%s (%d.%d), but has %s.%s (%d.%d)' % (dest_path, ascii_uid(src_stat[stat.ST_UID]), ascii_gid(src_stat[stat.ST_GID]), src_stat[stat.ST_UID], src_stat[stat.ST_GID], ascii_uid(dest_stat[stat.ST_UID]), ascii_gid(dest_stat[stat.ST_GID]), dest_stat[stat.ST_UID], dest_stat[stat.ST_GID]))
			unix_out('# changing ownership on %s' % dest_path)

			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])

			unix_out('')
			need_update = True

		if (src_stat[stat.ST_MODE] & 07777) != (dest_stat[stat.ST_MODE] & 07777):
			stdout('%s should have mode %04o, but has %04o' % (dest_path, src_stat[stat.ST_MODE] & 07777, dest_stat[stat.ST_MODE] & 07777))
			unix_out('# changing permissions on %s' % dest_path)

			set_permissions(dest_path, src_stat[stat.ST_MODE])

			unix_out('')
			need_update = True

#		if src_stat[stat.ST_MTIME] != dest_stat[stat.ST_MTIME]:
#			stdout('%s should have mtime %d, but has %d' % (dest_path, src_stat[stat.ST_MTIME], dest_stat[stat.ST_MTIME]))
#		if src_stat[stat.ST_CTIME] != dest_stat[stat.ST_CTIME]:
#			stdout('%s should have ctime %d, but has %d' % (dest_path, src_stat[stat.ST_CTIME], dest_stat[stat.ST_CTIME]))

	erase_saved(dest_path)
	return need_update


def copy_file(src, dest):
	if path_isfile(dest):
		unix_out('cp %s %s.saved' % (dest, dest))
	
	unix_out('umask 077')
	unix_out('cp %s %s' % (src, dest))
	
	if not synctool_lib.DRY_RUN:
		old_umask = os.umask(077)
		
		if not synctool_param.ERASE_SAVED:
			if path_isfile(dest):
				verbose('  saving %s as %s.saved' % (dest, dest))
				try:
					shutil.copy2(dest, '%s.saved' % dest)
				except:
					stderr('failed to save %s as %s.saved' % (dest, dest))
		
		verbose('  cp %s %s' % (src, dest))
		try:
			shutil.copy2(src, dest)			# copy file and stats
		except:
			stderr('failed to copy %s to %s' % (src, dest))
		
		os.umask(old_umask)
	else:
		if path_isfile(dest) and not synctool_param.ERASE_SAVED:
			verbose('  saving %s as %s.saved' % (dest, dest))
		
		verbose('  cp %s %s             # dry run, update not performed' % (src, dest))


def symlink_file(oldpath, newpath):
	if path_exists(newpath):
		unix_out('mv %s %s.saved' % (newpath, newpath))

	#
	# actually, if we want the ownership of the symlink to be correct,
	# we should do setuid() here
	# matching ownerships of symbolic links is not yet implemented
	#

	unix_out('umask 022')
	unix_out('ln -s %s %s' % (oldpath, newpath))

	if not synctool_lib.DRY_RUN:
		if path_exists(newpath):
			verbose('saving %s as %s.saved' % (newpath, newpath))
			try:
				os.rename(newpath, '%s.saved' % newpath)
			except OSError, reason:
				stderr('failed to save %s as %s.saved : %s' % (newpath, newpath, reason))

		old_umask = os.umask(022)		# we want symlinks to have mode 0755, but linux makes them 0777 anyway

		verbose('  os.symlink(%s, %s)' % (oldpath, newpath))
		try:
			os.symlink(oldpath, newpath)
		except OSError, reason:
			stderr('failed to create symlink %s -> %s : %s' % (newpath, oldpath, reason))

		os.umask(old_umask)

	else:
		verbose('  os.symlink(%s, %s)             # dry run, update not performed' % (oldpath, newpath))


def set_permissions(file, mode):
	unix_out('chmod 0%o %s' % (mode & 07777, file))

	if not synctool_lib.DRY_RUN:
		verbose('  os.chmod(%s, %04o)' % (file, mode & 07777))
		try:
			os.chmod(file, mode & 07777)
		except OSError, reason:
			stderr('failed to chmod %04o %s : %s' % (mode & 07777, file, reason))
	else:
		verbose('  os.chmod(%s, %04o)             # dry run, update not performed' % (file, mode & 07777))


def set_owner(file, uid, gid):
	unix_out('chown %s.%s %s' % (ascii_uid(uid), ascii_gid(gid), file))

	if not synctool_lib.DRY_RUN:
		verbose('  os.chown(%s, %d, %d)' % (file, uid, gid))
		try:
			os.chown(file, uid, gid)
		except OSError, reason:
			stderr('failed to chown %s.%s %s : %s' % (ascii_uid(uid), ascii_gid(gid), file, reason))
	else:
		verbose('  os.chown(%s, %d, %d)             # dry run, update not performed' % (file, uid, gid))


def delete_file(file):
	if not synctool_lib.DRY_RUN:
		if not synctool_param.ERASE_SAVED:
			unix_out('mv %s %s.saved' % (file, file))

			verbose('moving %s to %s.saved' % (file, file))
			try:
				os.rename(file, '%s.saved' % file)
			except OSError, reason:
				stderr('failed to move file to %s.saved : %s' % (file, reason))
		else:
			unix_out('rm %s' % file)
			verbose('  os.unlink(%s)' % file)
			try:
				os.unlink(file)
			except OSError, reason:
				stderr('failed to delete %s : %s' % (file, reason))
	else:
		if not synctool_param.ERASE_SAVED:
			verbose('moving %s to %s.saved             # dry run, update not performed' % (file, file))
		else:
			verbose('deleting %s    # dry run, delete not performed' % file)


def hard_delete_file(file):
	unix_out('rm -f %s' % file)

	if not synctool_lib.DRY_RUN:
		verbose('  os.unlink(%s)' % file)
		try:
			os.unlink(file)
		except OSError, reason:
			stderr('failed to delete %s : %s' % (file, reason))
	else:
		verbose('deleting %s             # dry run, update not performed' % file)


def erase_saved(dst):
	if synctool_param.ERASE_SAVED and path_isfile('%s.saved' % dst):
		unix_out('rm %s.saved' % dst)
		
		if synctool_lib.DRY_RUN:
			verbose('backup copy %s.saved not erased    # dry run, update not performed' % dst)
		else:
			verbose('erasing backup copy %s.saved' % dst)
			try:
				os.unlink('%s.saved' % dst)
			except OSError, reason:
				stderr('failed to delete %s : %s' % (file, reason))


def make_dir(path):
	unix_out('umask 077')
	unix_out('mkdir %s' % path)

	if not synctool_lib.DRY_RUN:
		old_umask = os.umask(077)

		verbose('  os.mkdir(%s)' % path)
		try:
			os.mkdir(path)
		except OSError, reason:
			stderr('failed to make directory %s : %s' % (path, reason))

		os.umask(old_umask)
	else:
		verbose('  os.mkdir(%s)             # dry run, update not performed' % path)


def move_dir(dir):
	unix_out('mv %s %s.saved' % (dir, dir))

	if not synctool_lib.DRY_RUN:
		verbose('moving %s to %s.saved' % (dir, dir))
		#
		#	directories are kept no matter what config.ERASE_SAVED says
		#
		try:
			os.rename(dir, '%s.saved' % dir)
		except OSError, reason:
			stderr('failed to move directory to %s.saved : %s' % (dir, reason))

	else:
		verbose('moving %s to %s.saved             # dry run, update not performed' % (dir, dir))


def run_command(cmd):
	'''run a shell command'''
	
	if synctool_lib.DRY_RUN:
		not_str = 'not '
	else:
		not_str = ''
	
	if cmd[0] != '/':
		# if relative path, use scriptdir
		cmd = synctool_param.SCRIPT_DIR + '/' + cmd
	
	# a command can have arguments
	arr = shlex.split(cmd)
	cmdfile = arr[0]
	
	if not path_exists(cmdfile):
		stderr('error: command %s not found' % synctool_lib.prettypath(cmdfile))
		return
	
	if not path_isexec(cmdfile):
		stderr("warning: file '%s' is not executable" % synctool_lib.prettypath(cmdfile))
		return
	
	if not synctool_lib.QUIET:
		stdout('%srunning command %s' % (not_str, synctool_lib.prettypath(cmd)))
	
	unix_out('# run command %s' % cmdfile)
	unix_out(cmd)
	
	if not synctool_lib.DRY_RUN:
		verbose('  os.system("%s")' % synctool_lib.prettypath(cmd))
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if use_subprocess:
			try:
				subprocess.Popen(cmd, shell=True)
			except:
				stderr("failed to run shell command '%s' : %s" % (synctool_lib.prettypath(cmd), reason))
		else:
			try:
				os.system(cmd)
			except OSError, reason:
				stderr("failed to run shell command '%s' : %s" % (synctool_lib.prettypath(cmd), reason))
		
		sys.stdout.flush()
		sys.stderr.flush()
	else:
		verbose('  os.system("%s")             # dry run, action not performed' % synctool_lib.prettypath(cmd))


def run_command_in_dir(dest_dir, cmd):
	'''change directory to dest_dir, and run the shell command'''
	
	verbose('  os.chdir(%s)' % dest_dir)
	unix_out('cd %s' % dest_dir)
	
	cwd = os.getcwd()
	
	# if dry run, the target directory may not exist yet (mkdir has not been called for real, for a dry run)
	if synctool_lib.DRY_RUN:
		run_command(cmd)
		
		verbose('  os.chdir(%s)' % cwd)
		unix_out('cd %s' % cwd)
		unix_out('')
		return
	
	try:
		os.chdir(dest_dir)
	except OSError, reason:
		stderr('error changing directory to %s: %s' % (dest_dir, reason))
	else:
		run_command(cmd)
		
		verbose('  os.chdir(%s)' % cwd)
		unix_out('cd %s' % cwd)
		unix_out('')
		
		try:
			os.chdir(cwd)
		except OSError, reason:
			stderr('error changing directory to %s: %s' % (cwd, reason))


def run_post(src, dest):
	'''run any on_update or .post script commands for destination path'''
	
	global DIR_CHANGED
	
	if path_isdir(dest):
		# directories will be handled later, so save this pair
		pair = (src, dest)
		DIR_CHANGED.append(pair)
		return
	
	dest_dir = os.path.dirname(dest)
	
	# file has changed, run on_update command
	if synctool_param.ON_UPDATE.has_key(dest):
		run_command_in_dir(dest_dir, synctool_param.ON_UPDATE[dest])
	
	# file has changed, run appropriate .post script
	postscript = synctool_overlay.postscript_for_path(src, dest)
	if postscript:
		run_command_in_dir(dest_dir, postscript)
	
	# content of directory was changed, so save this pair
	pair = (os.path.dirname(src), dest_dir)
	if not pair in DIR_CHANGED:
		DIR_CHANGED.append(pair)


def run_post_on_directory(src, dest):
	'''run .post script for a changed directory'''
	
	# Note that the script is executed with the changed dir as current working dir
	
	if synctool_param.ON_UPDATE.has_key(dest):
		run_command_in_dir(dest, synctool_param.ON_UPDATE[dest])
	
	# run appropriate .post script
	postscript = synctool_overlay.postscript_for_path(src, dest)
	if postscript:
		run_command_in_dir(dest, postscript)


def sort_directory_pair(a, b):
	'''sort function for directory pairs
	a and b are directory pair tuples: (src, dest)
	sort the deepest destination directories first'''
	
	n = -cmp(len(a[1]), len(b[1]))
	if not n:
		return cmp(a[1], b[1])
	
	return n


def run_post_on_directories():
	'''run pending .post scripts on directories that were changed'''
	
	global DIR_CHANGED
	
	# sort by dest_dir with deepest dirs first
	DIR_CHANGED.sort(sort_directory_pair)
	
	# run .post scripts on every dir
	# Note how you can have multiple sources for the same destination,
	# and this triggers all .post scripts for those sources
	for (src, dest) in DIR_CHANGED:
		run_post_on_directory(src, dest)


def overlay_callback(src, dest):
	'''compare files and run post-script if needed'''
	
	verbose('checking %s' % synctool_lib.prettypath(src))
	
	if compare_files(src, dest):
		run_post(src, dest)


def overlay_files():
	'''run the overlay function'''
	
	synctool_overlay.visit(synctool_overlay.OV_OVERLAY, overlay_callback)
	run_post_on_directories()


def delete_callback(src, dest):
	'''delete files'''
	
	if path_isdir(dest):			# do not delete directories
		return
	
	if path_exists(dest):
		if synctool_lib.DRY_RUN:
			not_str = 'not '
		else:
			not_str = ''
		
		stdout('%sdeleting %s : %s' % (not_str, synctool_lib.prettypath(src), dest))
		hard_delete_file(dest)
		run_post(src, dest)


def delete_files():
	synctool_overlay.visit(synctool_overlay.OV_DELETE, delete_callback)
	run_post_on_directories()


def tasks_callback(src, dest):
	'''run tasks'''
	
	if not os.path.isdir(src):
		run_command(src)
		unix_out('')


def run_tasks():
	synctool_overlay.visit(synctool_overlay.OV_TASKS, tasks_callback)


def always_run():
	'''always run these commands'''
	
	for cmd in synctool_param.ALWAYS_RUN:
		run_command(cmd)
		unix_out('')


def single_files(filename):
	'''check/update a single file'''
	'''returns (True, path_in_synctree) if file is different'''
	
	if not filename:
		stderr('missing filename')
		return (False, None)
	
	src = synctool_overlay.find(synctool_overlay.OV_OVERLAY, filename)
	if not src:
		stdout('%s is not in the overlay tree' % filename)
		return (False, None)
	
	verbose('checking against %s' % synctool_lib.prettypath(src))
	
	changed = compare_files(src, filename)
	if not changed:
		stdout('%s is up to date' % filename)
		unix_out('# %s is up to date\n' % filename)
	
	return (changed, src)


def single_task(filename):
	'''run a single task'''

	if not filename:
		stderr('missing task filename')
		return
	
	task_script = filename
	if task_script[0] != '/':				# trick to make find() work for tasks, too
		task_script = '/' + task_script
	
	src = synctool_overlay.find(synctool_overlay.OV_TASKS, task_script)
	if not src:
		stderr("no such task '%s'" % filename)
		return
	
	run_command(src)
	unix_out('')


def reference(filename):
	'''show which source file in the repository synctool chooses to use'''
	
	if not filename:
		stderr('missing filename')
		return
	
	src = synctool_overlay.find(synctool_overlay.OV_OVERLAY, filename)
	if not src:
		stdout('%s is not in the overlay tree' % filename)
		return
	
	stdout(src)


def diff_files(filename):
	'''display a diff of the file'''
	
	if not synctool_param.DIFF_CMD:
		stderr('error: diff_cmd is undefined in %s' % synctool_param.CONF_FILE)
		return
	
	synctool_lib.DRY_RUN = True						# be sure that it doesn't do any updates
	
	sync_path = synctool_overlay.find(synctool_overlay.OV_OVERLAY, filename)
	if not sync_path:
		return
	
	if synctool_lib.UNIX_CMD:
		unix_out('%s %s %s' % (synctool_param.DIFF_CMD, filename, sync_path))
	else:
		verbose('%s %s %s' % (synctool_param.DIFF_CMD, filename, synctool_lib.prettypath(sync_path)))
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if use_subprocess:
			cmd_arr = shlex.split(synctool_param.DIFF_CMD)
			cmd_arr.append(filename)
			cmd_arr.append(sync_path)
			subprocess.Popen(cmd_arr, shell=False)
		else:
			os.system('%s %s %s' % (synctool_param.DIFF_CMD, filename, sync_path))
		
		sys.stdout.flush()
		sys.stderr.flush()


def be_careful_with_getopt():
	'''check sys.argv for dangerous common typo's on the command-line'''
	
	# be extra careful with possible typo's on the command-line
	# because '-f' might run --fix because of the way that getopt() works
	
	for arg in sys.argv:
		
		# This is probably going to give stupid-looking output in some cases,
		# but it's better to be safe than sorry
		
		if arg[:2] == '-d' and string.find(arg, 'f') > -1:
			print "Did you mean '--diff'?"
			sys.exit(1)

		if arg[:2] == '-r' and string.find(arg, 'f') > -1:
			if string.count(arg, 'e') >= 2:
				print "Did you mean '--reference'?"
			else:
				print "Did you mean '--ref'?"
			sys.exit(1)


def	option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix):
	'''some combinations of command-line options don't make sense; alert the user and abort'''
	
	if opt_upload and (opt_diff or opt_single or opt_reference or opt_tasks):
		stderr("the --upload option can not be combined with --diff, --single, --ref, or --tasks")
		sys.exit(1)
	
	if opt_suffix and not opt_upload:
		stderr("option --suffix can only be used together with --upload")
		sys.exit(1)
	
	if opt_diff and (opt_single or opt_reference or opt_tasks or opt_fix):
		stderr("option --diff can not be combined with --single, --ref, --tasks, or --fix")
		sys.exit(1)
	
	if opt_reference and (opt_single or opt_tasks or opt_fix):
		stderr("option --reference can not be combined with --single, --tasks, or --fix")
		sys.exit(1)


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file'
	print '                        (default: %s)' % synctool_param.DEFAULT_CONF
#	print '  -n, --dry-run         Show what would have been updated'
	print '  -d, --diff=file       Show diff for file'
	print '  -e, --erase-saved     Erase *.saved backup files'
	print '  -1, --single=file     Update a single file/run single task'
	print '  -r, --ref=file        Show which source file synctool chooses'
	print '  -t, --tasks           Run the scripts in the tasks/ directory'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '      --unix            Output actions as unix shell commands'
	print '      --version         Print current version number'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2011'


def get_options():
	global SINGLE_FILES
	
	progname = os.path.basename(sys.argv[0])
	
	synctool_lib.DRY_RUN = True				# set default dry-run
	
	if len(sys.argv) <= 1:
		return (None, None, None)
	
	be_careful_with_getopt()	# check for dangerous common typo's on the command-line
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:d:1:r:etfvq', ['help', 'conf=', 'diff=', 'single=', 'ref=', 'erase-saved', 'tasks', 'fix', 'verbose', 'quiet',
			'unix', 'masterlog', 'version'])
	except getopt.error, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)
	
	except getopt.GetoptError, (reason):
		print '%s: %s' % (progname, reason)
		usage()
		sys.exit(1)
	
	except:
		usage()
		sys.exit(1)
	
	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command line')
		sys.exit(1)
	
	errors = 0
	
	action = ACTION_DEFAULT
	SINGLE_FILES = []
	
	# these are only used for checking the validity of command-line option combinations
	opt_diff = False
	opt_single = False
	opt_reference = False
	opt_tasks = False
	opt_upload = False
	opt_suffix = False
	opt_fix = False
	
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue
		
# dry run already is default
#
#			if opt in ('-n', '--dry-run'):
#				synctool_lib.DRY_RUN = True
#				continue
		
		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool_lib.DRY_RUN = False
			continue
		
		if opt in ('-e', '--erase-saved'):
			synctool_param.ERASE_SAVED = True
			continue
		
		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			continue
		
		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True
			continue
		
		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue
		
		if opt == '--masterlog':
			synctool_lib.MASTERLOG = True
			continue
		
		if opt in ('-d', '--diff'):
			opt_diff = True
			action = ACTION_DIFF
			file = synctool_lib.prepare_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt in ('-1', '--single'):
			opt_single = True
			file = synctool_lib.prepare_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt in ('-t', '--task', '--tasks'):
			opt_tasks = True
			action = ACTION_RUN_TASKS
			continue
		
		if opt in ('-r', '--ref', '--reference'):
			opt_reference = True
			action = ACTION_REFERENCE
			file = synctool_lib.prepare_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt == '--version':
			return ACTION_VERSION
		
		stderr("unknown command line option '%s'" % opt)
		errors = errors + 1

	if errors:
		usage()
		sys.exit(1)
	
	option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix)
	
	return action


if __name__ == '__main__':
	action = get_options()
	
	if action == ACTION_VERSION:
		print synctool_param.VERSION
		sys.exit(0)
	
	synctool_config.read_config()
	synctool_config.add_myhostname()
	
	if synctool_param.NODENAME == None:
		stderr('unable to determine my nodename, please check %s' % synctool_param.CONF_FILE)
		sys.exit(1)
	
	if synctool_param.NODENAME in synctool_param.IGNORE_GROUPS:
		stderr('%s: node %s is disabled in the config file' % (synctool_param.CONF_FILE, synctool_param.NODENAME))
		sys.exit(1)
	
	synctool_config.remove_ignored_groups()
	
	synctool_param.MY_GROUPS = synctool_config.get_my_groups()
	synctool_param.ALL_GROUPS = synctool_config.make_all_groups()
	
	if synctool_lib.UNIX_CMD:
		t = time.localtime(time.time())
		
		unix_out('#')
		unix_out('# script generated by synctool on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# NODENAME=%s' % synctool_param.NODENAME)
		unix_out('# HOSTNAME=%s' % synctool_param.HOSTNAME)
		unix_out('# MASTERDIR=%s' % synctool_param.MASTERDIR)
		unix_out('# SYMLINK_MODE=0%o' % synctool_param.SYMLINK_MODE)
		unix_out('#')
		
		if not synctool_lib.DRY_RUN:
			unix_out('# NOTE: --fix specified, applying updates')
			unix_out('#')
		
		unix_out('')
	else:
		if not synctool_lib.QUIET:
			verbose('my nodename: %s' % synctool_param.NODENAME)
			verbose('my hostname: %s' % synctool_param.HOSTNAME)
			verbose('masterdir: %s' % synctool_param.MASTERDIR)
			verbose('symlink_mode: 0%o' % synctool_param.SYMLINK_MODE)
			
			if synctool_param.LOGFILE != None and not synctool_lib.DRY_RUN:
				verbose('logfile: %s' % synctool_param.LOGFILE)
			
			verbose('')
			
			if synctool_lib.DRY_RUN:
				stdout('DRY RUN, not doing any updates')
			else:
				stdout('--fix specified, applying changes')
			verbose('')
	
	synctool_lib.openlog()
	
	os.putenv('SYNCTOOL_NODENAME', synctool_param.NODENAME)
	os.putenv('SYNCTOOL_MASTERDIR', synctool_param.MASTERDIR)
	
	if action == ACTION_DIFF:
		for file in SINGLE_FILES:
			diff_files(file)
	
	elif action == ACTION_RUN_TASKS:
		if SINGLE_FILES:
			for single_file in SINGLE_FILES:
				single_task(single_file)
		else:
			run_tasks()
	
	elif action == ACTION_REFERENCE:
		for file in SINGLE_FILES:
			reference(file)
	
	elif SINGLE_FILES:
		for single_file in SINGLE_FILES:
			(changed, src) = single_files(single_file)
			if changed:
				run_post(single_file)
		
		run_post_on_directories()
	
	else:
		overlay_files()
		delete_files()
		always_run()
	
	unix_out('# EOB')
	
	synctool_lib.closelog()


# EOB
