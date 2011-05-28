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

from synctool_lib import verbose,stdout,stderr,terse,unix_out

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

# blocksize for doing I/O while checksumming files
BLOCKSIZE = 16 * 1024

SINGLE_FILES = []

# list of changed directories
# This is for running .post scripts on changed directories
# every element is a tuple: (src_path, dest_path)
DIR_CHANGED = []


def dryrun_msg(str, action = 'update'):
	'''print a "dry run" message filled to (almost) 80 chars
	so that it looks nice on the terminal'''
	
	l1 = len(str) + 4
	
	msg = '# dry run, %s not performed' % action
	l2 = len(msg)
	
	if l1 + l2 <= 79:
		return str + (' ' * (79 - (l1 + l2))) + msg
	
	if l1 + 13 <= 79:
		# message is long, but we can shorten and it will fit on a line
		msg = '# dry run'
		l2 = 9
		return str + (' ' * (79 - (l1 + l2))) + msg
	
	# don't bother, return a long message
	return str + '    ' + msg


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


def compare_files(obj):
	'''see what the differences are for this SyncObject, and fix it
	if not a dry run
	
	obj.src_path is the file in the synctool/overlay tree
	obj.dest_path is the file in the system
	
	need_update is a local boolean saying if a path needs to be updated
	
	return value is False when file is not changed, True when file is updated
	
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
		return False
'''
	
	src_path = obj.src_path
	dest_path = obj.dest_path
	
	obj.src_stat()
	src_stat = obj.src_statbuf
	if not src_stat:
		return False
	
	obj.dest_stat()
	dest_stat = obj.dest_statbuf
