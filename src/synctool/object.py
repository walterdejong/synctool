#
#	synctool.object.py	WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import shutil

import synctool.lib
from synctool.lib import verbose,stdout,stderr,terse,unix_out,dryrun_msg
import synctool.param
import synctool.stat


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

	def __init__(self, src, dest, importance, statbuf1 = None,
					statbuf2 = None):
		self.src_path = src
		self.src_statbuf = statbuf1

		self.dest_path = dest
		self.dest_statbuf = statbuf2

		self.importance = importance


	def __repr__(self):
		return '[<SyncObject>: (%s) (%s)]' % (self.src_path, self.dest_path)


	def print_src(self):
		return synctool.lib.prettypath(self.src_path)


	def print_dest(self):
		return synctool.lib.prettypath(self.dest_path)


	def src_stat(self):
		'''call os.stat() if needed. Keep the statbuf cached'''

		if not self.src_statbuf:
			self.src_statbuf = synctool.stat.SyncStat(self.src_path)


	def src_isDir(self):
		self.src_stat()
		return self.src_statbuf.isDir()


	def src_isFile(self):
		self.src_stat()
		return self.src_statbuf.isFile()


	def src_isLink(self):
		self.src_stat()
		return self.src_statbuf.isLink()


	def src_exists(self):
		self.src_stat()
		return self.src_statbuf.exists()


	def src_isExec(self):
		self.src_stat()
		return self.src_statbuf.isExec()


	def src_ascii_uid(self):
		self.src_stat()
		return self.src_statbuf.ascii_uid()


	def src_ascii_gid(self):
		self.src_stat()
		return self.src_statbuf.ascii_gid()


	def dest_stat(self):
		'''call os.stat() if needed. Keep the statbuf cached'''

		if not self.dest_statbuf:
			self.dest_statbuf = synctool.stat.SyncStat(self.dest_path)


	def dest_isDir(self):
		self.dest_stat()
		return self.dest_statbuf.isDir()


	def dest_isFile(self):
		self.dest_stat()
		return self.dest_statbuf.isFile()


	def dest_isLink(self):
		self.dest_stat()
		return self.dest_statbuf.isLink()


	def dest_exists(self):
		self.dest_stat()
		return self.dest_statbuf.exists()


	def dest_isExec(self):
		self.dest_stat()
		return self.dest_statbuf.isExec()


	def dest_ascii_uid(self):
		self.dest_stat()
		return self.dest_statbuf.ascii_uid()


	def dest_ascii_gid(self):
		self.dest_stat()
		return self.dest_statbuf.ascii_gid()


	def compare_files(self):
		'''see what the differences are for this SyncObject, and fix it
		if not a dry run

		self.src_path is the file in the synctool/overlay tree
		self.dest_path is the file in the system

		need_update is a local boolean saying if a path needs to be updated

		Return False when file is not changed, True when file is updated

		--
		The structure of this long function is as follows;

			stat(src)		this stat is 'sacred' and
								dest should be set accordingly
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
			return False'''

		src_path = self.src_path
		dest_path = self.dest_path

		self.src_stat()
		src_stat = self.src_statbuf
		if not src_stat:
			return False

		self.dest_stat()
		dest_stat = self.dest_statbuf
