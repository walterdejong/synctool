#
#   synctool.stat.py    WJ110
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''a SyncStat object is a stat structure with caching'''

import os
import stat
import errno

from synctool.lib import error
import synctool.pwdgrp


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
        '''initialize instance'''

        self.entry_exists = False
        self.mode = self.uid = self.gid = self.size = None
        self.stat(path)

    def __repr__(self):
        '''return string representation'''

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
                error('stat(%s) failed: %s' % (path, err.strerror))

            self.entry_exists = False
            self.mode = self.uid = self.gid = self.size = None

        else:
            self.entry_exists = True

            self.mode = statbuf.st_mode
            self.uid = statbuf.st_uid
            self.gid = statbuf.st_gid
            self.size = statbuf.st_size

    def is_dir(self):
        '''Returns True if it's a directory'''

        return (self.entry_exists and stat.S_ISDIR(self.mode))

    def is_file(self):
        '''Returns True if it's a regular file'''

        return (self.entry_exists and stat.S_ISREG(self.mode))

    def is_link(self):
        '''Returns True if it's a symbolic link'''

        return (self.entry_exists and stat.S_ISLNK(self.mode))

    def is_fifo(self):
        '''Returns True if it's a FIFO'''

        return (self.entry_exists and stat.S_ISFIFO(self.mode))

    def is_sock(self):
        '''Returns True if it's a socket file'''

        return (self.entry_exists and stat.S_ISSOCK(self.mode))

    def is_chardev(self):
        '''Returns True if it's a character device file'''

        return (self.entry_exists and stat.S_ISCHR(self.mode))

    def is_blockdev(self):
        '''Returns True if it's a block device file'''

        return (self.entry_exists and stat.S_ISCHR(self.mode))

    def filetype(self):
        '''Returns the file type part of the mode'''

        return stat.S_IFMT(self.mode)

    def exists(self):
        '''Returns True if it exists'''

        return self.entry_exists

    def is_exec(self):
        '''Returns True if its mode has any 'x' bit set'''

        return (self.entry_exists and ((self.mode & 0111) != 0))

    def ascii_uid(self):
        '''Returns the username for this uid'''

        if not self.entry_exists:
            raise ValueError()

        return synctool.pwdgrp.pw_name(self.uid)

    def ascii_gid(self):
        '''Returns the group for this gid'''

        if not self.entry_exists:
            raise ValueError()

        return synctool.pwdgrp.grp_name(self.gid)

# EOB