#	if not dest_stat:
#		pass					# destination does not exist
	
	need_update = False
	
	#
	# if source is a symbolic link ...
	#
	if src_stat.isLink():
		need_update = False
		try:
			src_link = os.readlink(src_path)
		except OSError, reason:
			stderr('failed to readlink %s : %s' % (src_path, reason))
			terse(synctool_lib.TERSE_FAIL, 'readlink %s' % src_path)
			return False
		
		if not dest_stat.exists():
			stdout('symbolic link %s does not exist' % dest_path)
			terse(synctool_lib.TERSE_LINK, dest_path)
			unix_out('# create symbolic link %s' % dest_path)
			need_update = True
		
		elif dest_stat.isLink():
			try:
				dest_link = os.readlink(dest_path)
			except OSError, reason:
				stderr('failed to readlink %s : %s (but ignoring this error)' % (src_path, reason))
				terse(synctool_lib.TERSE_FAIL, 'readlink %s' % src_path)
				dest_link = None
			
			if src_link != dest_link:
				stdout('%s should point to %s, but points to %s' % (dest_path, src_link, dest_link))
				terse(synctool_lib.TERSE_LINK, dest_path)
				unix_out('# relink symbolic link %s' % dest_path)
				delete_file(dest_path)
				need_update = True
			
			if (dest_stat.mode & 07777) != synctool_param.SYMLINK_MODE:
				stdout('%s should have mode %04o (symlink), but has %04o' % (dest_path, synctool_param.SYMLINK_MODE, dest_stat.mode & 07777))
				terse(synctool_lib.TERSE_MODE, '%04o %s' % (synctool_param.SYMLINK_MODE, dest_path))
				unix_out('# fix permissions of symbolic link %s' % dest_path)
				need_update = True
		
		elif dest_stat.isDir():
			stdout('%s should be a symbolic link' % dest_path)
			terse(synctool_lib.TERSE_LINK, dest_path)
			unix_out('# target should be a symbolic link')
			save_dir(dest_path)
			need_update = True
		
		#
		# treat as file ...
		#
		else:
			stdout('%s should be a symbolic link' % dest_path)
			terse(synctool_lib.TERSE_LINK, dest_path)
			unix_out('# target should be a symbolic link')
			delete_file(dest_path)
			need_update = True
		
		#
		# (re)create the symbolic link
		#
		if need_update:
			symlink_file(obj, src_link)
			unix_out('')
			return True
	
	#
	# if the source is a directory ...
	#
	elif src_stat.isDir():
		if not dest_stat.exists():
			stdout('%s/ does not exist' % dest_path)
			terse(synctool_lib.TERSE_MKDIR, dest_path)
			unix_out('# make directory %s' % dest_path)
			need_update = True
		
		elif dest_stat.isLink():
			stdout('%s is a symbolic link, but should be a directory' % dest_path)
			terse(synctool_lib.TERSE_MKDIR, dest_path)
			unix_out('# target should be a directory instead of a symbolic link')
			delete_file(dest_path)
			need_update = True
		
		#
		# treat as a regular file
		#
		elif not dest_stat.isDir():
			stdout('%s should be a directory' % dest_path)
			terse(synctool_lib.TERSE_MKDIR, dest_path)
			unix_out('# target should be a directory')
			delete_file(dest_path)
			need_update = True
		
		#
		# make the directory
		#
		if need_update:
			make_dir(dest_path)
			set_owner(dest_path, src_stat.uid, src_stat.gid)
			set_permissions(dest_path, src_stat.mode)
			unix_out('')
			return True
	
	#
	# if source is a file ...
	#
	elif src_stat.isFile():
		if not dest_stat.exists():
			stdout('%s does not exist' % dest_path)
			terse(synctool_lib.TERSE_NEW, dest_path)
			unix_out('# copy file %s' % dest_path)
			need_update = True
		
		elif dest_stat.isLink():
			stdout('%s is a symbolic link, but should not be' % dest_path)
			terse(synctool_lib.TERSE_TYPE, dest_path)
			unix_out('# target should be a file instead of a symbolic link')
			delete_file(dest_path)
			need_update = True
		
		elif dest_stat.isDir():
			stdout('%s is a directory, but should not be' % dest_path)
			terse(synctool_lib.TERSE_TYPE, dest_path)
			unix_out('# target should be a file instead of a directory')
			save_dir(dest_path)
			need_update = True
		
		#
		# check file size
		#
		elif dest_stat.isFile():
			if src_stat.size != dest_stat.size:
				if synctool_lib.DRY_RUN:
					stdout('%s mismatch (file size)' % dest_path)
				else:
					stdout('%s updated (file size mismatch)' % dest_path)
				terse(synctool_lib.TERSE_SYNC, dest_path)
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
					if synctool_lib.DRY_RUN:
#						stdout('%s mismatch (SHA1 checksum)' % dest_path)
						stdout('%s mismatch (MD5 checksum)' % dest_path)
					else:
