#
#   synctool.stat.py    WJ110
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''a SyncStat object is a stat structure with caching'''

import os
import stat
import pwd
import grp
import errno

from synctool.lib import stderr


class SyncStat(object):
    '''structure to hold the relevant fields of a stat() buf'''

    # NB. the reasoning behind keeping a subset of the statbuf is that
    # a subset costs less memory than the real thing
    # However it may be possible that the Python object takes more
    # But then again, this object should take less than the posix.stat_result
    # Python object
    # Also note how I left device files (major, minor) out, they are so rare
    # that they get special treatment in object.py

    def __init__(self, path = None):
        self.entry_exists = False
        self.mode = self.uid = self.gid = self.size = None

        self.stat(path)


    def __repr__(self):
        if self.entry_exists:
            return '[<SyncStat>: %04o %d.%d %d]' % (self.mode, self.uid,
                                                    self.gid, self.size)

        return '[<SyncStat>: None]'


    def stat(self, path):
        '''get the stat() information for a pathname'''

        if not path:
            self.entry_exists = False
            self.mode = self.uid = self.gid = self.size = None
            return

        try:
            statbuf = os.lstat(path)
        except OSError as err:
            # could be something stupid like "Permission denied" ...
            # although synctool should be run as root

            if err.errno != errno.ENOENT:
                # "No such file or directory" is a valid error
                # when the destination is missing
                stderr('error: stat(%s) failed: %s' % (path, err.strerror))

            self.entry_exists = False
            self.mode = self.uid = self.gid = self.size = None

        else:
            self.entry_exists = True

            self.mode = statbuf.st_mode
            self.uid = statbuf.st_uid
            self.gid = statbuf.st_gid
            self.size = statbuf.st_size


    def is_dir(self):
        return (self.entry_exists and stat.S_ISDIR(self.mode))


    def is_file(self):
        return (self.entry_exists and stat.S_ISREG(self.mode))


    def is_link(self):
        return (self.entry_exists and stat.S_ISLNK(self.mode))


    def is_fifo(self):
        return (self.entry_exists and stat.S_ISFIFO(self.mode))


    def is_chardev(self):
        return (self.entry_exists and stat.S_ISCHR(self.mode))


    def is_blockdev(self):
        return (self.entry_exists and stat.S_ISCHR(self.mode))


    def filetype(self):
        return stat.S_IFMT(self.mode)


    def exists(self):
        return self.entry_exists


    def is_exec(self):
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
