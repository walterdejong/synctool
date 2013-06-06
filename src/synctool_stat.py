#
#	synctool_unbuffered.py	WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

from synctool_lib import stderr

import os
import stat
import pwd
import grp
import errno


class SyncStat:
	'''structure to hold the relevant fields of a stat() buf'''

	# NB. the reasoning behind keeping a subset of the statbuf is that
	# a subset costs less memory than the real thing
	# However it may be possible that the Python object takes more
	# But then again, this object should take less than the posix.stat_result
	# Python object

	def __init__(self, path = None):
		self.stat(path)


	def __repr__(self):
		if self.entry_exists:
			return '[<SyncStat>: %04o %d.%d %d]' % (self.mode, self.uid, self.gid, self.size)

		return '[<SyncStat>: None]'


	def stat(self, path):
		'''get the stat() information for a pathname'''

		if not path:
			self.entry_exists = False
			self.mode = self.uid = self.gid = self.size = None
			return

		try:
			statbuf = os.lstat(path)
		except OSError, err:
			# could be something stupid like "Permission denied" ...
			# although synctool should be run as root

			if err.errno != errno.ENOENT:
				# "No such file or directory" is a valid error
				# when the destination is missing
				stderr('error: stat(%s) failed: %s' % (path, reason))

			self.entry_exists = False
			self.mode = self.uid = self.gid = self.size = None

		else:
			self.entry_exists = True

			# use older stat.ST_xxx notation for older Python versions ...
			self.mode = statbuf[stat.ST_MODE]
			self.uid = statbuf[stat.ST_UID]
			self.gid = statbuf[stat.ST_GID]
			self.size = statbuf[stat.ST_SIZE]


	def isDir(self):
		return (self.entry_exists and stat.S_ISDIR(self.mode))


	def isFile(self):
		return (self.entry_exists and stat.S_ISREG(self.mode))


	def isLink(self):
		return (self.entry_exists and stat.S_ISLNK(self.mode))


	def exists(self):
		return self.entry_exists


	def isExec(self):
		return (self.entry_exists and ((self.mode & 0111) != 0))


	def ascii_uid(self):
		'''get the name for this uid'''

		if not self.entry_exists:
			return None

		try:
			entry = pwd.getpwuid(self.uid)
			return entry[0]

		except KeyError:
			pass

		return '%d' % self.uid


	def ascii_gid(self):
		'''get the name for this gid'''

		if not self.entry_exists:
			return None

		try:
			entry = grp.getgrgid(self.gid)
			return entry[0]

		except KeyError:
			pass

		return '%d' % self.gid


# EOB