#						stdout('%s updated (SHA1 mismatch)' % dest_path)
						stdout('%s updated (MD5 mismatch)' % dest_path)

					terse(synctool_lib.TERSE_SYNC, dest_path)
					unix_out('# updating file %s' % dest_path)
					need_update = True
		
		else:
			stdout('%s should be a regular file' % dest_path)
			terse(synctool_lib.TERSE_TYPE, dest_path)
			unix_out('# target should be a regular file')
			need_update = True
		
		if need_update:
			copy_file(obj)
			set_owner(dest_path, src_stat.uid, src_stat.gid)
			set_permissions(dest_path, src_stat.mode)
			unix_out('')
			return True
	
	else:
		#
		# source is not a symbolic link, not a directory, and not a regular file
		#
		stderr("be advised: don't know how to handle %s" % src_path)
		terse(synctool_lib.TERSE_WARNING, 'unknown type %s' % src_path)
		
		if not dest_stat.exists():
			return False
		
		if dest_stat.isLink():
			stdout('%s should not be a symbolic link' % dest_path)
			terse(synctool_lib.TERSE_WARNING, 'wrong type %s' % dest_path)
		else:
			if dest_stat.isDir():
				stdout('%s should not be a directory' % dest_path)
				terse(synctool_lib.TERSE_WARNING, 'wrong type %s' % dest_path)
			else:
				if dest_stat.isFile():
					stdout('%s should not be a regular file' % dest_path)
					terse(synctool_lib.TERSE_WARNING, 'wrong type %s' % dest_path)
				else:
					stderr("don't know how to handle %s" % dest_path)
					terse(synctool_lib.TERSE_WARNING, 'unknown type %s' % dest_path)
	
	#
	# check mode and owner/group of files and/or directories
	#
	# os.chmod() and os.chown() don't work well with symbolic links as they work
	# on the destination rather than the symlink itself
	# python lacks an os.lchmod() and os.lchown() as they are not portable
	# anyway, symbolic links have been dealt with already ...
	#
	if dest_stat.exists() and not dest_stat.isLink():
		if src_stat.uid != dest_stat.uid or src_stat.gid != dest_stat.gid:
			owner = src_stat.ascii_uid()
			group = src_stat.ascii_gid()
			stdout('%s should have owner %s.%s (%d.%d), but has %s.%s (%d.%d)' % (dest_path, owner, group,
				src_stat.uid, src_stat.gid,
				dest_stat.ascii_uid(), dest_stat.ascii_gid(),
				dest_stat.uid, dest_stat.gid))
			
			terse(synctool_lib.TERSE_OWNER, '%s.%s %s' % (owner, group, dest_path))
			unix_out('# changing ownership on %s' % dest_path)
			
			set_owner(dest_path, src_stat.uid, src_stat.gid)
			
			unix_out('')
			need_update = True
		
		if (src_stat.mode & 07777) != (dest_stat.mode & 07777):
			stdout('%s should have mode %04o, but has %04o' % (dest_path, src_stat.mode & 07777, dest_stat.mode & 07777))
			terse(synctool_lib.TERSE_MODE, '%04o %s' % (src_stat.mode & 07777, dest_path))
			unix_out('# changing permissions on %s' % dest_path)
			
			set_permissions(dest_path, src_stat.mode)
			
			unix_out('')
			need_update = True
		
#		if src_stat[stat.ST_MTIME] != dest_stat[stat.ST_MTIME]:
#			stdout('%s should have mtime %d, but has %d' % (dest_path, src_stat[stat.ST_MTIME], dest_stat[stat.ST_MTIME]))
#		if src_stat[stat.ST_CTIME] != dest_stat[stat.ST_CTIME]:
#			stdout('%s should have ctime %d, but has %d' % (dest_path, src_stat[stat.ST_CTIME], dest_stat[stat.ST_CTIME]))
	
	erase_saved(dest_path)
	return need_update


def copy_file(obj):
	src = obj.src_path
	dest = obj.dest_path
	
	if obj.dest_isFile():
		unix_out('cp %s %s.saved' % (dest, dest))
	
	unix_out('umask 077')
	unix_out('cp %s %s' % (src, dest))
	
	if not synctool_lib.DRY_RUN:
		old_umask = os.umask(077)
		
		if synctool_param.BACKUP_COPIES:
			if obj.dest_isFile():
				verbose('  saving %s as %s.saved' % (dest, dest))
				try:
					shutil.copy2(dest, '%s.saved' % dest)
				except:
					stderr('failed to save %s as %s.saved' % (dest, dest))
		
		verbose('  cp %s %s' % (src, dest))
		try:
			shutil.copy2(src, dest)			# copy file and stats
		except:
			stderr('failed to copy %s to %s' % (obj.print_src(), dest))
		
		os.umask(old_umask)
	else:
		if obj.dest_isFile() and synctool_param.BACKUP_COPIES:
			verbose('  saving %s as %s.saved' % (dest, dest))
		
		verbose(dryrun_msg('  cp %s %s' % (src, dest)))