#		if not dest_stat:
#			pass					# destination does not exist

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
				terse(synctool.lib.TERSE_FAIL, 'readlink %s' % src_path)
				return False

			if not dest_stat.exists():
				stdout('symbolic link %s does not exist' % dest_path)
				terse(synctool.lib.TERSE_LINK, dest_path)
				unix_out('# create symbolic link %s' % dest_path)
				need_update = True

			elif dest_stat.isLink():
				try:
					dest_link = os.readlink(dest_path)
				except OSError, reason:
					stderr('failed to readlink %s : %s '
						'(but ignoring this error)' % (src_path, reason))
					terse(synctool.lib.TERSE_FAIL, 'readlink %s' % src_path)
					dest_link = None

				if src_link != dest_link:
					stdout('%s should point to %s, but points to %s' %
						(dest_path, src_link, dest_link))
					terse(synctool.lib.TERSE_LINK, dest_path)
					unix_out('# relink symbolic link %s' % dest_path)
					need_update = True

			elif dest_stat.isDir():
				stdout('%s should be a symbolic link' % dest_path)
				terse(synctool.lib.TERSE_LINK, dest_path)
				unix_out('# target should be a symbolic link')
				self.save_dir()
				need_update = True

			#
			# treat as file ...
			#
			else:
				stdout('%s should be a symbolic link' % dest_path)
				terse(synctool.lib.TERSE_LINK, dest_path)
				unix_out('# target should be a symbolic link')
				need_update = True

			#
			# (re)create the symbolic link
			#
			if need_update:
				self.symlink_file(src_link)
				unix_out('')
				return True

		#
		# if the source is a directory ...
		#
		elif src_stat.isDir():
			if not dest_stat.exists():
				stdout('%s/ does not exist' % dest_path)
				terse(synctool.lib.TERSE_MKDIR, dest_path)
				unix_out('# make directory %s' % dest_path)
				need_update = True

			elif dest_stat.isLink():
				stdout('%s is a symbolic link, but should be a directory' %
					dest_path)
				terse(synctool.lib.TERSE_MKDIR, dest_path)
				unix_out('# target should be a directory instead of '
					'a symbolic link')
				self.delete_file()
				need_update = True

			#
			# treat as a regular file
			#
			elif not dest_stat.isDir():
				stdout('%s should be a directory' % dest_path)
				terse(synctool.lib.TERSE_MKDIR, dest_path)
				unix_out('# target should be a directory')
				self.delete_file()
				need_update = True

			#
			# make the directory
			#
			if need_update:
				self.make_dir()
				self.set_owner()
				self.set_permissions()
				unix_out('')
				return True

		#
		# if source is a file ...
		#
		elif src_stat.isFile():
			if not dest_stat.exists():
				stdout('%s does not exist' % dest_path)
				terse(synctool.lib.TERSE_NEW, dest_path)
				unix_out('# copy file %s' % dest_path)
				need_update = True

			elif dest_stat.isLink():
				stdout('%s is a symbolic link, but should not be' % dest_path)
				terse(synctool.lib.TERSE_TYPE, dest_path)
				unix_out('# target should be a file instead of '
					'a symbolic link')
				self.delete_file()
				need_update = True

			elif dest_stat.isDir():
				stdout('%s is a directory, but should not be' % dest_path)
				terse(synctool.lib.TERSE_TYPE, dest_path)
				unix_out('# target should be a file instead of a directory')
				self.save_dir()
				need_update = True

			#
			# check file size
			#
			elif dest_stat.isFile():
				if src_stat.size != dest_stat.size:
					if synctool.lib.DRY_RUN:
						stdout('%s mismatch (file size)' % dest_path)
					else:
						stdout('%s updated (file size mismatch)' % dest_path)
					terse(synctool.lib.TERSE_SYNC, dest_path)
					unix_out('# updating file %s' % dest_path)
					need_update = True
				else:
					#
					# check file contents (SHA1 or MD5 checksum)
					#
					try:
						src_sum, dest_sum = synctool.lib.checksum_files(
											src_path, dest_path)
					except IOError, (err, reason):
# error was already printed
#						stderr('error: %s' % reason)
						return False

					if src_sum != dest_sum:
						if synctool.lib.DRY_RUN:
#							stdout('%s mismatch (SHA1 checksum)' % dest_path)
							stdout('%s mismatch (MD5 checksum)' % dest_path)
						else:
