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


class SyncStat:
    '''structure to hold the relevant fields of a stat() buf'''

    # NB. the reasoning behind keeping a subset of the statbuf is that
    # a subset costs less memory than the real thing
    # However it may be possible that the Python object takes more
    # But then again, should take less than the posix.stat_result Pyobject
    # Also note how I left device files (major, minor) out, they are so rare
    # that they get special treatment in object.py

    def __init__(self, path=''):
        # type: (str) -> None
        '''initialize instance'''

        self.entry_exists = False
        self.mode = 0
        self.uid = self.gid = -1
        self.size = -1
        self.atime = self.mtime = 0
        self.stat(path)

    def __repr__(self):
        # type: () -> str
        '''return string representation'''

        if self.entry_exists:
            return '[<SyncStat>: %04o %d.%d %d]' % (self.mode, self.uid,
                                                    self.gid, self.size)

        return '[<SyncStat>: None]'

    def stat(self, path):
        # type: (str) -> None
        '''get the stat() information for a pathname'''

        if not path:
            self.entry_exists = False
            self.mode = 0
            self.uid = self.gid = -1
            self.size = 0
            self.atime = self.mtime = 0
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
            self.mode = 0
            self.uid = self.gid = -1
            self.size = 0
            self.atime = self.mtime = 0

        else:
            self.entry_exists = True
            self.mode = statbuf.st_mode
            self.uid = statbuf.st_uid
            self.gid = statbuf.st_gid
            self.size = statbuf.st_size
            # Note that statbuf times are float values (!)
            # trunc to an integer value
            self.atime = int(statbuf.st_atime)
            self.mtime = int(statbuf.st_mtime)

    def is_dir(self):
        # type: () -> bool
        ''' Returns True if it is a directory'''

        return (self.entry_exists and stat.S_ISDIR(self.mode))

    def is_file(self):
        # type: () -> bool
        '''Returns True if it's a regular file'''

        return self.entry_exists and stat.S_ISREG(self.mode)

    def is_link(self):
        # type: () -> bool
        '''Returns True if it's a symbolic link'''

        return self.entry_exists and stat.S_ISLNK(self.mode)

    def is_fifo(self):
        # type: () -> bool
        '''Returns True if it's a FIFO'''

        return self.entry_exists and stat.S_ISFIFO(self.mode)

    def is_sock(self):
        # type: () -> bool
        '''Returns True if it's a socket file'''

        return self.entry_exists and stat.S_ISSOCK(self.mode)

    def is_chardev(self):
        # type: () -> bool
        '''Returns True if it's a character device file'''

        return self.entry_exists and stat.S_ISCHR(self.mode)

    def is_blockdev(self):
        # type: () -> bool
        '''Returns True if it's a block device file'''

        return self.entry_exists and stat.S_ISCHR(self.mode)

    def filetype(self):
        # type: () -> int
        '''Returns the file type part of the mode'''

        return stat.S_IFMT(self.mode)

    def exists(self):
        # type: () -> bool
        '''Returns True if it exists'''

        return self.entry_exists

    def is_exec(self):
        # type: () -> bool
        '''Returns True if its mode has any 'x' bit set'''

        return self.entry_exists and ((self.mode & 0o111) != 0)

    def ascii_uid(self):
        # type: () -> str
        '''Returns the username for this uid'''

        if not self.entry_exists:
            raise ValueError()

        return synctool.pwdgrp.pw_name(self.uid)

    def ascii_gid(self):
        # type: () -> str
        '''Returns the group for this gid'''

        if not self.entry_exists:
            raise ValueError()

        return synctool.pwdgrp.grp_name(self.gid)

# EOB