def symlink_file(obj, oldpath):
	# note that old_path is the readlink() of the obj.src_path
	new_path = obj.dest_path
	
	if obj.dest_exists():
		unix_out('mv %s %s.saved' % (newpath, newpath))
	
	#
	# actually, if we want the ownership of the symlink to be correct,
	# we should do setuid() here
	# matching ownerships of symbolic links is not yet implemented
	#
	
	# linux makes all symlinks mode 0777, but some other platforms do not
	umask_mode = synctool_param.symlink_mode ^ 0777
	
	unix_out('umask %03o' % umask_mode)
	unix_out('ln -s %s %s' % (oldpath, newpath))
	
	if not synctool_lib.DRY_RUN:
		if obj.dest_exists():
			verbose('saving %s as %s.saved' % (newpath, newpath))
			try:
				os.rename(newpath, '%s.saved' % newpath)
			except OSError, reason:
				stderr('failed to save %s as %s.saved : %s' % (newpath, newpath, reason))
				terse(synctool_lib.TERSE_FAIL, 'save %s.saved' % newpath)
		
		old_umask = os.umask(umask_mode)
		
		verbose('  os.symlink(%s, %s)' % (oldpath, newpath))
		try:
			os.symlink(oldpath, newpath)
		except OSError, reason:
			stderr('failed to create symlink %s -> %s : %s' % (newpath, oldpath, reason))
			terse(synctool_lib.TERSE_FAIL, 'link %s' % newpath)
		
		os.umask(old_umask)
	
	else:
		verbose(dryrun_msg('  os.symlink(%s, %s)' % (oldpath, newpath)))


def set_permissions(file, mode):
	unix_out('chmod 0%o %s' % (mode & 07777, file))

	if not synctool_lib.DRY_RUN:
		verbose('  os.chmod(%s, %04o)' % (file, mode & 07777))
		try:
			os.chmod(file, mode & 07777)
		except OSError, reason:
			stderr('failed to chmod %04o %s : %s' % (mode & 07777, file, reason))
	else:
		verbose(dryrun_msg('  os.chmod(%s, %04o)' % (file, mode & 07777)))


def set_owner(file, uid, gid):
	unix_out('chown %s.%s %s' % (ascii_uid(uid), ascii_gid(gid), file))

	if not synctool_lib.DRY_RUN:
		verbose('  os.chown(%s, %d, %d)' % (file, uid, gid))
		try:
			os.chown(file, uid, gid)
		except OSError, reason:
			stderr('failed to chown %s.%s %s : %s' % (ascii_uid(uid), ascii_gid(gid), file, reason))
	else:
		verbose(dryrun_msg('  os.chown(%s, %d, %d)' % (file, uid, gid)))


def delete_file(file):
	if not synctool_lib.DRY_RUN:
		if synctool_param.BACKUP_COPIES:
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
		if synctool_param.BACKUP_COPIES:
			verbose(dryrun_msg('moving %s to %s.saved' % (file, file)))
		else:
			verbose(dryrun_msg('deleting %s' % file, 'delete'))


def hard_delete_file(file):
	unix_out('rm -f %s' % file)

	if not synctool_lib.DRY_RUN:
		verbose('  os.unlink(%s)' % file)
		try:
			os.unlink(file)
		except OSError, reason:
			stderr('failed to delete %s : %s' % (file, reason))
	else:
		verbose(dryrun_msg('deleting %s' % file, 'delete'))


def erase_saved(dest):
	if synctool_lib.ERASE_SAVED and path_exists('%s.saved' % dest) and not path_isdir('%s.saved' % dest):
		terse(synctool_lib.TERSE_DELETE, '%s.saved' % dest)
		unix_out('rm %s.saved' % dest)
		
		if synctool_lib.DRY_RUN:
			stdout(dryrun_msg('erase %s.saved' % dest, 'erase'))
		else:
			stdout('erase %s.saved' % dest)
			verbose('  os.unlink(%s.saved)' % dest)
			try:
				os.unlink('%s.saved' % dest)
			except OSError, reason:
				stderr('failed to delete %s : %s' % (dest, reason))


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
		verbose(dryrun_msg('  os.mkdir(%s)' % path))


