#
#	synctool.object.py	WJ110
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import shutil
import hashlib

import synctool.lib
from synctool.lib import verbose, stdout, stderr, terse, unix_out, dryrun_msg
import synctool.param
import synctool.syncstat

# size for doing I/O while checksumming files
IO_SIZE = 16 * 1024


class SyncObject:
	'''a class holding the source path (file in the repository)
	and the destination path (target file on the system).
	The group number denotes the importance of the group.
	The SyncObject caches any stat info'''

	# importance is really the index of the file's group in MY_GROUPS[]
	# a lower importance is more important;
	# negative is invalid/irrelevant group

	# stat info is cached so you don't have to call os.stat() all the time

	# POST_SCRIPTS uses the same SyncObject class, but interprets src_path
	# as the path of the .post script and dest_path as the destination
	# directory where the script is to be run

	def __init__(self, src, dest, importance, statbuf1=None, statbuf2=None):
		self.src_path = src
		if not statbuf1:
			self.src_stat = synctool.syncstat.SyncStat(self.src_path)
		else:
			self.src_stat = statbuf1

		self.dest_path = dest
		if not statbuf2:
			self.dest_stat = synctool.syncstat.SyncStat(self.dest_path)
		else:
			self.dest_stat = statbuf2

		self.importance = importance


	def __repr__(self):
		return '[<SyncObject>: (%s) (%s)]' % (self.src_path, self.dest_path)


	def print_src(self):
		return synctool.lib.prettypath(self.src_path)


	def print_dest(self):
		return synctool.lib.prettypath(self.dest_path)


	def compare_files(self):
		'''see what the differences are for this SyncObject, and fix it
		if not a dry run

		self.src_path is the file in the synctool/overlay tree
		self.dest_path is the file in the system

		Return False when file is not changed, True when file is updated'''

		need_update = False

		if self.src_stat.is_link():
			need_update = self._compare_link()

		elif self.src_stat.is_dir():
			need_update = self._compare_dir()

		elif self.src_stat.is_file():
			need_update = self._compare_file()

		elif self.src_stat.is_fifo():
			need_update = self._compare_fifo()

		else:
			# source is not a symbolic link, not a directory,
			# and not a regular file
			stderr("be advised: don't know how to handle %s" % self.src_path)
			terse(synctool.lib.TERSE_WARNING, 'unknown type %s' %
												self.src_path)
			if not self.dest_stat.exists():
				return False

			elif self.dest_stat.is_link():
				stdout('%s should not be a symbolic link' % self.dest_path)
				terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
													self.dest_path)
			elif self.dest_stat.is_dir():
				stdout('%s/ should not be a directory' % self.dest_path)
				terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
													self.dest_path)
			elif self.dest_stat.is_file():
				stdout('%s should not be a regular file' % self.dest_path)
				terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
													self.dest_path)
			elif self.dest_stat.is_fifo():
				stdout('%s should not be a fifo' % self.dest_path)
				terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
													self.dest_path)
			else:
				stderr("don't know how to handle %s" % self.dest_path)
				terse(synctool.lib.TERSE_WARNING, 'unknown type %s' %
													self.dest_path)

		# check mode and owner/group of files and/or directories
		if self.dest_stat.exists():
			if self._compare_ownership():
				need_update = True

			if self._compare_permissions():
				need_update = True

		return need_update


	def _compare_link(self):
		'''compare symbolic link src with dest'''

		need_update = False
		try:
			src_link = os.readlink(self.src_path)
		except OSError, reason:
			stderr('failed to readlink %s : %s' % (self.src_path, reason))
			terse(synctool.lib.TERSE_FAIL, 'readlink %s' % self.src_path)
			return False

		if not self.dest_stat.exists():
			stdout('symbolic link %s does not exist' % self.dest_path)
			terse(synctool.lib.TERSE_LINK, self.dest_path)
			unix_out('# create symbolic link %s' % self.dest_path)
			need_update = True

		elif self.dest_stat.is_link():
			try:
				dest_link = os.readlink(self.dest_path)
			except OSError, reason:
				stderr('failed to readlink %s : %s '
					'(but ignoring this error)' % (self.src_path, reason))
				terse(synctool.lib.TERSE_FAIL, 'readlink %s' % self.src_path)
				dest_link = None

			if src_link != dest_link:
				stdout('%s should point to %s, but points to %s' %
					(self.dest_path, src_link, dest_link))
				terse(synctool.lib.TERSE_LINK, self.dest_path)
				unix_out('# relink symbolic link %s' % self.dest_path)
				need_update = True

		elif self.dest_stat.is_dir():
			stdout('%s/ should be a symbolic link' % self.dest_path)
			terse(synctool.lib.TERSE_LINK, self.dest_path)
			unix_out('# target should be a symbolic link')
			self._save_dir()
			need_update = True

		# treat as file ...
		else:
			stdout('%s should be a symbolic link' % self.dest_path)
			terse(synctool.lib.TERSE_LINK, self.dest_path)
			unix_out('# target should be a symbolic link')
			self.delete_file()
			need_update = True

		# (re)create the symbolic link
		if need_update:
			self._symlink_file(src_link)
			self._set_symlink_ownership()
			self._set_symlink_permissions()
			unix_out('')
			return True

		return False


	def _compare_dir(self):
		'''compare directory src with dest'''

		need_update = False

		if not self.dest_stat.exists():
			stdout('%s/ does not exist' % self.dest_path)
			terse(synctool.lib.TERSE_MKDIR, self.dest_path)
			unix_out('# make directory %s' % self.dest_path)
			need_update = True

		elif self.dest_stat.is_link():
			stdout('%s is a symbolic link, but should be a directory' %
					self.dest_path)
			terse(synctool.lib.TERSE_MKDIR, self.dest_path)
			unix_out('# target should be a directory instead of '
					'a symbolic link')
			self.delete_file()
			need_update = True

		# treat as a regular file
		elif not self.dest_stat.is_dir():
			stdout('%s should be a directory' % self.dest_path)
			terse(synctool.lib.TERSE_MKDIR, self.dest_path)
			unix_out('# target should be a directory')
			self.delete_file()
			need_update = True

		# make the directory
		if need_update:
			self._make_dir()
			self._set_ownership()
			self._set_permissions()
			unix_out('')
			return True

		return False


	def _compare_file(self):
		'''compare file src with dest'''

		need_update = False

		if not self.dest_stat.exists():
			stdout('%s does not exist' % self.dest_path)
			terse(synctool.lib.TERSE_NEW, self.dest_path)
			unix_out('# copy file %s' % self.dest_path)
			need_update = True

		elif self.dest_stat.is_link():
			stdout('%s is a symbolic link, but should not be' %
					self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a file instead of '
				'a symbolic link')
			self.delete_file()
			need_update = True

		elif self.dest_stat.is_dir():
			stdout('%s/ is a directory, but should not be' % self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a file instead of a directory')
			self._save_dir()
			need_update = True

		elif self.dest_stat.is_fifo():
			stdout('%s is a fifo, but should not be' % self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a file instead of a fifo')
			self.delete_file()
			need_update = True

		elif self.dest_stat.is_file():
			# check file size
			if self.src_stat.size != self.dest_stat.size:
				if synctool.lib.DRY_RUN:
					stdout('%s mismatch (file size)' % self.dest_path)
				else:
					stdout('%s updated (file size mismatch)' % self.dest_path)
				terse(synctool.lib.TERSE_SYNC, self.dest_path)
				unix_out('# updating file %s' % self.dest_path)
				need_update = True

			elif self._compare_checksums():
				need_update = True

		else:
			stdout('%s should be a regular file' % self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a regular file')
			need_update = True

		if need_update:
			self._copy_file()
			self._set_ownership()
			self._set_permissions()
			unix_out('')
			return True

		return False


	def _compare_fifo(self):
		'''compare fifo src with dest'''

		need_update = False

		if not self.dest_stat.exists():
			stdout('%s does not exist' % self.dest_path)
			terse(synctool.lib.TERSE_NEW, self.dest_path)
			unix_out('# make fifo %s' % self.dest_path)
			need_update = True

		elif self.dest_stat.is_dir():
			stdout('%s/ should be a fifo' % self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a fifo instead of a directory')
			self._save_dir()
			need_update = True

		else:	# treat as regular file
			stdout('%s should be a fifo' % self.dest_path)
			terse(synctool.lib.TERSE_TYPE, self.dest_path)
			unix_out('# target should be a fifo')
			self.delete_file()
			need_update = True

		if need_update:
			self._make_fifo()
			self._set_ownership()
			self._set_permissions()
			unix_out('')
			return True

		return False


	def _compare_checksums(self):
		'''compare checksum of src and dest'''

		try:
			f1 = open(self.src_path, 'r')
		except IOError, reason:
			stderr('error: failed to open %s : %s' % (self.src_path, reason))
			return False

		sum1 = hashlib.md5()
		sum2 = hashlib.md5()

		with f1:
			try:
				f2 = open(self.dest_path, 'r')
			except IOError, reason:
				stderr('error: failed to open %s : %s' %
						(self.dest_path, reason))
				return False

			with f2:
				ended = False
				while not ended and (sum1.digest() == sum2.digest()):
					try:
						data1 = f1.read(IO_SIZE)
					except IOError, reason:
						stderr('error reading file %s: %s' %
								(self.src_path, reason))
						return False

					if not data1:
						ended = True
					else:
						sum1.update(data1)

					try:
						data2 = f2.read(IO_SIZE)
					except IOError, reason:
						stderr('error reading file %s: %s' %
								(self.dest_path, reason))
						return False

					if not data2:
						ended = True
					else:
						sum2.update(data2)

		if sum1.digest() != sum2.digest():
			if synctool.lib.DRY_RUN:
				stdout('%s mismatch (MD5 checksum)' % (self.dest_path))
			else:
				stdout('%s updated (MD5 mismatch)' % (self.dest_path))

			terse(synctool.lib.TERSE_SYNC, self.dest_path)
			unix_out('# updating file %s' % self.dest_path)
			return True

		return False


	def _compare_ownership(self):
		'''compare ownership of src and dest'''

		if (self.src_stat.uid != self.dest_stat.uid or
			self.src_stat.gid != self.dest_stat.gid):
			owner = self.src_stat.ascii_uid()
			group = self.src_stat.ascii_gid()
			stdout('%s should have owner %s.%s (%d.%d), but has %s.%s '
					'(%d.%d)' % (self.dest_path, owner, group,
					self.src_stat.uid, self.src_stat.gid,
					self.dest_stat.ascii_uid(), self.dest_stat.ascii_gid(),
					self.dest_stat.uid, self.dest_stat.gid))

			terse(synctool.lib.TERSE_OWNER, '%s.%s %s' % (owner, group,
											self.dest_path))
			unix_out('# changing ownership on %s' % self.dest_path)
			self._set_ownership()
			unix_out('')
			return True

		return False


	def _compare_permissions(self):
		'''compare permission bits of src and dest'''

		if self.src_stat.is_link() and not hasattr(os, 'lchmod'):
			# this platform does not support changing the mode
			# of a symbolic link
			# eg. on Linux all symlinks are mode 0777 (weird!)
			return False

		if (self.src_stat.mode & 07777) != (self.dest_stat.mode & 07777):
			stdout('%s should have mode %04o, but has %04o' % (self.dest_path,
					self.src_stat.mode & 07777, self.dest_stat.mode & 07777))
			terse(synctool.lib.TERSE_MODE, '%04o %s' %
											(self.src_stat.mode & 07777,
											self.dest_path))
			unix_out('# changing permissions on %s' % self.dest_path)
			self._set_permissions()
			unix_out('')
			return True

		return False


	def _copy_file(self):
		self._mkdir_basepath()

		src = self.src_path
		dest = self.dest_path

		if self.dest_stat.is_file():		# FIXME backup copies
			unix_out('cp %s %s.saved' % (dest, dest))

		unix_out('cp %s %s' % (src, dest))

		if not synctool.lib.DRY_RUN:
			if synctool.param.BACKUP_COPIES:
				if self.dest_stat.is_file():
					verbose('  saving %s as %s.saved' % (dest, dest))
					try:
						shutil.copy2(dest, '%s.saved' % dest)
					except IOError, reason:
						stderr('failed to save %s as %s.saved: %s' %
								(dest, dest, reason))

			verbose('  cp %s %s' % (src, dest))
			try:
				shutil.copy2(src, dest)			# copy file and stats
			except IOError, reason:
				stderr('failed to copy %s to %s: %s' %
						(self.print_src(), dest, reason))
		else:
			if self.dest_stat.is_file() and synctool.param.BACKUP_COPIES:
				verbose('  saving %s as %s.saved' % (dest, dest))

			verbose(dryrun_msg('  cp %s %s' % (src, dest)))


	def _symlink_file(self, oldpath):
		self._mkdir_basepath()

		# note that old_path is the readlink() of the self.src_path
		newpath = self.dest_path

		# FIXME backup copies
		if self.dest_stat.exists():
			unix_out('mv %s %s.saved' % (newpath, newpath))

		unix_out('ln -s %s %s' % (oldpath, newpath))

		if not synctool.lib.DRY_RUN:
			if self.dest_stat.exists():
				verbose('saving %s as %s.saved' % (newpath, newpath))
				try:
					os.rename(newpath, '%s.saved' % newpath)
				except OSError, reason:
					stderr('failed to save %s as %s.saved : %s' %
							(newpath, newpath, reason))
					terse(synctool.lib.TERSE_FAIL, 'save %s.saved' % newpath)

			verbose('  os.symlink(%s, %s)' % (oldpath, newpath))
			try:
				os.symlink(oldpath, newpath)
			except OSError, reason:
				stderr('failed to create symlink %s -> %s : %s' %
						(newpath, oldpath, reason))
				terse(synctool.lib.TERSE_FAIL, 'link %s' % newpath)

		else:
			verbose(dryrun_msg('  os.symlink(%s, %s)' % (oldpath, newpath)))


	def _make_fifo(self):
		self._mkdir_basepath()

		if self.dest_stat.exists() and synctool.param.BACKUP_COPIES:
			unix_out('mv %s %s.saved' % (self.dest_path, self.dest_path))

		unix_out('mkfifo %s' % self.dest_path)

		if not synctool.lib.DRY_RUN:
			if self.dest_stat.exists() and synctool.param.BACKUP_COPIES:
				verbose('saving %s as %s.saved' % (self.dest_path,
													self.dest_path))
				try:
					os.rename(self.dest_path, '%s.saved' % self.dest_path)
				except OSError, reason:
					stderr('failed to save %s as %s.saved : %s' %
							(self.dest_path, self.dest_path, reason))
					terse(synctool.lib.TERSE_FAIL, 'save %s.saved' %
													self.dest_path)

			verbose('  os.mkfifo(%s)' % self.dest_path)
			try:
				os.mkfifo(self.dest_path)
			except OSError, reason:
				stderr('failed to create fifo %s : %s' % (self.dest_path,
															reason))
				terse(synctool.lib.TERSE_FAIL, 'fifo %s' % self.dest_path)

		else:
			verbose(dryrun_msg('  os.mkfifo(%s)' % self.dest_path))


	def _set_symlink_permissions(self):
		# check if this platform supports lchmod()
		# Linux does not have lchmod: its symlinks are always mode 0777
		if not hasattr(os, 'lchmod'):
			return

		fn = self.dest_path
		mode = self.src_stat.mode

		unix_out('lchmod 0%o %s' % (mode & 07777, fn))

		if not synctool.lib.DRY_RUN:
			verbose('  os.lchmod(%s, %04o)' % (fn, mode & 07777))
			try:
				os.lchmod(fn, mode & 07777)
			except OSError, reason:
				stderr('failed to lchmod %04o %s : %s' %
						(mode & 07777, fn, reason))
		else:
			verbose(dryrun_msg('  os.lchmod(%s, %04o)' % (fn, mode & 07777)))


	def _set_symlink_ownership(self):
		if not hasattr(os, 'lchown'):
			return

		fn = self.dest_path
		uid = self.src_stat.uid
		gid = self.src_stat.gid

		unix_out('lchown %s.%s %s' % (self.src_stat.ascii_uid(),
										self.src_stat.ascii_gid(), fn))

		if not synctool.lib.DRY_RUN:
			verbose('  os.lchown(%s, %d, %d)' % (fn, uid, gid))
			try:
				os.chown(fn, uid, gid)
			except OSError, reason:
				stderr('failed to lchown %s.%s %s : %s' %
						(self.src_stat.ascii_uid(),
						self.src_stat.ascii_gid(), fn, reason))
		else:
			verbose(dryrun_msg('  os.lchown(%s, %d, %d)' % (fn, uid, gid)))


	def _set_permissions(self):
		if self.src_stat.is_link():
			self._set_symlink_permissions()
			return

		fn = self.dest_path
		mode = self.src_stat.mode

		unix_out('chmod 0%o %s' % (mode & 07777, fn))

		if not synctool.lib.DRY_RUN:
			verbose('  os.chmod(%s, %04o)' % (fn, mode & 07777))
			try:
				os.chmod(fn, mode & 07777)
			except OSError, reason:
				stderr('failed to chmod %04o %s : %s' %
						(mode & 07777, fn, reason))
		else:
			verbose(dryrun_msg('  os.chmod(%s, %04o)' % (fn, mode & 07777)))


	def _set_ownership(self):
		if self.src_stat.is_link():
			self._set_symlink_ownership()
			return

		fn = self.dest_path
		uid = self.src_stat.uid
		gid = self.src_stat.gid

		unix_out('chown %s.%s %s' % (self.src_stat.ascii_uid(),
									self.src_stat.ascii_gid(), fn))

		if not synctool.lib.DRY_RUN:
			verbose('  os.chown(%s, %d, %d)' % (fn, uid, gid))
			try:
				os.chown(fn, uid, gid)
			except OSError, reason:
				stderr('failed to chown %s.%s %s : %s' %
						(self.src_stat.ascii_uid(),
						self.src_stat.ascii_gid(), fn, reason))
		else:
			verbose(dryrun_msg('  os.chown(%s, %d, %d)' % (fn, uid, gid)))


	def delete_file(self):
		fn = self.dest_path

		if not synctool.lib.DRY_RUN:
			if synctool.param.BACKUP_COPIES:
				unix_out('mv %s %s.saved' % (fn, fn))

				verbose('moving %s to %s.saved' % (fn, fn))
				try:
					os.rename(file, '%s.saved' % fn)
				except OSError, reason:
					stderr('failed to move file to %s.saved : %s' %
							(fn, reason))
			else:
				unix_out('rm %s' % fn)
				verbose('  os.unlink(%s)' % fn)
				try:
					os.unlink(fn)
				except OSError, reason:
					stderr('failed to delete %s : %s' % (fn, reason))
		else:
			if synctool.param.BACKUP_COPIES:
				verbose(dryrun_msg('moving %s to %s.saved' % (fn, fn)))
			else:
				verbose(dryrun_msg('deleting %s' % fn, 'delete'))


	def hard_delete_file(self):
		fn = self.dest_path

		unix_out('rm -f %s' % fn)

		if not synctool.lib.DRY_RUN:
			verbose('  os.unlink(%s)' % fn)
			try:
				os.unlink(fn)
			except OSError, reason:
				stderr('failed to delete %s : %s' % (fn, reason))
		else:
			verbose(dryrun_msg('deleting %s' % fn, 'delete'))


	def erase_saved(self):
		dest = self.dest_path

		stat_saved_path = synctool.syncstat.SyncStat('%s.saved' % dest)

		if stat_saved_path.exists() and not stat_saved_path.is_dir():
			terse(synctool.lib.TERSE_DELETE, '%s.saved' % dest)
			unix_out('rm %s.saved' % dest)

			if synctool.lib.DRY_RUN:
				stdout(dryrun_msg('erase %s.saved' % dest, 'erase'))
			else:
				stdout('erase %s.saved' % dest)
				verbose('  os.unlink(%s.saved)' % dest)
				try:
					os.unlink('%s.saved' % dest)
				except OSError, reason:
					stderr('failed to delete %s : %s' % (dest, reason))


	def _make_dir(self):
		self._mkdir_basepath()

		path = self.dest_path

		unix_out('mkdir %s' % path)

		if not synctool.lib.DRY_RUN:
			verbose('  os.mkdir(%s)' % path)
			try:
				os.mkdir(path)
			except OSError, reason:
				stderr('failed to make directory %s : %s' % (path, reason))
		else:
			verbose(dryrun_msg('  os.mkdir(%s)' % path))


	def _save_dir(self):
		if not synctool.param.BACKUP_COPIES:
			return

		path = self.dest_path

		unix_out('mv %s %s.saved' % (path, path))

		if not synctool.lib.DRY_RUN:
			verbose('moving %s to %s.saved' % (path, path))
			try:
				os.rename(path, '%s.saved' % path)
			except OSError, reason:
				stderr('failed to move directory to %s.saved : %s' %
						(path, reason))

		else:
			verbose(dryrun_msg('moving %s to %s.saved' % (path, path),
								'move'))


	def _mkdir_basepath(self):
		'''call mkdir -p if the destination directory does not exist yet'''

		if synctool.lib.DRY_RUN:
			return

		# check if the directory exists
		basedir = os.path.dirname(self.dest_path)
		stat = synctool.syncstat.SyncStat(basedir)
		if not stat.exists():
			# create the directory
			verbose('making directory %s' % synctool.lib.prettypath(basedir))
			unix_out('mkdir -p %s' % basedir)
			synctool.lib.mkdir_p(basedir)


# EOB