#							stdout('%s updated (SHA1 mismatch)' % dest_path)
							stdout('%s updated (MD5 mismatch)' % dest_path)

						terse(synctool.lib.TERSE_SYNC, dest_path)
						unix_out('# updating file %s' % dest_path)
						need_update = True

			else:
				stdout('%s should be a regular file' % dest_path)
				terse(synctool.lib.TERSE_TYPE, dest_path)
				unix_out('# target should be a regular file')
				need_update = True

			if need_update:
				self.copy_file()
				self.set_owner()
				self.set_permissions()
				unix_out('')
				return True

		else:
			# source is not a symbolic link, not a directory,
			# and not a regular file
			stderr("be advised: don't know how to handle %s" % src_path)
			terse(synctool.lib.TERSE_WARNING, 'unknown type %s' % src_path)

			if not dest_stat.exists():
				return False

			if dest_stat.isLink():
				stdout('%s should not be a symbolic link' % dest_path)
				terse(synctool.lib.TERSE_WARNING, 'wrong type %s' % dest_path)
			else:
				if dest_stat.isDir():
					stdout('%s should not be a directory' % dest_path)
					terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
														dest_path)
				else:
					if dest_stat.isFile():
						stdout('%s should not be a regular file' % dest_path)
						terse(synctool.lib.TERSE_WARNING, 'wrong type %s' %
															dest_path)
					else:
						stderr("don't know how to handle %s" % dest_path)
						terse(synctool.lib.TERSE_WARNING, 'unknown type %s' %
															dest_path)

		#
		# check mode and owner/group of files and/or directories
		#
		# os.chmod() and os.chown() don't work well with symbolic links
		# as they work on the destination rather than the symlink itself
		# python lacks an os.lchmod() and os.lchown(), they are not portable
		# anyway, symbolic links have been dealt with already ...
		#
		if dest_stat.exists() and not dest_stat.isLink():
			if src_stat.uid != dest_stat.uid or src_stat.gid != dest_stat.gid:
				owner = src_stat.ascii_uid()
				group = src_stat.ascii_gid()
				stdout('%s should have owner %s.%s (%d.%d), '
					'but has %s.%s (%d.%d)' % (dest_path, owner, group,
					src_stat.uid, src_stat.gid,
					dest_stat.ascii_uid(), dest_stat.ascii_gid(),
					dest_stat.uid, dest_stat.gid))

				terse(synctool.lib.TERSE_OWNER, '%s.%s %s' %
												(owner, group, dest_path))
				unix_out('# changing ownership on %s' % dest_path)

				self.set_owner()

				unix_out('')
				need_update = True

			if (src_stat.mode & 07777) != (dest_stat.mode & 07777):
				stdout('%s should have mode %04o, but has %04o' %
						(dest_path,
						src_stat.mode & 07777,
						dest_stat.mode & 07777))
				terse(synctool.lib.TERSE_MODE, '%04o %s' %
												(src_stat.mode & 07777,
												dest_path))
				unix_out('# changing permissions on %s' % dest_path)

				self.set_permissions()

				unix_out('')
				need_update = True