def save_dir(dir):
	if not synctool_param.BACKUP_COPIES:
		return
	
	unix_out('mv %s %s.saved' % (dir, dir))

	if not synctool_lib.DRY_RUN:
		verbose('moving %s to %s.saved' % (dir, dir))
		try:
			os.rename(dir, '%s.saved' % dir)
		except OSError, reason:
			stderr('failed to move directory to %s.saved : %s' % (dir, reason))

	else:
		verbose(dryrun_msg('moving %s to %s.saved' % (dir, dir), 'move'))


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
	
	terse(synctool_lib.TERSE_EXEC, cmdfile)
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
		verbose(dryrun_msg('  os.system("%s")' % synctool_lib.prettypath(cmd), 'action'))


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
	
	# they have run, now cleanup DIR_CHANGED
	DIR_CHANGED = {}


def overlay_callback(obj):
	'''compare files and run post-script if needed'''
	
	verbose('checking %s' % obj.print_src())
	
	if compare_files(obj):
		run_post(obj.src_path, obj.dest_path)


def overlay_files():
	'''run the overlay function'''
	
	synctool_overlay.visit(synctool_overlay.OV_OVERLAY, overlay_callback)


def delete_callback(obj):
	'''delete files'''
	
	if obj.dest_isDir():		# do not delete directories
		return
	
	if obj.dest_exists():
		if synctool_lib.DRY_RUN:
			not_str = 'not '
		else:
			not_str = ''
		
		stdout('%sdeleting %s : %s' % (not_str, obj.print_src(), obj.print_dest()))
		hard_delete_file(obj.dest_path)
		run_post(obj.src_path, obj.dest_path)


def delete_files():
	synctool_overlay.visit(synctool_overlay.OV_DELETE, delete_callback)


def tasks_callback(obj):
	'''run tasks'''
	
	if not obj.src_isDir():
		run_command(obj.src_path)
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
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return (False, None)
	
	verbose('checking against %s' % obj.print_src())
	
	changed = compare_files(obj)
	if not changed:
		stdout('%s is up to date' % filename)
		terse(synctool_lib.TERSE_OK, filename)
		unix_out('# %s is up to date\n' % obj.print_dest())
	
	return (changed, obj.src_path)


def single_task(filename):
	'''run a single task'''

	if not filename:
		stderr('missing task filename')
		return
	
	task_script = filename
	if task_script[0] != '/':				# trick to make find() work for tasks, too
		task_script = '/' + task_script
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_TASKS, task_script)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr("no such task '%s'" % filename)
		return
	
	run_command(obj.src_path)
	unix_out('')


def reference(filename):
	'''show which source file in the repository synctool chooses to use'''
	
	if not filename:
		stderr('missing filename')
		return
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		stderr('%s is not in the overlay tree' % filename)
		return
	
	print obj.print_src()


