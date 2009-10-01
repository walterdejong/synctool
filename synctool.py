#! /usr/bin/env python
#
#	synctool	WJ103
#

import synctool_config
import synctool_lib
import synctool_core

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

try:
	import hashlib
	use_hashlib = True
except ImportError:
	import md5
	use_hashlib = False

# extra command-line option --tasks
RUN_TASKS = False

# blocksize for doing I/O while checksumming files
BLOCKSIZE = 16 * 1024


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
	ended = 0
	while len1 == len2 and sum1.digest() == sum2.digest() and not ended:
		data1 = f1.read(BLOCKSIZE)
		if not data1:
			ended = 1
		else:
			len1 = len1 + len(data1)
			sum1.update(data1)

		data2 = f2.read(BLOCKSIZE)
		if not data2:
			ended = 1
		else:
			len2 = len2 + len(data2)
			sum2.update(data2)

	f1.close()
	f2.close()
	return sum1.digest(), sum2.digest()


def stat_islink(stat_struct):
	'''returns if a file is a symbolic link'''
	'''this function is needed because os.path.islink() returns False for dead symlinks, which is not what I want ...'''

	if not stat_struct:
		return 0

	return stat.S_ISLNK(stat_struct[stat.ST_MODE])


def stat_isdir(stat_struct):
	'''returns if a file is a directory'''
	'''this function is needed because os.path.isdir() returns True for symlinks to directories ...'''

	if not stat_struct:
		return 0

	return stat.S_ISDIR(stat_struct[stat.ST_MODE])


def stat_isfile(stat_struct):
	'''returns if a file is a regular file'''
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


def path_isignored(full_path, filename):
	if len(synctool_config.IGNORE_FILES) > 0:
		if filename in synctool_config.IGNORE_FILES:
			return 1

		arr = string.split(filename, '.')
		if len(arr) > 1 and arr[-1][0] == '_' and string.join(arr[:-1], '.') in synctool_config.IGNORE_FILES:
			return 1

	if path_isdir(full_path):
		if synctool_config.IGNORE_DOTDIRS and filename[0] == '.':
			verbose('ignoring hidden directory $masterdir/%s/' % full_path[synctool_config.MASTER_LEN:])
			return 1
	else:
		if synctool_config.IGNORE_DOTFILES and filename[0] == '.':
			verbose('ignoring hidden file $masterdir/%s' % full_path[synctool_config.MASTER_LEN:])
			return 1

	return 0


