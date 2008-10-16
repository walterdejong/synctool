#! /usr/bin/env python
#
#	synctool	WJ103
#

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
import md5

DEFAULT_CONF='synctool.conf'

CONF_FILE=DEFAULT_CONF
DRY_RUN=1
VERBOSE=0
QUIET=0
UNIX_CMD=0
RUN_TASKS=0
LOGFILE=None
LOGFD=None

UPDATE_CACHE={}

#
#	default symlink mode
#	Linux makes them 0777 no matter what umask you have ...
#	but how do you like them on a different platform?
#
#	The symlink mode can be set in the config file with keyword symlink_mode
#
SYMLINK_MODE=0755

MONTHS = ( 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec' )


def verbose(str):
	'''do conditional output based on the verbose command line parameter'''

	if VERBOSE:
		print str


def unix_out(str):
	'''output as unix shell command'''

	if UNIX_CMD:
		print str


def stdout(str):
	if not UNIX_CMD:
		print str

	log(str)


def stderr(str):
	print str
	log(str)


def openlog(filename):
	global LOGFD

	LOGFD = None
	if filename != None and filename != '':
		try:
			LOGFD = open(filename, 'a')
		except IOError, (err, reason):
			print 'error: failed to open logfile %s : %s' % (filename, reason)
			sys.exit(-1)

		log('start run')


def closelog():
	global LOGFD

	if LOGFD != None:
		log('end run\n')

		LOGFD.close()
		LOGFD = None


def log(str):
	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' % (MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))


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
		raise IOError(err, 'failed to open %s : %s' % (file1, reason))

	try:
		f2 = open(file2, 'r')
	except IOError(err, reason):
		raise IOError(err, 'failed to open %s : %s' % (file2, reason))

	sum1 = md5.new()
	sum2 = md5.new()

	len1 = len2 = 0
	ended = 0
	while len1 == len2 and sum1.digest() == sum2.digest() and not ended:
		data1 = f1.read(4096)
		if not data1:
			ended = 1
		else:
			len1 = len1 + len(data1)
			sum1.update(data1)

		data2 = f2.read(4096)
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


def compare_files(src_path, dest_path):
	'''see what the differences are between src and dest, and fix it if not a dry run

	src_path is the file in the synctool/overlay tree
	dest_path is the file in the system

	UPDATE_CACHE is a name cache of files that have been updated
	it helps avoiding duplicate checks for files that have multiple classes

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

	global UPDATE_CACHE

	if UPDATE_CACHE.has_key(dest_path):
		verbose('%s was already updated' % dest_path)
		return 1

	src_stat = stat_path(src_path)
	if not src_stat:
		return 0

	dest_stat = stat_path(dest_path)
#	if not dest_path:
#		pass					# destination does not exist

	done = 0
	need_update = 0

#
#	is source is a symbolic link ...
#
	if not done and stat_islink(src_stat):
		need_update = 0
		try:
			src_link = os.readlink(src_path)
		except OSError, reason:
			stderr('failed to readlink %s : %s' % (src_path, reason))
			return 0

		if not stat_exists(dest_stat):
			done = 1
			stdout('symbolic link %s does not exist' % dest_path)
			unix_out('# create symbolic link %s' % dest_path)
			need_update = 1

		if stat_islink(dest_stat):
			done = 1
			try:
				dest_link = os.readlink(dest_path)
			except OSError, reason:
				stderr('failed to readlink %s : %s (but ignoring this error)' % (src_path, reason))
				dest_link = None

			if src_link != dest_link:
				stdout('%s should point to %s, but points to %s' % (dest_path, src_link, dest_link))
				unix_out('# relink symbolic link %s' % dest_path)
				delete_file(dest_path)
				need_update = 1

			if (dest_stat[stat.ST_MODE] & 07777) != SYMLINK_MODE:
				stdout('%s should have mode %04o (symlink), but has %04o' % (dest_path, SYMLINK_MODE, dest_stat[stat.ST_MODE] & 07777))
				unix_out('# fix permissions of symbolic link %s' % dest_path)
				need_update = 1

		elif stat_isdir(dest_stat):
			done = 1
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			move_dir(dest_path)
			need_update = 1

#
#	treat as file ...
#
		if not done:
			stdout('%s should be a symbolic link' % dest_path)
			unix_out('# target should be a symbolic link')
			delete_file(dest_path)
			need_update = 1

#
#	(re)create the symbolic link
#
		if need_update:
			symlink_file(src_link, dest_path)
			unix_out('')
			UPDATE_CACHE[dest_path] = 1
			return 1

		done = 1

#
#	if the source is a directory ...
#
	if not done and stat_isdir(src_stat):
		if not stat_exists(dest_stat):
			done = 1
			stdout('%s/ does not exist' % dest_path)
			unix_out('# make directory %s' % dest_path)
			need_update = 1

		if stat_islink(dest_stat):
			done = 1
			stdout('%s is a symbolic link, but should be a directory' % dest_path)
			unix_out('# target should be a directory instead of a symbolic link')
			delete_file(dest_path)
			need_update = 1

#
#	treat as a regular file
#
		if not done and not stat_isdir(dest_stat):
			done = 1
			stdout('%s should be a directory' % dest_path)
			unix_out('# target should be a directory')
			delete_file(dest_path)
			need_update = 1

#
#	make the directory
#
		if need_update:
			make_dir(dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])
			unix_out('')
			UPDATE_CACHE[dest_path] = 1
			return 1

		done = 1

#
#	if source is a file ...
#
	if not done and stat_isfile(src_stat):
		if not stat_exists(dest_stat):
			done = 1
			stdout('%s does not exist' % dest_path)
			unix_out('# copy file %s' % dest_path)
			need_update = 1

		if stat_islink(dest_stat):
			done = 1
			stdout('%s is a symbolic link, but should not be' % dest_path)
			unix_out('# target should be a file instead of a symbolic link')
			delete_file(dest_path)
			need_update = 1

		if stat_isdir(dest_stat):
			done = 1
			stdout('%s is a directory, but should not be' % dest_path)
			unix_out('# target should be a file instead of a directory')
			move_dir(dest_path)
			need_update = 1

#
#	check file size
#
		if stat_isfile(dest_stat):
			if src_stat[stat.ST_SIZE] != dest_stat[stat.ST_SIZE]:
				done = 1
				if DRY_RUN:
					stdout('%s mismatch (file size)' % dest_path)
				else:
					stdout('%s updated (file size mismatch)' % dest_path)
				unix_out('# updating file %s' % dest_path)
				need_update = 1
			else:
#
#	check file contents (SHA1 or MD5 checksum)
#
				try:
					src_sum, dest_sum = checksum_files(src_path, dest_path)
				except IOError, (err, reason):
					stderr('error: %s' % reason)
					return 0

				if src_sum != dest_sum:
					done = 1
					if DRY_RUN:
#						stdout('%s mismatch (SHA1 checksum)' % dest_path)
						stdout('%s mismatch (MD5 checksum)' % dest_path)
					else:
#						stdout('%s updated (SHA1 mismatch)' % dest_path)
						stdout('%s updated (MD5 mismatch)' % dest_path)

					unix_out('# updating file %s' % dest_path)
					need_update = 1

		elif not done:
			done = 1
			stdout('%s should be a regular file' % dest_path)
			unix_out('# target should be a regular file')
			need_update = 1

		if need_update:
			copy_file(src_path, dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])
			unix_out('')
			UPDATE_CACHE[dest_path] = 1
			return 1

		done = 1

	elif not done:
#
#	source is not a symbolic link, not a directory, and not a regular file
#
		stderr("be advised: don't know how to handle %s" % src_path)

		if not stat_exists(dest_stat):
			return 0

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
			UPDATE_CACHE[dest_path] = 1
			return 1

		if (src_stat[stat.ST_MODE] & 07777) != (dest_stat[stat.ST_MODE] & 07777):
			stdout('%s should have mode %04o, but has %04o' % (dest_path, src_stat[stat.ST_MODE] & 07777, dest_stat[stat.ST_MODE] & 07777))
			unix_out('# changing permissions on %s' % dest_path)

			set_permissions(dest_path, src_stat[stat.ST_MODE])

			unix_out('')
			UPDATE_CACHE[dest_path] = 1
			return 1

#		if src_stat[stat.ST_MTIME] != dest_stat[stat.ST_MTIME]:
#			stdout('%s should have mtime %d, but has %d' % (dest_path, src_stat[stat.ST_MTIME], dest_stat[stat.ST_MTIME]))
#		if src_stat[stat.ST_CTIME] != dest_stat[stat.ST_CTIME]:
#			stdout('%s should have ctime %d, but has %d' % (dest_path, src_stat[stat.ST_CTIME], dest_stat[stat.ST_CTIME]))

	return 0


def copy_file(src, dest):
	if path_isfile(dest):
		unix_out('mv %s %s.saved' % (dest, dest))

	unix_out('umask 077')
	unix_out('cp %s %s' % (src, dest))

	if not DRY_RUN:
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

	if not DRY_RUN:
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

	if not DRY_RUN:
		verbose('  os.chmod(%s, %04o)' % (file, mode & 07777))
		try:
			os.chmod(file, mode & 07777)
		except OSError, reason:
			stderr('failed to chmod %04o %s : %s' % (mode & 07777, file, reason))
	else:
		verbose('  os.chmod(%s, %04o)             # dry run, update not performed' % (file, mode & 07777))


def set_owner(file, uid, gid):
	unix_out('chown %s.%s %s' % (ascii_uid(uid), ascii_gid(gid), file))

	if not DRY_RUN:
		verbose('  os.chown(%s, %d, %d)' % (file, uid, gid))
		try:
			os.chown(file, uid, gid)
		except OSError, reason:
			stderr('failed to chown %s.%s %s : %s' % (ascii_uid(uid), ascii_gid(gid), file, reason))
	else:
		verbose('  os.chown(%s, %d, %d)             # dry run, update not performed' % (file, uid, gid))


def delete_file(file):
	unix_out('mv %s %s.saved' % (file, file))

	if not DRY_RUN:
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

	if not DRY_RUN:
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

	if not DRY_RUN:
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

	if not DRY_RUN:
		verbose('moving %s to %s.saved' % (dir, dir))
		try:
			os.rename(dir, '%s.saved' % dir)
		except OSError, reason:
			stderr('failed to move directory to %s.saved : %s' % (dir, reason))

	else:
		verbose('moving %s to %s.saved             # dry run, update not performed' % (dir, dir))


def strip_group_dir(dir, full_path, cfg, all_groups, groups):
	'''strip the group extension and return the basename, None on error'''

	parts = string.split(dir, '/')
	if not parts:
		arr = string.split(dir, '.')
	else:
		arr = string.split(parts[-1], '.')

	if len(arr) > 1 and arr[-1][0] == '_':
		group_ext = arr[-1][1:]

		if not group_ext in all_groups:
			master_len = len(cfg['masterdir'])
			stderr('warning: unknown group %s on directory $masterdir%s/, skipping' % (group_ext, full_path[master_len:]))
			return None

		if not group_ext in groups:
			master_len = len(cfg['masterdir'])
			verbose('skipping directory $masterdir%s/, it is not one of my groups' % full_path[master_len:])
			return None

		if not parts:
			dir = string.join(arr[:-1], '.')
		else:
			dir = string.join(arr[:-1], '.')
			dir = string.join(parts[:-1], '/') + '/' + dir

#	stderr('TD returning dir == %s' % dir)
	return dir


def strip_group_file(filename, full_path, cfg, all_groups, groups):
	'''strip group extension and return basename, None on error'''

	if path_isdir(full_path):
		return strip_group_dir(filename, full_path, cfg, all_groups, groups)

	arr = string.split(filename, '.')

	if len(arr) <= 1:
		master_len = len(cfg['masterdir'])
		stderr('warning: no extension on $masterdir%s, skipping' % full_path[master_len:])
		return None

	if arr[-1][0] != '_':
		master_len = len(cfg['masterdir'])
		stderr('warning: no underscored extension on $masterdir%s, skipping' % full_path[master_len:])
		return None

	group_ext = arr[-1][1:]

	if not group_ext in all_groups:
		master_len = len(cfg['masterdir'])
		stderr('warning: unknown group on $masterdir%s, skipping' % full_path[master_len:])
		return None

	if not group_ext in groups:
		master_len = len(cfg['masterdir'])
		verbose('skipping $masterdir%s, it is not one of my groups' % full_path[master_len:])
		return None

	return string.join(arr[:-1], '.')		# strip the 'group' or 'host' extension


def check_overrides(path, full_path, cfg, groups):
	override = None

	for group in groups:
		possible_override = '%s._%s' % (path, group)

		if path_exists(possible_override):
			override = possible_override
			break

	if override and full_path != override:
		master_len = len(cfg['masterdir'])
		verbose('overridden by $masterdir%s' % override[master_len:])

		if path_isdir(override):
			return 2

		return 1

	return 0


def compose_path(path):
	'''return a full destination path without any group extensions in subdirectory names'''
	'''e.g. /etc/sysconfig._group1/ifcfg-eth0._host1 => /etc/sysconfig/ifcfg-eth0'''

	arr = string.split(path, '/')

	newarr = []

#
#	we already know that this path is not going to be overridden any more, so
#	we can do this a bit hackish and simply strip all/any group extensions
#
	for part in arr:
		arr2 = string.split(part, '.')
		if len(arr2) > 1 and arr2[-1][0] == '_':
			newpart = string.join(arr2[:-1], '.')
			newarr.append(newpart)
		else:
			newarr.append(part)

	newpath = string.join(newarr, '/')
#	verbose('compose_path(%s) => %s' % (path, newpath))
	return newpath


def treewalk_overlay(args, dir, files):
	'''scan the overlay directory and check against the live system'''

	(cfg, base_path, groups, all_groups) = args
	base_len = len(base_path)

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	dest_dir = dir[base_len:]
	if not dest_dir:
		dest_dir = '/'

	n = 0
	nr_files = len(files)

	while n < nr_files:
		file = files[n]

		full_path = os.path.join(dir, file)

		verbose('checking $masterdir%s' % full_path[master_len:])

		dest = os.path.join(dest_dir, file)
#
#	check for valid group
#
		dest = strip_group_file(dest, full_path, cfg, all_groups, groups)
		if not dest:
			files.remove(file)			# this is important for directories
			nr_files = nr_files - 1
			continue

#
#	is this file/dir overridden by another group for this host?
#
		val = check_overrides(os.path.join(masterdir, 'overlay', dest[1:]), full_path, cfg, groups)
		if val:
			if val != 2:				# do not prune directories
				files.remove(file)

			nr_files = nr_files - 1
			continue

		n = n + 1

		dest = compose_path(dest)

#
#	if file is updated, run the appropriate on_update command
#
		if compare_files(full_path, dest):
			on_update(cfg, dest)


def on_update(cfg, dest):
	'''run on_update command for the dest file'''

	if cfg.has_key('on_update'):

# if the dest file is not in the on_update map, maybe it's directory is ...
# note that if there are multiple files in the directory that are updated,
# the action may is triggered multiple times as well

		update = cfg['on_update']
		if not update.has_key(dest):
			dest = os.path.dirname(dest)
			if not update.has_key(dest):
				dest = dest + '/'

		if update.has_key(dest):
			cmd = update[dest]
			run_command(cfg, cmd)


def run_command(cfg, cmd):
	'''run a shell command'''

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	if DRY_RUN:
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
		script_path = os.path.join(masterdir, 'scripts')
		if not os.path.isdir(script_path):
			stderr('error: no such directory $masterdir/scripts')
			return

		cmdfile = os.path.join(script_path, cmdfile)

		arr[0] = cmdfile
		cmd = string.join(arr)

	elif len(cmd1) > master_len and cmd1[:master_len] == masterdir:
		cmd1 = '$masterdir%s' % cmd1[master_len:]

	if not os.path.isfile(cmdfile):
		stderr('error: command %s not found' % cmd1)
		return

	arr[0] = cmd1
	cmd1 = string.join(arr)
	if not QUIET:
		stdout('%srunning command %s' % (not_str, cmd1))

	unix_out('# run command %s' % cmd1)
	unix_out(cmd)
	unix_out('')

	if not DRY_RUN:
		verbose('  os.system("%s")' % cmd1)
		try:
			os.system(cmd)
		except OSError, reason:
			stderr("failed to run shell command '%s' : %s" % (cmd1, reason))
	else:
		verbose('  os.system("%s")             # dry run, action not performed' % cmd)


def make_all_groups(cfg):
	'''make a list of all possible groups'''

	all_groups = []
	host_dict = cfg['host']
	for host in host_dict.keys():
		for group in host_dict[host]:
			if not group in all_groups:
				all_groups.append(group)

	all_groups.extend(cfg['ignore_groups'])		# although ignored, they are existing groups
	return all_groups


def overlay_files(cfg):
	'''run the overlay function'''

	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	base_path = os.path.join(masterdir, 'overlay')
	if not os.path.isdir(base_path):
		verbose('skipping %s, no such directory' % base_path)
		base_path = None

	if base_path:
		os.path.walk(base_path, treewalk_overlay, (cfg, base_path, groups, all_groups))


def treewalk_delete(args, dir, files):
	(cfg, delete_path, groups, all_groups) = args

	delete_len = len(delete_path)
	master_len = len(cfg['masterdir'])

	dest_dir = dir[delete_len:]
	if not dest_dir:
		dest_dir = '/'

	n = 0
	nr_files = len(files)

	while n < nr_files:
		file = files[n]

		full_path = os.path.join(dir, file)

		verbose('checking $masterdir%s' % full_path[master_len:])

		dest = os.path.join(dest_dir, file)
#
#	check for valid group
#
		dest = strip_group_file(dest, full_path, cfg, all_groups, groups)
		if not dest:
			files.remove(file)			# this is important for directories
			nr_files = nr_files - 1
			continue

#
#	is this file/dir overridden by another group for this host?
#
		if check_overrides(os.path.join(delete_path, dest[1:]), full_path, cfg, groups):
			files.remove(file)			# this is important for directories
			nr_files = nr_files - 1
			continue

		n = n + 1

		dest = compose_path(dest)

		if os.path.isdir(dest):			# do not delete directories
			continue

		if path_exists(dest):
			if DRY_RUN:
				not_str = 'not '
			else:
				not_str = ''

			stdout('%sdeleting $masterdir%s : %s' % (not_str, full_path[master_len:], dest))
			hard_delete_file(dest)


def delete_files(cfg):
	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	delete_path = os.path.join(masterdir, 'delete')
	if not os.path.isdir(delete_path):
		verbose('skipping $masterdir/delete, no such directory')
		return

	os.path.walk(delete_path, treewalk_delete, (cfg, delete_path, groups, all_groups))


def treewalk_tasks(args, dir, files):
	'''scan the tasks directory and run the necessary tasks'''

	(cfg, base_path, groups, all_groups) = args
	base_len = len(base_path)

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	dest_dir = dir[base_len:]
	if not dest_dir:
		dest_dir = '/'

	n = 0
	nr_files = len(files)

	while n < nr_files:
		file = files[n]

		full_path = os.path.join(dir, file)

		verbose('checking $masterdir%s' % full_path[master_len:])

		dest = os.path.join(dest_dir, file)

		dest = strip_group_file(dest, full_path, cfg, all_groups, groups)
		if not dest:
			files.remove(file)
			nr_files = nr_files - 1
			continue

#
#	is this file overridden by another group for this host?
#
		if check_overrides(os.path.join(masterdir, 'tasks', dest[1:]), full_path, cfg, groups):
			files.remove(file)
			nr_files = nr_files - 1
			continue

		n = n + 1

		dest = compose_path(dest)

		if path_isdir(dest):
			continue

# run the task
		run_command(cfg, dest)


def run_tasks(cfg):
	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	tasks_path = os.path.join(masterdir, 'tasks')
	if not os.path.isdir(tasks_path):
		verbose('skipping $masterdir/tasks, no such directory')
		return

	os.path.walk(tasks_path, treewalk_tasks, (cfg, tasks_path, groups, all_groups))


def always_run(cfg):
	'''always run these commands'''

	if not cfg.has_key('always_run'):
		return

	for cmd in cfg['always_run']:
		run_command(cfg, cmd)


def find_synctree(cfg, filename):
	'''helper function for single_files() and diff_files()'''
	'''find the path in the synctree for a given filename'''

	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]

	base_path = os.path.join(masterdir, 'overlay')
	if not os.path.isdir(base_path):
		stderr('error: overlay directory %s does not exist' % base_path)
		return None

#
#	make an absolute path
#
	if filename[0] != '/':
		filename = os.path.join(os.getcwd(), filename)

	full_path = base_path

	for part in string.split(filename, '/'):
		if not part:				# it started with a '/'
			continue

		overridden = 0
		for group in groups:
			src = os.path.join(full_path, '%s._%s' % (part, group))
			if path_exists(src):
				overridden = 1
				break

		if overridden:
			full_path = src
			continue

#
#	Mind that files in the synctree must end with a group extension
#	So it is correct to use path_isdir() here
#
		src = os.path.join(full_path, part)
		if not path_isdir(src):
			verbose('checking against %s' % src)
			stderr('%s is not in the synctool tree' % filename)
			return None

		full_path = src

	return full_path


def single_files(cfg, filename):
	'''check/update a single file'''
	'''returns (1, path_in_synctree) if file is different'''

	if not filename:
		stderr('missing filename')
		return (0, None)

	full_path = find_synctree(cfg, filename)
	if not full_path:
		return (0, None)

	verbose('checking against %s' % full_path)

	changed = compare_files(full_path, filename)
	if not changed:
		stdout('%s is up to date' % filename)
		unix_out('# %s is up to date\n' % filename)

	return (changed, full_path)


def diff_files(cfg, filename):
	'''display a diff of the file'''

	global DRY_RUN

	if not cfg.has_key('diff_cmd'):
		stderr('error: diff_cmd is undefined in %s' % CONF_FILE)
		return

	DRY_RUN=1							# be sure that it doesn't do any updates

	sync_path = find_synctree(cfg, filename)
	if not sync_path:
		return

	if UNIX_CMD:
		unix_out('%s %s %s' % (cfg['diff_cmd'], filename, sync_path))
	else:
		verbose('%s %s %s' % (cfg['diff_cmd'], filename, sync_path))
		os.system('%s %s %s' % (cfg['diff_cmd'], filename, sync_path))


def read_config(filename):
	'''read the config file and return cfg structure'''

	if not filename:
		filename = os.path.join('.', DEFAULT_CONF)

	cfg = {}
	cfg['ignore_groups'] = []

	if os.path.isdir(filename):
		filename = os.path.join(filename, DEFAULT_CONF)

# funky ... it is possible to open() directories without problems ...
	if not os.path.isfile(filename):
		stderr("no such config file '%s'" % filename)
		sys.exit(-1)

	try:
		cwd = os.getcwd()
	except OSError, reason:
		cwd = '.'

	filename = os.path.join(cwd, filename)
	if not QUIET:
		stdout('using config file: %s' % filename)

	try:
		f = open(filename, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (filename, reason))
		sys.exit(-1)

	lineno = 0
	errors = 0

	while 1:
		line = f.readline()
		if not line:
			break

		lineno = lineno + 1

		line = string.strip(line)
		if not line:
			continue

		if line[0] == '#':
			continue

		arr = string.split(line)
		if len(arr) <= 1:
			stderr('%s:%d: syntax error ; expected key/value pair' % (filename, lineno))
			errors = errors + 1
			continue

		keyword = string.lower(arr[0])

#
#	keyword: masterdir
#
		if keyword == 'masterdir':
			if cfg.has_key('masterdir'):
				stderr("%s:%d: redefinition of masterdir" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['masterdir'] = arr[1]
			continue

#
#	keyword: symlink_mode
#
		if keyword == 'symlink_mode':
			if cfg.has_key('symlink_mode'):
				stderr("%s:%d: redefinition of symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			try:
				mode = int(arr[1], 8)
			except ValueError:
				stderr("%s:%d: invalid argument for symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['symlink_mode'] = mode
			continue

#
#	keyword: host
#
		if keyword == 'host':
			if len(arr) < 2:
				stderr("%s:%d: 'host' requires at least 1 argument: the hostname" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('host'):
				cfg['host'] = {}

			host = arr[1]
			groups = arr[2:]

			if cfg['host'].has_key(host):
				stderr("%s:%d: redefinition of host %s" % (filename, lineno, host))
				errors = errors + 1
				continue

			cfg['host'][host] = groups
			continue

#
#	keyword: ignore_host
#
		if keyword == 'ignore_host':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_host' requires 1 argument: the hostname to ignore" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['ignore_groups'].append(arr[1])
			continue

#
#	keyword: ignore_group
#
		if keyword == 'ignore_group':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_group' requires at least 1 argument: the group to ignore" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['ignore_groups'].extend(arr[1:])
			continue

#
#	keyword: on_update
#
		if keyword == 'on_update':
			if len(arr) < 3:
				stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('on_update'):
				cfg['on_update'] = {}

			file = arr[1]
			cmd = string.join(arr[2:])

			if cfg['on_update'].has_key(file):
				stderr("%s:%d: redefinition of on_update %s" % (filename, lineno, file))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[2][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[2])
			else:
				full_cmd = arr[2]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['on_update'][file] = cmd
			continue

#
#	keyword: always_run
#
		if keyword == 'always_run':
			if len(arr) < 2:
				stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('always_run'):
				cfg['always_run'] = []

			cmd = string.join(arr[1:])

			if cmd in cfg['always_run']:
				stderr("%s:%d: same command defined again: %s" % (filename, lineno, cmd))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[1][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[1])
			else:
				full_cmd = arr[1]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['always_run'].append(cmd)
			continue

#
#	keyword: diff_cmd
#
		if keyword == 'diff_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'diff_cmd' requires an argument: the full path to the 'diff' command" % (filename, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('diff_cmd'):
				stderr("%s:%d: redefinition of diff_cmd" % (filename, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, cmd))
				errors = errors + 1
				continue

			cfg['diff_cmd'] = string.join(arr[1:])
			continue

		stderr("%s:%d: unknown keyword '%s'" % (filename, lineno, keyword))
		errors = errors + 1

	f.close()

	if not cfg.has_key('masterdir'):
		cfg['masterdir'] = '.'

#
#	get my hostname
#
	hostname = socket.gethostname()
	arr = string.split(hostname, '.')

	if arr[0] in cfg['ignore_groups']:
		stderr('host %s is disabled in the config file' % arr[0])
		errors = errors + 1
	else:
		if cfg['host'].has_key(hostname):
			cfg['hostname'] = hostname

			if len(arr) > 0 and arr[0] != hostname and cfg['host'].has_key(arr[0]):
				stderr("%s: conflict; host %s and %s are both defined" % (filename, hostname, arr[0]))
				errors = errors + 1
		else:
			if len(arr) > 0 and cfg['host'].has_key(arr[0]):
				cfg['hostname'] = arr[0]
				hostname = arr[0]
			else:
				stderr('%s: no entry for host %s defined' % (filename, hostname))
				errors = errors + 1

	if errors > 0:
		sys.exit(-1)

# implicitly add 'hostname' as first group
	if not hostname in cfg['host'][hostname]:
		cfg['host'][hostname].insert(0, hostname)

	for host in cfg['host'].keys():
		if not host in cfg['host'][host]:
			cfg['host'][host].insert(0, host)

# remove ignored groups from all hosts
		changed = 0
		groups = cfg['host'][host]
		for ignore in cfg['ignore_groups']:
			if ignore in groups:
				groups.remove(ignore)
				changed = 1

		if changed:
			cfg['host'][host] = groups

	return cfg


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file (default: %s)' % DEFAULT_CONF
#	print '  -n, --dry-run         Show what would have been updated'
	print '  -d, --diff=file       Show diff for file'
	print '  -1, --single=file     Update a single file'
	print '  -t, --tasks           Run the scripts in the tasks/ directory'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '  -x, --unix            Output actions as unix shell commands'
	print '  -l, --log=logfile     Log taken actions to logfile'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@sara.nl> (c) 2003-2006'


def main():
	global CONF_FILE, DRY_RUN, VERBOSE, QUIET, UNIX_CMD, LOGFILE, SYMLINK_MODE, RUN_TASKS

	progname = os.path.basename(sys.argv[0])

	diff_file = None
	single_file = None

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:l:d:1:tfvqx", ['help', 'conf=', 'log=', 'diff=', 'single=', 'tasks', 'fix', 'verbose', 'quiet', 'unix'])
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
				CONF_FILE=arg
				continue

# dry run already is default
#
#			if opt in ('-n', '--dry-run'):
#				DRY_RUN=1
#				continue

			if opt in ('-f', '--fix'):
				DRY_RUN=0
				continue

			if opt in ('-v', '--verbose'):
				VERBOSE=1
				continue

			if opt in ('-q', '--quiet'):
				QUIET=1
				continue

			if opt in ('-x', '--unix'):
				UNIX_CMD=1
				continue

			if opt in ('-l', '--log'):
				LOGFILE=arg
				continue

			if opt in ('-d', '--diff'):
				diff_file=arg
				continue

			if opt in ('-1', '--single'):
				single_file=arg
				continue

			if opt in ('-t', '--task', '--tasks'):
				RUN_TASKS=1
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

		if diff_file and single_file:
			if diff_file != single_file:
				stderr("options '--diff' and '--single' cannot be combined")
				sys.exit(1)

		if diff_file and not DRY_RUN:
			stderr("options '--diff' and '--fix' cannot be combined")
			sys.exit(1)

	cfg = read_config(CONF_FILE)

	if cfg.has_key('symlink_mode'):
		SYMLINK_MODE = cfg['symlink_mode']

	if UNIX_CMD:
		import time

		t = time.localtime(time.time())

		unix_out('#')
		unix_out('# synctool by Walter de Jong <walter@sara.nl> (c) 2003')
		unix_out('#')
		unix_out('# script generated on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# HOSTNAME=%s' % cfg['hostname'])
		unix_out('# MASTERDIR=%s' % cfg['masterdir'])
		unix_out('# SYMLINK_MODE=0%o' % SYMLINK_MODE)
		unix_out('#')

		if DRY_RUN:
			unix_out('# NOTE: dry run, not doing any updates')
		else:
			unix_out('# NOTE: --fix specified, applying updates')
			if LOGFILE != None:
				unix_out('#')
				unix_out('# logging to: %s' % LOGFILE)

		unix_out('#')
		unix_out('')
	else:
		if not QUIET:
			stdout('my hostname: %s' % cfg['hostname'])
			stdout('masterdir: %s' % cfg['masterdir'])
			verbose('symlink_mode: 0%o' % SYMLINK_MODE)

			if LOGFILE != None and not DRY_RUN:
				stdout('logfile: %s' % LOGFILE)

			stdout('')

			if DRY_RUN:
				stdout(' DRY RUN, not doing any updates')
			else:
				stdout(' --fix specified, applying changes')
			stdout('')

	openlog(LOGFILE)

	os.putenv('MASTERDIR', cfg['masterdir'])

	if diff_file:
		diff_files(cfg, diff_file)

	elif single_file:
		(changed, full_path) = single_files(cfg, single_file)
		if changed:
			on_update(cfg, full_path)

	else:
		overlay_files(cfg)
		delete_files(cfg)
		always_run(cfg)

	if RUN_TASKS:
		run_tasks(cfg)

	unix_out('# EOB')

	closelog()


if __name__ == '__main__':
	main()

# EOB