#			if src_stat.st_mtime != dest_stat.st_mtime:
#				stdout('%s should have mtime %d, but has %d' %
#						(dest_path, src_stat.st_mtime, dest_stat.st_mtime))
#			if src_stat[stat.st_ctime != dest_stat.st_ctime:
#				stdout('%s should have ctime %d, but has %d' %
#						(dest_path, src_stat.st_ctime, dest_stat.st_ctime))

		return need_update


	def copy_file(self):
		self.mkdir_basepath()

		src = self.src_path
		dest = self.dest_path

		if self.dest_isFile():
			unix_out('cp %s %s.saved' % (dest, dest))

		unix_out('umask 077')
		unix_out('cp %s %s' % (src, dest))

		if not synctool.lib.DRY_RUN:
			old_umask = os.umask(077)

			if synctool.param.BACKUP_COPIES:
				if self.dest_isFile():
					verbose('  saving %s as %s.saved' % (dest, dest))
					try:
						shutil.copy2(dest, '%s.saved' % dest)
					except:
						stderr('failed to save %s as %s.saved' % (dest, dest))

			verbose('  cp %s %s' % (src, dest))
			try:
				shutil.copy2(src, dest)			# copy file and stats
			except:
				stderr('failed to copy %s to %s' % (self.print_src(), dest))

			os.umask(old_umask)
		else:
			if self.dest_isFile() and synctool.param.BACKUP_COPIES:
				verbose('  saving %s as %s.saved' % (dest, dest))

			verbose(dryrun_msg('  cp %s %s' % (src, dest)))


	def symlink_file(self, oldpath):
		self.mkdir_basepath()

		# note that old_path is the readlink() of the self.src_path
		newpath = self.dest_path

		if self.dest_exists():
			unix_out('mv %s %s.saved' % (newpath, newpath))

		# symlinks are created using the default umask
		# on Linux, the mode of symlinks is always 0777 (weird!)
		# on other platforms, it gets a mode according to umask

		# if we want the ownership of the symlink to be correct,
		# we should do setuid() here
		# matching ownerships of symbolic links is not yet implemented

		unix_out('ln -s %s %s' % (oldpath, newpath))

		if not synctool.lib.DRY_RUN:
			if self.dest_exists():
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


	def set_permissions(self):
		file = self.dest_path
		mode = self.src_statbuf.mode

		unix_out('chmod 0%o %s' % (mode & 07777, file))

		if not synctool.lib.DRY_RUN:
			verbose('  os.chmod(%s, %04o)' % (file, mode & 07777))
			try:
				os.chmod(file, mode & 07777)
			except OSError, reason:
				stderr('failed to chmod %04o %s : %s' %
						(mode & 07777, file, reason))
		else:
			verbose(dryrun_msg('  os.chmod(%s, %04o)' % (file, mode & 07777)))


	def set_owner(self):
		file = self.dest_path
		uid = self.src_statbuf.uid
		gid = self.src_statbuf.gid

		unix_out('chown %s.%s %s' % (self.src_ascii_uid(),
									self.src_ascii_gid(), file))

		if not synctool.lib.DRY_RUN:
			verbose('  os.chown(%s, %d, %d)' % (file, uid, gid))
			try:
				os.chown(file, uid, gid)
			except OSError, reason:
				stderr('failed to chown %s.%s %s : %s' %
						(self.src_ascii_uid(), self.src_ascii_gid(),
						file, reason))
		else:
			verbose(dryrun_msg('  os.chown(%s, %d, %d)' % (file, uid, gid)))


	def delete_file(self):
		file = self.dest_path

		if not synctool.lib.DRY_RUN:
			if synctool.param.BACKUP_COPIES:
				unix_out('mv %s %s.saved' % (file, file))

				verbose('moving %s to %s.saved' % (file, file))
				try:
					os.rename(file, '%s.saved' % file)
				except OSError, reason:
					stderr('failed to move file to %s.saved : %s' %
							(file, reason))
			else:
				unix_out('rm %s' % file)
				verbose('  os.unlink(%s)' % file)
				try:
					os.unlink(file)
				except OSError, reason:
					stderr('failed to delete %s : %s' %
							(file, reason))
		else:
			if synctool.param.BACKUP_COPIES:
				verbose(dryrun_msg('moving %s to %s.saved' % (file, file)))
			else:
				verbose(dryrun_msg('deleting %s' % file, 'delete'))


	def hard_delete_file(self):
		file = self.dest_path

		unix_out('rm -f %s' % file)

		if not synctool.lib.DRY_RUN:
			verbose('  os.unlink(%s)' % file)
			try:
				os.unlink(file)
			except OSError, reason:
				stderr('failed to delete %s : %s' % (file, reason))
		else:
			verbose(dryrun_msg('deleting %s' % file, 'delete'))


	def erase_saved(self):
		dest = self.dest_path

		stat_saved_path = synctool.stat.SyncStat('%s.saved' % dest)

		if stat_saved_path.exists() and not stat_saved_path.isDir():
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


	def make_dir(self):
		self.mkdir_basepath()

		path = self.dest_path

		unix_out('umask 077')
		unix_out('mkdir %s' % path)

		if not synctool.lib.DRY_RUN:
			old_umask = os.umask(077)

			verbose('  os.mkdir(%s)' % path)
			try:
				os.mkdir(path)
			except OSError, reason:
				stderr('failed to make directory %s : %s' % (path, reason))

			os.umask(old_umask)
		else:
			verbose(dryrun_msg('  os.mkdir(%s)' % path))


	def save_dir(self):
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


	def mkdir_basepath(self):
		'''call mkdir -p if the destination directory does not exist yet'''

		if synctool.lib.DRY_RUN:
			return

		# check if the directory exists
		basedir = os.path.dirname(self.dest_path)
		stat = synctool.stat.SyncStat(basedir)
		if not stat.exists():
			# create the directory
			verbose('making directory %s' % synctool.lib.prettypath(basedir))
			unix_out('mkdir -p %s' % basedir)
			synctool.lib.mkdir_p(basedir)

# EOB