def compare_files(src_path, dest_path):
	'''see what the differences are between src and dest, and fix it if not a dry run

	src_path is the file in the synctool/overlay tree
	dest_path is the file in the system

	done is a local boolean saying if a path has been checked
	need_update is a local boolean saying if a path needs to be updated

	return value is 0 when file is not changed, 1 when file is updated

--
	The structure of this long function is as follows;

		stat(src)				this stat is 'sacred' and dest should be set accordingly
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
#	is source is a symbolic link ...
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

			if (dest_stat[stat.ST_MODE] & 07777) != synctool_config.SYMLINK_MODE:
				stdout('%s should have mode %04o (symlink), but has %04o' % (dest_path, synctool_config.SYMLINK_MODE, dest_stat[stat.ST_MODE] & 07777))
				unix_out('# fix permissions of symbolic link %s' % dest_path)
				need_update = True

		elif stat_isdir(dest_stat):
			done = True
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			move_dir(dest_path)
			need_update = True

#
#	treat as file ...
#
		if not done:
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			delete_file(dest_path)
			need_update = True

#
#	(re)create the symbolic link
#
		if need_update:
			symlink_file(src_link, dest_path)
			unix_out('')
			return True

		done = True

#
#	if the source is a directory ...
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
#	treat as a regular file
#
		if not done and not stat_isdir(dest_stat):
			done = True
			stdout('%s should be a directory' % dest_path)
			unix_out('# target should be a directory')
			delete_file(dest_path)
			need_update = True

#
#	make the directory
#
		if need_update:
			make_dir(dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])
			unix_out('')
			return True

		done = True

#
#	if source is a file ...
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
#	check file size
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
#	check file contents (SHA1 or MD5 checksum)
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
#	source is not a symbolic link, not a directory, and not a regular file
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
#	check mode and owner/group of files and/or directories
#
#	os.chmod() and os.chown() don't work well with symbolic links as they work on the destination
#	python lacks an os.lchmod() and os.lchown() as they are not portable
#	anyway, symbolic links have been dealt with already ...
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

	return need_update


def copy_file(src, dest):
	if path_isfile(dest):
		unix_out('mv %s %s.saved' % (dest, dest))

	unix_out('umask 077')
	unix_out('cp %s %s' % (src, dest))

	if not synctool_lib.DRY_RUN:
		if path_isfile(dest):
			verbose('  saving %s as %s.saved' % (dest, dest))
			try:
				os.rename(dest, '%s.saved' % dest)
			except OSError, reason:
				stderr('failed to save %s as %s.saved : %s' % (dest, dest, reason))

		old_umask = os.umask(077)

		verbose('  cp %s %s' % (src, dest))
		try:
			shutil.copy2(src, dest)			# copy file and stats
		except:
			stderr('failed to copy %s to %s' % (src, dest))

		os.umask(old_umask)
	else:
		if path_isfile(dest):
			verbose('  saving %s as %s.saved' % (dest, dest))

		verbose('  cp %s %s             # dry run, update not performed' % (src, dest))


def symlink_file(oldpath, newpath):
	if path_exists(newpath):
		unix_out('mv %s %s.saved' % (newpath, newpath))

#
#	actually, if we want the ownership of the symlink to be correct, we should do setuid() here
#	matching ownerships of symbolic links is not yet implemented
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
	unix_out('mv %s %s.saved' % (file, file))

	if not synctool_lib.DRY_RUN:
		verbose('moving %s to %s.saved' % (file, file))
		try:
			os.rename(file, '%s.saved' % file)
		except OSError, reason:
			stderr('failed to move file to %s.saved : %s' % (file, reason))

#		verbose('  os.unlink(%s)' % file)
#		try:
#			os.unlink(file)
#		except OSError, reason:
#			stderr('failed to delete %s : %s' % (file, reason))
	else:
		verbose('moving %s to %s.saved             # dry run, update not performed' % (file, file))


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

# a command can have arguments
	arr = string.split(cmd)
	if not arr:
		cmdfile = cmd
	else:
		cmdfile = arr[0]

# cmd1 is the pretty printed version of the command
	cmd1 = cmdfile
	if cmd1[0] != '/':
		cmd1 = '$masterdir/scripts/%s' % cmd1
#
#	if relative path, use script_path
#
		script_path = os.path.join(synctool_config.MASTERDIR, 'scripts')
		if not os.path.isdir(script_path):
			stderr('error: no such directory $masterdir/scripts')
			return

		cmdfile = os.path.join(script_path, cmdfile)

		arr[0] = cmdfile
		cmd = string.join(arr)

	elif len(cmd1) > synctool_config.MASTER_LEN and cmd1[:synctool_config.MASTER_LEN] == synctool_config.MASTERDIR + '/':
		cmd1 = '$masterdir/%s' % cmd1[synctool_config.MASTER_LEN:]

	if not path_exists(cmdfile):
		stderr('error: command %s not found' % cmd1)
		return

	if not path_isexec(cmdfile):
		stderr("warning: file '%s' is not executable" % cmdfile)
		return

	arr[0] = cmd1
	cmd1 = string.join(arr)
	if not synctool_lib.QUIET:
		stdout('%srunning command %s' % (not_str, cmd1))

	unix_out('# run command %s' % cmd1)
	unix_out(cmd)

	if not synctool_lib.DRY_RUN:
		verbose('  os.system("%s")' % cmd1)

		sys.stdout.flush()
		sys.stderr.flush()

		try:
			os.system(cmd)
		except OSError, reason:
			stderr("failed to run shell command '%s' : %s" % (cmd1, reason))

		sys.stdout.flush()
		sys.stderr.flush()
	else:
		verbose('  os.system("%s")             # dry run, action not performed' % cmd)


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


def overlay_callback(src_dir, dest_dir, filename, ext):
	'''compare files and run post-script if needed'''

	if ext:
		src = os.path.join(src_dir, '%s._%s' % (filename, ext))
	else:
		src = os.path.join(src_dir, filename)

	dest = os.path.join(dest_dir, filename)

	verbose('checking $masterdir/%s' % src[synctool_config.MASTER_LEN:])

	if compare_files(src, dest):
# file has changed, run on_update command
		if synctool_config.ON_UPDATE.has_key(dest):
			run_command_in_dir(dest_dir, synctool_config.ON_UPDATE[dest])

# file has changed, run appropriate .post script
		if synctool_core.POST_SCRIPTS.has_key(filename):
			run_command_in_dir(dest_dir, os.path.join(src_dir, synctool_core.POST_SCRIPTS[filename][0]))

# file in dir has changed, flag it
		synctool_core.DIR_CHANGED = True

	return True


def overlay_dir_updated(src_dir, dest_dir):
	'''this def gets called if there were any updates in this dir'''

# dir has changed, run on_update command
	if synctool_config.ON_UPDATE.has_key(dest_dir):
		run_command_in_dir(dest_dir, synctool_config.ON_UPDATE[dest_dir])

# dir has changed, run appropriate .post script
	basename = os.path.basename(dest_dir)
	dirname = os.path.dirname(src_dir)
	if synctool_core.POST_SCRIPTS.has_key(basename):
		run_command_in_dir(os.path.dirname(dest_dir), os.path.join(dirname, synctool_core.POST_SCRIPTS[basename][0]))


def overlay_files():
	'''run the overlay function'''

	base_path = os.path.join(synctool_config.MASTERDIR, 'overlay')
	if not os.path.isdir(base_path):
		stderr('error: $masterdir/overlay/ not found')
		return

	synctool_core.treewalk(base_path, '/', overlay_callback, overlay_dir_updated)


def delete_callback(src_dir, dest_dir, filename, ext):
	'''delete files'''

	if ext:
		src = os.path.join(src_dir, '%s._%s' % (filename, ext))
	else:
		src = os.path.join(src_dir, filename)

	dest = os.path.join(dest_dir, filename)

	if path_isdir(dest):			# do not delete directories
		return True

	if path_exists(dest):
		if synctool_lib.DRY_RUN:
			not_str = 'not '
		else:
			not_str = ''

		stdout('%sdeleting $masterdir/%s : %s' % (not_str, src[synctool_config.MASTER_LEN:], dest))
		hard_delete_file(dest)

# file in dir has changed, flag it
		synctool_core.DIR_CHANGED = True

	return True


def delete_dir_updated(src_dir, dest_dir):
	'''this def gets called when a file in the dir was deleted'''

# do the same as for overlay; run .post scripts
	overlay_dir_updated(src_dir, dest_dir)


def delete_files():
	base_path = os.path.join(synctool_config.MASTERDIR, 'delete')
	if not os.path.isdir(base_path):
		stderr('error: $masterdir/delete/ not found')
		return

	synctool_core.treewalk(base_path, '/', delete_callback, delete_dir_updated)


def tasks_callback(src_dir, dest_dir, filename, ext):
	'''run tasks'''

	if ext:
		src = os.path.join(src_dir, '%s._%s' % (filename, ext))
	else:
		src = os.path.join(src_dir, filename)

	run_command(src)
	unix_out('')
	return True


def run_tasks():
	base_path = os.path.join(synctool_config.MASTERDIR, 'tasks')
	if not os.path.isdir(base_path):
		stderr('error: $masterdir/tasks/ not found')
		return

	synctool_core.treewalk(base_path, '/', tasks_callback)


def always_run():
	'''always run these commands'''

	for cmd in synctool_config.ALWAYS_RUN:
		run_command(cmd)
		unix_out('')


def single_files(filename):
	'''check/update a single file'''
	'''returns (1, path_in_synctree) if file is different'''

	if not filename:
		stderr('missing filename')
		return (0, None)

	src = synctool_core.find_synctree('overlay', filename)
	if not src:
		stdout('%s is not in the overlay tree' % filename)
		return (0, None)

	verbose('checking against %s' % src)

	changed = compare_files(src, filename)
	if not changed:
		stdout('%s is up to date' % filename)
		unix_out('# %s is up to date\n' % filename)

	return (changed, src)


def on_update_single(src, dest):
	'''a single file has been updated. Run on_update command or appropriate .post script'''

	dest_dir = os.path.dirname(dest)

# file has changed, run on_update command
	if synctool_config.ON_UPDATE.has_key(dest):
		run_command_in_dir(dest_dir, synctool_config.ON_UPDATE[dest])

# file has changed, run appropriate .post script

	src_dir = os.path.dirname(src)
	filename = os.path.basename(dest)

	synctool_core.treewalk(src_dir, dest_dir, None, None, False)		# this constructs new synctool_core.POST_SCRIPTS dictionary

	if synctool_core.POST_SCRIPTS.has_key(filename):
		run_command_in_dir(dest_dir, os.path.join(src_dir, synctool_core.POST_SCRIPTS[filename][0]))

# if it was a indeed a file and not a directory, check if the directory has a .post script, too
	if os.path.isfile(src):
		src_dir = os.path.dirname(src_dir)
		basename = os.path.basename(dest_dir)
		dest_dir = os.path.dirname(dest_dir)

		if synctool_config.ON_UPDATE.has_key(dest_dir):
			run_command_in_dir(dest_dir, synctool_config.ON_UPDATE[dest_dir])

		synctool_core.treewalk(src_dir, dest_dir, None, None, False)		# this constructs new synctool_core.POST_SCRIPTS dictionary

		if synctool_core.POST_SCRIPTS.has_key(basename):
			run_command_in_dir(dest_dir, os.path.join(src_dir, synctool_core.POST_SCRIPTS[basename][0]))


def single_task(filename):
	'''run a single task'''

	if not filename:
		stderr('missing task filename')
		return

	task_script = filename
	if task_script[0] != '/':				# trick to make find_synctree() work for tasks, too
		task_script = '/' + task_script

	src = synctool_core.find_synctree('tasks', task_script)
	if not src:
		stderr("no such task '%s'" % filename)
		return

	run_command(src)
	unix_out('')


def diff_files(filename):
	'''display a diff of the file'''

	if not synctool_config.DIFF_CMD:
		stderr('error: diff_cmd is undefined in %s' % synctool_config.CONF_FILE)
		return

	synctool_lib.DRY_RUN = True						# be sure that it doesn't do any updates

	sync_path = synctool_core.find_synctree('overlay', filename)
	if not sync_path:
		return

	if synctool_lib.UNIX_CMD:
		unix_out('%s %s %s' % (synctool_config.DIFF_CMD, filename, sync_path))
	else:
		verbose('%s %s %s' % (synctool_config.DIFF_CMD, filename, sync_path))

		sys.stdout.flush()
		sys.stderr.flush()

		os.system('%s %s %s' % (synctool_config.DIFF_CMD, filename, sync_path))

		sys.stdout.flush()
		sys.stderr.flush()


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file'
	print '                        (default: %s)' % synctool_config.DEFAULT_CONF
#	print '  -n, --dry-run         Show what would have been updated'
	print '  -d, --diff=file       Show diff for file'
	print '  -1, --single=file     Update a single file/run single task'
	print '  -t, --tasks           Run the scripts in the tasks/ directory'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '      --unix            Output actions as unix shell commands'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@sara.nl> (c) 2003-2009'


if __name__ == '__main__':
	progname = os.path.basename(sys.argv[0])

	synctool_lib.DRY_RUN = True			# set default dry-run

	diff_file = None
	single_file = None

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:d:1:tfvq", ['help', 'conf=', 'diff=', 'single=', 'tasks', 'fix', 'verbose', 'quiet', 'unix', 'masterlog'])
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

		errors = 0

		for opt, arg in opts:
			if opt in ('-h', '--help', '-?'):
				usage()
				sys.exit(1)

			if opt in ('-c', '--conf'):
				synctool_config.CONF_FILE = arg
				continue

# dry run already is default
#
#			if opt in ('-n', '--dry-run'):
#				synctool_lib.DRY_RUN = True
#				continue

			if opt in ('-f', '--fix'):
				synctool_lib.DRY_RUN = False
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
				diff_file = arg
				continue

			if opt in ('-1', '--single'):
				single_file = arg
				continue

			if opt in ('-t', '--task', '--tasks'):
				RUN_TASKS = True
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

		if diff_file and RUN_TASKS:
			stderr("options '--diff' and '--tasks' cannot be combined")
			sys.exit(1)

		if diff_file and single_file:
			if diff_file != single_file:
				stderr("options '--diff' and '--single' cannot be combined")
				sys.exit(1)

		if diff_file and not synctool_lib.DRY_RUN:
			stderr("options '--diff' and '--fix' cannot be combined")
			sys.exit(1)

	synctool_config.read_config()
	synctool_config.add_myhostname()

	if synctool_config.NODENAME == None:
		stderr('unable to determine my nodename, please check %s' % synctool_config.CONF_FILE)
		sys.exit(1)

	if synctool_config.NODENAME in synctool_config.IGNORE_GROUPS:
		stderr('%s: node %s is disabled in the config file' % (synctool_config.CONF_FILE, synctool_config.NODENAME))
		sys.exit(1)

	synctool_config.remove_ignored_groups()

	synctool_config.GROUPS = synctool_config.get_my_groups()
	synctool_config.ALL_GROUPS = synctool_config.make_all_groups()

	if synctool_lib.UNIX_CMD:
		t = time.localtime(time.time())

		unix_out('#')
		unix_out('# synctool by Walter de Jong <walter@sara.nl> (c) 2003-2009')
		unix_out('#')
		unix_out('# script generated on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# NODENAME=%s' % synctool_config.NODENAME)
		unix_out('# HOSTNAME=%s' % synctool_config.HOSTNAME)
		unix_out('# MASTERDIR=%s' % synctool_config.MASTERDIR)
		unix_out('# SYMLINK_MODE=0%o' % synctool_config.SYMLINK_MODE)
		unix_out('#')

		if not synctool_lib.DRY_RUN:
			unix_out('# NOTE: --fix specified, applying updates')
			unix_out('#')

		unix_out('')
	else:
		if not synctool_lib.QUIET:
			verbose('my nodename: %s' % synctool_config.NODENAME)
			verbose('my hostname: %s' % synctool_config.HOSTNAME)
			verbose('masterdir: %s' % synctool_config.MASTERDIR)
			verbose('symlink_mode: 0%o' % synctool_config.SYMLINK_MODE)

			if synctool_config.LOGFILE != None and not synctool_lib.DRY_RUN:
				verbose('logfile: %s' % synctool_lib.LOGFILE)

			verbose('')

			if synctool_lib.DRY_RUN:
				stdout('DRY RUN, not doing any updates')
			else:
				stdout('--fix specified, applying changes')
			verbose('')

	synctool_lib.openlog()

	os.putenv('SYNCTOOL_NODENAME', synctool_config.NODENAME)
	os.putenv('SYNCTOOL_MASTERDIR', synctool_config.MASTERDIR)

	if diff_file:
		diff_files(diff_file)

	elif single_file:
		if RUN_TASKS:
			cmd = single_task(single_file)
			if cmd:
				run_command(cmd)
				unix_out('')
		else:
			(changed, src) = single_files(single_file)
			if changed:
				on_update_single(src, single_file)

	elif RUN_TASKS:
		run_tasks()

	else:
		overlay_files()
		delete_files()
		always_run()

	unix_out('# EOB')

	synctool_lib.closelog()


# EOB
