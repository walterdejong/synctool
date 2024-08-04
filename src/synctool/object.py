#
#   synctool.object.py    WJ110
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''a SyncObject is a source file + matching destination path and attributes'''

import os
import stat
import datetime
import shutil
import hashlib

from typing import Dict, Optional

import synctool.lib
from synctool.lib import verbose, stdout, error, terse, unix_out, log
from synctool.lib import dryrun_msg, prettypath, TERSE_FAIL, print_timestamp
import synctool.param
import synctool.syncstat

try:
    import posix
    SyncStat = synctool.syncstat.SyncStat
except ImportError:
    pass

# size for doing I/O while checksumming files
IO_SIZE = 16 * 1024


class VNode:
    '''base class for doing actions with directory entries'''

    def __init__(self, filename, statbuf, exists):
        # type: (str, SyncStat, bool) -> None
        '''filename is typically destination path
        statbuf is source statbuf
        exists is boolean whether dest path already exists
        '''

        self.name = filename
        self.stat = statbuf
        self.exists = exists

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return '(unknown file type)'

    def move_saved(self):
        # type: () -> None
        '''move existing entry to .saved'''

        # do not save files that already are .saved
        _, ext = os.path.splitext(self.name)
        if ext == '.saved':
            return

        verbose(dryrun_msg('saving %s as %s.saved' % (self.name, self.name)))
        unix_out('mv %s %s.saved' % (self.name, self.name))

        if not synctool.lib.DRY_RUN:
            verbose('  os.rename(%s, %s.saved)' % (self.name, self.name))
            try:
                os.rename(self.name, '%s.saved' % self.name)
            except OSError as err:
                error('failed to save %s as %s.saved : %s' % (self.name,
                                                              self.name,
                                                              err.strerror))
                terse(TERSE_FAIL, 'save %s.saved' % self.name)

    def harddelete(self):
        # type: () -> None
        '''delete existing entry'''

        if synctool.lib.DRY_RUN:
            not_str = 'not '
        else:
            not_str = ''

        stdout('%sdeleting %s' % (not_str, self.name))
        unix_out('rm %s' % self.name)
        terse(synctool.lib.TERSE_DELETE, self.name)

        if not synctool.lib.DRY_RUN:
            verbose('  os.unlink(%s)' % self.name)
            try:
                os.unlink(self.name)
            except OSError as err:
                error('failed to delete %s : %s' % (self.name, err.strerror))
                terse(TERSE_FAIL, 'delete %s' % self.name)
            else:
                log('deleted %s' % self.name)

    def quiet_delete(self):
        # type: () -> None
        '''silently delete existing entry; only called by fix()'''

        if not synctool.lib.DRY_RUN and not synctool.param.BACKUP_COPIES:
            verbose('  os.unlink(%s)' % self.name)
            try:
                os.unlink(self.name)
            except OSError:
                pass

    def mkdir_basepath(self):
        # type: () -> None
        '''call mkdir -p to create leading path'''

        if synctool.lib.DRY_RUN:
            return

        basedir = os.path.dirname(self.name)

        # be a bit quiet about it
        if synctool.lib.VERBOSE or synctool.lib.UNIX_CMD:
            verbose('making directory %s' % prettypath(basedir))

        synctool.lib.mkdir_p(basedir)

    def compare(self, _src_path, _dest_stat):
        # type: (str, SyncStat) -> bool
        '''compare content
        Return True when same, False when different
        '''

        return True

    def create(self):
        # type: () -> None
        '''create a new entry'''

    def fix(self):
        # type: () -> None
        '''repair the existing entry
        set owner and permissions equal to source
        '''

        if self.exists:
            if synctool.param.BACKUP_COPIES:
                self.move_saved()
            else:
                self.quiet_delete()

        self.mkdir_basepath()
        self.create()
        self.set_owner()
        self.set_permissions()
        if synctool.param.SYNC_TIMES:
            self.set_times()

    def set_owner(self):
        # type: () -> None
        '''set ownership equal to source'''

        verbose(dryrun_msg('  os.chown(%s, %d, %d)' %
                           (self.name, self.stat.uid, self.stat.gid)))
        unix_out('chown %s.%s %s' % (self.stat.ascii_uid(),
                                     self.stat.ascii_gid(), self.name))
        if not synctool.lib.DRY_RUN:
            try:
                os.chown(self.name, self.stat.uid, self.stat.gid)
            except OSError as err:
                error('failed to chown %s.%s %s : %s' %
                      (self.stat.ascii_uid(), self.stat.ascii_gid(),
                       self.name, err.strerror))
                terse(TERSE_FAIL, 'owner %s' % self.name)

    def set_permissions(self):
        # type: () -> None
        '''set access permission bits equal to source'''

        verbose(dryrun_msg('  os.chmod(%s, %04o)' %
                           (self.name, self.stat.mode & 0o7777)))
        unix_out('chmod 0%o %s' % (self.stat.mode & 0o7777, self.name))
        if not synctool.lib.DRY_RUN:
            try:
                os.chmod(self.name, self.stat.mode & 0o7777)
            except OSError as err:
                error('failed to chmod %04o %s : %s' %
                      (self.stat.mode & 0o7777, self.name, err.strerror))
                terse(TERSE_FAIL, 'mode %s' % self.name)

    def set_times(self):
        # type: () -> None
        '''set access and modification times'''

        # only mtime is shown
        verbose(dryrun_msg('  os.utime(%s, %s)' %
                           (self.name, print_timestamp(self.stat.mtime))))
        # print timestamp in other format
        datet = datetime.datetime.fromtimestamp(self.stat.mtime)
        time_str = datet.strftime('%Y%m%d%H%M.%S')
        unix_out('touch -t %s %s' % (time_str, self.name))
        if not synctool.lib.DRY_RUN:
            try:
                os.utime(self.name, (self.stat.atime, self.stat.mtime))
            except OSError as err:
                error('failed to set utime on %s : %s' % (self.name,
                                                          err.strerror))
                terse(TERSE_FAIL, 'utime %s' % self.name)



class VNodeFile(VNode):
    '''vnode for a regular file'''

    def __init__(self, filename, statbuf, exists, src_path):
        # type: (str, SyncStat, bool, str) -> None
        '''initialize instance'''

        super().__init__(filename, statbuf, exists)
        self.src_path = src_path

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'regular file'

    def compare(self, src_path, dest_stat):
        # type: (str, SyncStat) -> bool
        '''see if files are the same
        Return True if the same
        '''

        if self.stat.size != dest_stat.size:
            if synctool.lib.DRY_RUN:
                stdout('%s mismatch (file size)' % self.name)
            else:
                stdout('%s updated (file size mismatch)' % self.name)
            terse(synctool.lib.TERSE_SYNC, self.name)
            unix_out('# updating file %s' % self.name)
            return False

        return self._compare_checksums(src_path)

    def _compare_checksums(self, src_path):
        # type: (str) -> bool
        '''compare checksum of src_path and dest: self.name
        Return True if the same'''

        try:
            ffile1 = open(src_path, 'rb')
        except OSError as err:
            error('failed to open %s : %s' % (src_path, err.strerror))
            # return True because we can't fix an error in src_path
            return True

        sum1 = hashlib.md5()
        sum2 = hashlib.md5()

        with ffile1:
            try:
                ffile2 = open(self.name, 'rb')
            except OSError as err:
                error('failed to open %s : %s' % (self.name, err.strerror))
                return False

            with ffile2:
                ended = False
                while not ended and (sum1.digest() == sum2.digest()):
                    try:
                        data1 = ffile1.read(IO_SIZE)
                    except OSError as err:
                        error('failed to read file %s: %s' % (src_path,
                                                              err.strerror))
                        return False

                    if not data1:
                        ended = True
                    else:
                        sum1.update(data1)

                    try:
                        data2 = ffile2.read(IO_SIZE)
                    except OSError as err:
                        error('failed to read file %s: %s' % (self.name,
                                                              err.strerror))
                        return False

                    if not data2:
                        ended = True
                    else:
                        sum2.update(data2)

        if sum1.digest() != sum2.digest():
            if synctool.lib.DRY_RUN:
                stdout('%s mismatch (MD5 checksum)' % self.name)
            else:
                stdout('%s updated (MD5 mismatch)' % self.name)

            unix_out('# updating file %s' % self.name)
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self):
        # type: () -> None
        '''copy file'''

        if not self.exists:
            terse(synctool.lib.TERSE_NEW, self.name)

        verbose(dryrun_msg('  copy %s %s' % (self.src_path, self.name)))
        unix_out('cp %s %s' % (self.src_path, self.name))
        if not synctool.lib.DRY_RUN:
            try:
                # copy file
                shutil.copy(self.src_path, self.name)
            except OSError as err:
                error('failed to copy %s to %s: %s' %
                      (prettypath(self.src_path), self.name, err.strerror))
                terse(TERSE_FAIL, self.name)



class VNodeDir(VNode):
    '''vnode for a directory'''

#    def __init__(self, filename, statbuf, exists):
#        # type: (str, SyncStat, bool) -> None
#        '''initialize instance'''
#
#        super(VNodeDir, self).__init__(filename, statbuf, exists)

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'directory'

    def create(self):
        # type: () -> None
        '''create directory'''

        if synctool.lib.path_exists(self.name):
            # it can happen that the dir already exists
            # due to recursion in visit() + VNode.mkdir_basepath()
            # So this is double checked for dirs that did not exist
            return

        verbose(dryrun_msg('  os.mkdir(%s)' % self.name))
        unix_out('mkdir %s' % self.name)
        terse(synctool.lib.TERSE_MKDIR, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mkdir(self.name, self.stat.mode & 0o7777)
            except OSError as err:
                error('failed to make directory %s : %s' % (self.name,
                                                            err.strerror))
                terse(TERSE_FAIL, 'mkdir %s' % self.name)

    def harddelete(self):
        # type: () -> None
        '''delete directory'''

        if synctool.lib.DRY_RUN:
            not_str = 'not '
        else:
            not_str = ''

        stdout('%sremoving %s' % (not_str, self.name + os.sep))
        unix_out('rmdir %s' % self.name)
        terse(synctool.lib.TERSE_DELETE, self.name + os.sep)
        if not synctool.lib.DRY_RUN:
            verbose('  os.rmdir(%s)' % self.name)
            try:
                os.rmdir(self.name)
            except OSError:
                # probably directory not empty
                # refuse to delete dir, just move it aside
                verbose('refusing to delete directory %s' % self.name)
                self.move_saved()

    def quiet_delete(self):
        # type: () -> None
        '''silently delete directory; only called by fix()'''

        if not synctool.lib.DRY_RUN and not synctool.param.BACKUP_COPIES:
            verbose('  os.rmdir(%s)' % self.name)
            try:
                os.rmdir(self.name)
            except OSError:
                # probably directory not empty
                # refuse to delete dir, just move it aside
                verbose('refusing to delete directory %s' % self.name)
                self.move_saved()

    def set_times(self):
        # type: () -> None
        '''set access and modification times'''

        # Note: should we raise RuntimeError here?



class VNodeLink(VNode):
    '''vnode for a symbolic link'''

    def __init__(self, filename, statbuf, exists, oldpath):
        # type: (str, SyncStat, bool, str) -> None
        '''initialize instance'''

        super().__init__(filename, statbuf, exists)
        self.oldpath = oldpath

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'symbolic link'

    def compare(self, _src_path, _dest_stat):
        # type: (str, SyncStat) -> bool
        '''compare symbolic links'''

        if not self.exists:
            return False

        try:
            link_to = os.readlink(self.name)
        except OSError as err:
            error('failed to read symlink %s : %s' % (self.name,
                                                      err.strerror))
            return False

        if self.oldpath != link_to:
            stdout('%s should point to %s, but points to %s' %
                   (self.name, self.oldpath, link_to))
            terse(synctool.lib.TERSE_LINK, self.name)
            return False

        return True

    def create(self):
        # type: () -> None
        '''create symbolic link'''

        verbose(dryrun_msg('  os.symlink(%s, %s)' % (self.oldpath,
                                                     self.name)))
        unix_out('ln -s %s %s' % (self.oldpath, self.name))
        terse(synctool.lib.TERSE_LINK, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.symlink(self.oldpath, self.name)
            except OSError as err:
                error('failed to create symlink %s -> %s : %s' %
                      (self.name, self.oldpath, err.strerror))
                terse(TERSE_FAIL, 'link %s' % self.name)

    def set_owner(self):
        # type: () -> None
        '''set ownership of symlink'''

        if not hasattr(os, 'lchown'):
            # you never know
            return

        verbose(dryrun_msg('  os.lchown(%s, %d, %d)' %
                           (self.name, self.stat.uid, self.stat.gid)))
        unix_out('lchown %s.%s %s' % (self.stat.ascii_uid(),
                                      self.stat.ascii_gid(), self.name))
        if not synctool.lib.DRY_RUN:
            try:
                os.lchown(self.name, self.stat.uid, self.stat.gid)
            except OSError as err:
                error('failed to lchown %s.%s %s : %s' %
                      (self.stat.ascii_uid(), self.stat.ascii_gid(),
                       self.name, err.strerror))
                terse(TERSE_FAIL, 'owner %s' % self.name)

    def set_permissions(self):
#pylint: disable=no-member
        # type: () -> None
        '''set permissions of symlink (if possible)'''

        # check if this platform supports lchmod()
        # Linux does not have lchmod: its symlinks are always mode 0777
        if not hasattr(os, 'lchmod'):
            return

        verbose(dryrun_msg('  os.lchmod(%s, %04o)' %
                           (self.name, self.stat.mode & 0o7777)))
        unix_out('lchmod 0%o %s' % (self.stat.mode & 0o7777, self.name))
        if not synctool.lib.DRY_RUN:
            try:
                os.lchmod(self.name, self.stat.mode & 0o7777)
            except OSError as err:
                error('failed to lchmod %04o %s : %s' %
                      (self.stat.mode & 0o7777, self.name, err.strerror))
                terse(TERSE_FAIL, 'mode %s' % self.name)

    def set_times(self):
        # type: () -> None
        '''set access and modification times'''

        # Note: should we raise RuntimeError here?



class VNodeFifo(VNode):
    '''vnode for a fifo'''

#    def __init__(self, filename, statbuf, exists):
#        # type: (str, SyncStat, bool) -> None
#        '''initialize instance'''
#
#        super(VNodeFifo, self).__init__(filename, statbuf, exists)

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'fifo'

    def create(self):
        # type: () -> None
        '''make a fifo'''

        verbose(dryrun_msg('  os.mkfifo(%s)' % self.name))
        unix_out('mkfifo %s' % self.name)
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mkfifo(self.name, self.stat.mode & 0o777)
            except OSError as err:
                error('failed to create fifo %s : %s' % (self.name,
                                                         err.strerror))
                terse(TERSE_FAIL, 'fifo %s' % self.name)



class VNodeChrDev(VNode):
    '''vnode for a character device file'''

    def __init__(self, filename, syncstat_obj, exists, src_stat):
        # type: (str, SyncStat, bool, posix.stat_result) -> None
        '''initialize instance'''

        super().__init__(filename, syncstat_obj, exists)
        self.src_stat = src_stat

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'character device file'

    def compare(self, _src_path, dest_stat):
        # type: (str, SyncStat) -> bool
        '''see if devs are the same'''

        if not self.exists:
            return False

        # dest_stat is a SyncStat object and it's useless here
        # I need a real, fresh statbuf that includes st_rdev field
        try:
            dest_stat = os.lstat(self.name)             # type: ignore
        except OSError as err:
            error('error checking %s : %s' % (self.name, err.strerror))
            return False

        # Note: mypy triggers false errors here
        # Also, no luck with Union[SyncStat, posix.stat_result]
        # In any case, for VNodeChrDev and VNodeBlkDev,
        # the self.src_stat is of type posix.stat_result
        src_major = os.major(self.src_stat.st_rdev)     # type: ignore
        src_minor = os.minor(self.src_stat.st_rdev)     # type: ignore
        dest_major = os.major(dest_stat.st_rdev)        # type: ignore
        dest_minor = os.minor(dest_stat.st_rdev)        # type: ignore
        if src_major != dest_major or src_minor != dest_minor:
            stdout('%s should have major,minor %d,%d but has %d,%d' %
                   (self.name, src_major, src_minor, dest_major, dest_minor))
            unix_out('# updating major,minor %s' % self.name)
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self):
        # type: () -> None
        '''make a character device file'''

        major = os.major(self.src_stat.st_rdev)         # type: ignore
        minor = os.minor(self.src_stat.st_rdev)         # type: ignore
        verbose(dryrun_msg('  os.mknod(%s, CHR %d,%d)' % (self.name, major,
                                                          minor)))
        unix_out('mknod %s c %d %d' % (self.name, major, minor))
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mknod(self.name,
                         (self.src_stat.st_mode & 0o777) | stat.S_IFCHR,
                         os.makedev(major, minor))
            except OSError as err:
                error('failed to create device %s : %s' % (self.name,
                                                           err.strerror))
                terse(TERSE_FAIL, 'device %s' % self.name)



class VNodeBlkDev(VNode):
    '''vnode for a block device file'''

    def __init__(self, filename, syncstat_obj, exists, src_stat):
        # type: (str, SyncStat, bool, posix.stat_result) -> None
        '''initialize instance'''

        super().__init__(filename, syncstat_obj, exists)
        self.src_stat = src_stat

    def typename(self):
        # type: () -> str
        '''return file type as human readable string'''

        return 'block device file'

    def compare(self, _src_path, dest_stat):
        # type: (str, SyncStat) -> bool
        '''see if devs are the same'''

        if not self.exists:
            return False

        # dest_stat is a SyncStat object and it's useless here
        # I need a real, fresh statbuf that includes st_rdev field
        try:
            dest_stat = os.lstat(self.name)             # type: ignore
        except OSError as err:
            error('error checking %s : %s' % (self.name, err.strerror))
            return False

        src_major = os.major(self.src_stat.st_rdev)     # type: ignore
        src_minor = os.minor(self.src_stat.st_rdev)     # type: ignore
        dest_major = os.major(dest_stat.st_rdev)        # type: ignore
        dest_minor = os.minor(dest_stat.st_rdev)        # type: ignore
        if src_major != dest_major or src_minor != dest_minor:
            stdout('%s should have major,minor %d,%d but has %d,%d' %
                   (self.name, src_major, src_minor, dest_major, dest_minor))
            unix_out('# updating major,minor %s' % self.name)
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self):
        # type: () -> None
        '''make a block device file'''

        major = os.major(self.src_stat.st_rdev)          # type: ignore
        minor = os.minor(self.src_stat.st_rdev)          # type: ignore
        verbose(dryrun_msg('  os.mknod(%s, BLK %d,%d)' % (self.name, major,
                                                          minor)))
        unix_out('mknod %s b %d %d' % (self.name, major, minor))
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mknod(self.name,
                         (self.src_stat.st_mode & 0o777) | stat.S_IFBLK,
                         os.makedev(major, minor))
            except OSError as err:
                error('failed to create device %s : %s' % (self.name,
                                                           err.strerror))
                terse(TERSE_FAIL, 'device %s' % self.name)



class SyncObject():
    '''a class holding the source path (file in the repository)
    and the destination path (target file on the system).
    The SyncObject caches any stat info
    '''

    FIX_UNDEF = 0
    FIX_CREATE = 1
    FIX_TYPE = 2
    FIX_UPDATE = 3
    FIX_OWNER = 4
    FIX_MODE = 8    # this is actually a bit
    FIX_TIME = 16   # this is actually a bit

    def __init__(self, src_name, dest_name, ov_type=0):
        # type: (str, str, int) -> None
        '''src_name is simple filename without leading path
        dest_name is the src_name without group extension
        ov_type describes what overlay type the object has:
        OV_POST, OV_TEMPLATE, etc.
        '''

        # booleans is_post and no_ext are used by the overlay code

        self.src_path = src_name
        self.dest_path = dest_name
        self.ov_type = ov_type
        self.src_stat = synctool.syncstat.SyncStat()
        self.dest_stat = synctool.syncstat.SyncStat()
        self.fix_action = SyncObject.FIX_UNDEF

    def make(self, src_dir, dest_dir):
        # type: (str, str) -> None
        '''make() fills in the full paths and stat structures'''

        self.src_path = os.path.join(src_dir, self.src_path)
        self.src_stat = synctool.syncstat.SyncStat(self.src_path)
        self.dest_path = os.path.join(dest_dir, self.dest_path)
        self.dest_stat = synctool.syncstat.SyncStat(self.dest_path)

    def print_src(self):
        # type: () -> str
        '''pretty print my source path'''

        if self.src_stat.is_dir():
            return prettypath(self.src_path) + os.sep

        return prettypath(self.src_path)

    def __repr__(self):
        # type: () -> str
        '''return string representation'''

        return '[<SyncObject>: (%s) (%s)]' % (self.src_path, self.dest_path)

    def check(self):
        # type: () -> int
        '''check differences between src and dest,
        Return a FIX_xxx code
        '''

        # src_path is under $overlay/
        # dest_path is in the filesystem

        vnode = None

        if not self.dest_stat.exists():
            stdout('%s does not exist' % self.dest_path)
            return SyncObject.FIX_CREATE

        src_type = self.src_stat.filetype()
        dest_type = self.dest_stat.filetype()
        if src_type != dest_type:
            # entry is of a different file type
            vnode = self.vnode_obj()
            if vnode is None:
                # error message already printed
                return SyncObject.FIX_UNDEF
            stdout('%s should be a %s' % (self.dest_path, vnode.typename()))
            terse(synctool.lib.TERSE_WARNING, ('wrong type %s' %
                                               self.dest_path))
            return SyncObject.FIX_TYPE

        vnode = self.vnode_obj()
        if vnode is None:
            # error message already printed
            return SyncObject.FIX_UNDEF

        if not vnode.compare(self.src_path, self.dest_stat):
            # content is different; change the entire object
            log('updating %s' % self.dest_path)
            return SyncObject.FIX_UPDATE

        # check ownership and permissions and time
        # rectify if needed
        fix_action = 0
        if ((self.src_stat.uid != self.dest_stat.uid) or
                (self.src_stat.gid != self.dest_stat.gid)):
            stdout('%s should have owner %s.%s (%d.%d), '
                   'but has %s.%s (%d.%d)' % (self.dest_path,
                                              self.src_stat.ascii_uid(),
                                              self.src_stat.ascii_gid(),
                                              self.src_stat.uid,
                                              self.src_stat.gid,
                                              self.dest_stat.ascii_uid(),
                                              self.dest_stat.ascii_gid(),
                                              self.dest_stat.uid,
                                              self.dest_stat.gid))
            terse(synctool.lib.TERSE_OWNER, ('%s.%s %s' %
                                             (self.src_stat.ascii_uid(),
                                              self.src_stat.ascii_gid(),
                                              self.dest_path)))
            fix_action = SyncObject.FIX_OWNER

        if self.src_stat.mode != self.dest_stat.mode:
            stdout('%s should have mode %04o, but has %04o' %
                   (self.dest_path, self.src_stat.mode & 0o7777,
                    self.dest_stat.mode & 0o7777))
            terse(synctool.lib.TERSE_MODE, ('%04o %s' %
                                            (self.src_stat.mode & 0o7777,
                                             self.dest_path)))
            fix_action |= SyncObject.FIX_MODE

        # check times, but not for symlinks, directories
        if (synctool.param.SYNC_TIMES and
                not self.src_stat.is_link() and not self.src_stat.is_dir() and
                self.src_stat.mtime != self.dest_stat.mtime):
            stdout('%s has wrong timestamp %s' %
                   (self.dest_path, print_timestamp(self.dest_stat.mtime)))
            terse(synctool.lib.TERSE_MODE, ('%s has wrong timestamp' %
                                            self.dest_path))
            fix_action |= SyncObject.FIX_TIME

        return fix_action

    def fix(self, fix_action, pre_dict, post_dict):
        # type: (int, Dict[str, str], Dict[str, str]) -> bool
        '''fix differences, and run .pre/.post script if any
        Returns True if updated, else False
        '''

        # most cases will have FIX_UNDEF
        if fix_action == SyncObject.FIX_UNDEF:
            return False

        vnode = self.vnode_obj()
        if vnode is None:
            # error message was already printed
            return False

        # Note that .post scripts are not run for owner/mode/time changes

        need_run = False

        if fix_action == SyncObject.FIX_CREATE:
            self.run_script(pre_dict)
            log('creating %s' % self.dest_path)
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_TYPE:
            self.run_script(pre_dict)
            log('fix type %s' % self.dest_path)
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_UPDATE:
            self.run_script(pre_dict)
            log('updating %s' % self.dest_path)
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_OWNER:
            log('set owner %s.%s (%d.%d) %s' %
                (self.src_stat.ascii_uid(), self.src_stat.ascii_gid(),
                 self.src_stat.uid, self.src_stat.gid,
                 self.dest_path))
            vnode.set_owner()

        if fix_action & SyncObject.FIX_MODE:
            log('set mode %04o %s' % (self.src_stat.mode & 0o7777,
                                      self.dest_path))
            vnode.set_permissions()

        if fix_action & SyncObject.FIX_TIME:
            log('set time %s' % self.dest_path)
            # leave the atime intact
            vnode.stat.atime = self.dest_stat.atime
            vnode.set_times()

        # run .post script, if needed
        # Note: for dirs, it is run from overlay._walk_subtree()
        if need_run and not self.src_stat.is_dir():
            self.run_script(post_dict)

        return True

    def run_script(self, scripts_dict):
        # type: (Dict[str, str]) -> None
        '''run a .pre/.post script, if any'''

        if synctool.lib.NO_POST:
            return

        if self.dest_path not in scripts_dict:
            return

        script = scripts_dict[self.dest_path]

        # temporarily restore original umask
        # so the script runs with the umask set by the sysadmin
        os.umask(synctool.param.ORIG_UMASK)

        if self.dest_stat.is_dir():
            # run in the directory itself
            synctool.lib.run_command_in_dir(self.dest_path, script)
        else:
            # run in the directory where the file is
            synctool.lib.run_command_in_dir(os.path.dirname(self.dest_path),
                                            script)
        os.umask(0o77)

    def vnode_obj(self):
#pylint: disable=too-many-return-statements
        # type: () -> Optional[VNode]
        '''create vnode object for this SyncObject
        Returns the new VNode, or None on error
        '''

        exists = self.dest_stat.exists()

        if self.src_stat.is_file():
            return VNodeFile(self.dest_path, self.src_stat, exists,
                             self.src_path)

        if self.src_stat.is_dir():
            return VNodeDir(self.dest_path, self.src_stat, exists)

        if self.src_stat.is_link():
            try:
                oldpath = os.readlink(self.src_path)
            except OSError as err:
                error('failed to read symlink %s : %s' % (self.print_src(),
                                                          err.strerror))
                terse(TERSE_FAIL, self.src_path)
                return None

            return VNodeLink(self.dest_path, self.src_stat, exists, oldpath)

        if self.src_stat.is_fifo():
            return VNodeFifo(self.dest_path, self.src_stat, exists)

        if self.src_stat.is_chardev():
            return VNodeChrDev(self.dest_path, self.src_stat, exists,
                               os.stat(self.src_path))

        if self.src_stat.is_blockdev():
            return VNodeBlkDev(self.dest_path, self.src_stat, exists,
                               os.stat(self.src_path))

        # error, can not handle file type of src_path
        return None

    def vnode_dest_obj(self):
#pylint: disable=too-many-return-statements
        # type: () -> Optional[VNode]
        '''create vnode object for this SyncObject's destination'''

        exists = self.dest_stat.exists()

        if self.dest_stat.is_file():
            return VNodeFile(self.dest_path, self.src_stat, exists,
                             self.src_path)

        if self.dest_stat.is_dir():
            return VNodeDir(self.dest_path, self.src_stat, exists)

        if self.dest_stat.is_link():
            try:
                oldpath = os.readlink(self.src_path)
            except OSError as err:
                error('failed to read symlink %s : %s' % (self.print_src(),
                                                          err.strerror))
                terse(TERSE_FAIL, self.src_path)
                return None

            return VNodeLink(self.dest_path, self.src_stat, exists, oldpath)

        if self.dest_stat.is_fifo():
            return VNodeFifo(self.dest_path, self.src_stat, exists)

        if self.dest_stat.is_chardev():
            return VNodeChrDev(self.dest_path, self.src_stat, exists,
                               os.stat(self.src_path))

        if self.dest_stat.is_blockdev():
            return VNodeBlkDev(self.dest_path, self.src_stat, exists,
                               os.stat(self.src_path))

        # error, can not handle file type of src_path
        return None

    def check_purge_timestamp(self):
        # type: () -> bool
        '''check timestamp between src and dest
        Returns True if same, False if not
        '''

        # This is only used for purge/
        # check() has already determined that the files are the same
        # Now only check the timestamp ...

        if synctool.param.SYNC_TIMES:
            # this was already handled by check() and fix()
            return True

        # set times, but not for symlinks, directories
        if (not self.src_stat.is_link() and not self.src_stat.is_dir() and
                self.src_stat.mtime != self.dest_stat.mtime):
            stdout('%s mismatch (only timestamp)' % self.dest_path)
            terse(synctool.lib.TERSE_WARNING,
                  '%s (only timestamp)' % self.dest_path)

            vnode = self.vnode_obj()
            if vnode is None:
                # error message already printed
                # no further action needed; return True
                return True
            # leave the atime intact
            vnode.stat.atime = self.dest_stat.atime
            vnode.set_times()
            return False

        return True

# EOB
