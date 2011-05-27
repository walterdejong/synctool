#
#	synctool_unbuffered.py	WJ110
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_stat
import synctool_lib
import synctool_param


class SyncObject:
	'''a class holding the source path (file in the repository)
	and the destination path (target file on the system).
	The group number denotes the importance of the group.
	The SyncObject caches any stat info'''
	
	# groupnum is really the index of the file's group in MY_GROUPS[]
	# a lower groupnum is more important; negative is invalid/irrelevant group
	
	# stat info is cached so you don't have to call os.stat() all the time
	
	# POST_SCRIPTS uses the same SyncObject class, but interprets src_path
	# as the path of the .post script and dest_path as the destination directory
	# where the script is to be run
	
	def __init__(self, src, dest, groupnum, statbuf1 = None, statbuf2 = None):
		self.src_path = src
		self.src_statbuf = statbuf1
		
		self.dest_path = dest
		self.dest_statbuf = statbuf2
		
		self.groupnum = groupnum
	
	
	def __repr__(self):
		return '[<SyncObject>: (%s) (%s)]' % (self.src_path, self.dest_path)
	
	
	def print_src(self):
		return synctool_lib.prettypath(self.src_path)
	
	
	def print_dest(self):
		return synctool_lib.prettypath(self.dest_path)
	
	
	def src_stat(self):
		'''call os.stat() if needed. Keep the statbuf cached'''
		
		if not self.src_statbuf:
			self.src_statbuf = synctool_stat.SyncStat(self.src_path)
	
	
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
			self.dest_statbuf = synctool_stat.SyncStat(self.dest_path)
	
	
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


# EOB