def diff_files(filename):
	'''display a diff of the file'''
	
	if not synctool_param.DIFF_CMD:
		stderr('error: diff_cmd is undefined in %s' % synctool_param.CONF_FILE)
		return
	
	synctool_lib.DRY_RUN = True						# be sure that it doesn't do any updates
	
	(obj, err) = synctool_overlay.find_terse(synctool_overlay.OV_OVERLAY, filename)
	if err == synctool_overlay.OV_FOUND_MULTIPLE:
		# multiple source possible
		# possibilities have already been printed
		sys.exit(1)
	
	if err == synctool_overlay.OV_NOT_FOUND:
		return
	
	if synctool_lib.UNIX_CMD:
		unix_out('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.src_path))
	else:
		verbose('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.print_src()))
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if use_subprocess:
			cmd_arr = shlex.split(synctool_param.DIFF_CMD)
			cmd_arr.append(dest)
			cmd_arr.append(obj.src_path)
			subprocess.Popen(cmd_arr, shell=False)
		else:
			os.system('%s %s %s' % (synctool_param.DIFF_CMD, dest, obj.src_path))
		
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
	print '  -d, --diff=file       Show diff for file'
	print '  -e, --erase-saved     Erase *.saved backup files'
	print '  -1, --single=file     Update a single file/run single task'
	print '  -r, --ref=file        Show which source file synctool chooses'
	print '  -t, --tasks           Run the scripts in the tasks/ directory'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -F, --fullpath        Show full paths instead of shortened ones'
	print '  -T, --terse           Show terse, shortened paths'
	print '      --color           Use colored output (only for terse mode)'
	print '      --no-color        Do not color output'
	print '      --unix            Output actions as unix shell commands'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '      --version         Print current version number'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that synctool does a dry run unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2003-2011'


def get_options():
	global SINGLE_FILES
	
	progname = os.path.basename(sys.argv[0])
	
	synctool_lib.DRY_RUN = True				# set default dry-run
	
	# check for dangerous common typo's on the command-line
	be_careful_with_getopt()
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:d:1:r:etfFTvq',
			['help', 'conf=', 'diff=', 'single=', 'ref=', 'erase-saved',
			'tasks', 'fix', 'fullpath', 'terse', 'color', 'no-color',
			'verbose', 'quiet', 'unix', 'masterlog', 'version'])
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
	
	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue
		
		if opt == '--version':
			print synctool_param.VERSION
			sys.exit(0)
	
	synctool_config.read_config()
	
	if not synctool_param.TERSE:
		# giving --terse changes program behavior as early as
		# in the get_options() loop itself, so set it here already
		for opt, args in opts:
			if opt in ('-T', '--terse'):
				synctool_param.TERSE = True
				synctool_param.FULL_PATH = False
				continue
			
			if opt in ('-F', '--fullpath'):
				synctool_param.FULL_PATH = True
				continue
	
	# then go process all the other options
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
		if opt in ('-h', '--help', '-?', '-c', '--conf', '-T', '--terse', '-F', '--fullpath', '--version'):
			# already done
			continue
		
# dry run already is default
#
#		if opt in ('-n', '--dry-run'):
#			synctool_lib.DRY_RUN = True
#			continue
		
		if opt in ('-e', '--erase-saved'):
			synctool_lib.ERASE_SAVED = True
			synctool_param.BACKUP_COPIES = False
			continue
		
		if opt in ('-f', '--fix'):
			opt_fix = True
			synctool_lib.DRY_RUN = False
			continue
		
		if opt == '--color':
			synctool_param.COLORIZE = True
			continue
		
		if opt == '--no-color':
			synctool_param.COLORIZE = False
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
			file = synctool_lib.strip_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		if opt in ('-1', '--single'):
			opt_single = True
			file = synctool_lib.strip_path(arg)
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
			file = synctool_lib.strip_path(arg)
			if not file in SINGLE_FILES:
				SINGLE_FILES.append(file)
			continue
		
		stderr("unknown command line option '%s'" % opt)
		errors = errors + 1

	if errors:
		usage()
		sys.exit(1)
	
	option_combinations(opt_diff, opt_single, opt_reference, opt_tasks, opt_upload, opt_suffix, opt_fix)
	
	return action


if __name__ == '__main__':
	action = get_options()
	
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
				terse(synctool_lib.TERSE_DRYRUN, 'not doing any updates')
			else:
				stdout('--fix specified, applying changes')
				terse(synctool_lib.TERSE_FIXING, ' applying changes')
			
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
				run_post(src, single_file)
		
		run_post_on_directories()
	
	else:
		overlay_files()
		delete_files()
		run_post_on_directories()
		always_run()
	
	unix_out('# EOB')
	
	synctool_lib.closelog()


# EOB
