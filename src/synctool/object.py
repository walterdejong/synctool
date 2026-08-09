#
#   synctool.object.py    WJ110
#
#   synctool Copyright 2026 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''a SyncObject is a source file + matching destination path and attributes'''

from __future__ import annotations

import datetime
import hashlib
import os
import shutil
import stat

try:
    import posix
except ImportError:
    pass

import synctool.lib
import synctool.param
import synctool.syncstat
from synctool.lib import (
    TERSE_FAIL,
    dryrun_msg,
    error,
    log,
    prettypath,
    print_timestamp,
    stdout,
    terse,
    unix_out,
    verbose,
)

SyncStat = synctool.syncstat.SyncStat

# size for doing I/O while checksumming files
IO_SIZE = 16 * 1024


class VNode:
    '''base class for doing actions with directory entries'''

    def __init__(self, filename: str, statbuf: SyncStat, exists: bool) -> None:
        '''filename is typically destination path
        statbuf is source statbuf
        exists is boolean whether dest path already exists
        '''

        self.name = filename
        self.stat = statbuf
        self.exists = exists

    def typename(self) -> str:
        '''return file type as human readable string'''

        return '(unknown file type)'

    def move_saved(self) -> None:
        '''move existing entry to .saved'''

        # do not save files that already are .saved
        _, ext = os.path.splitext(self.name)
        if ext == '.saved':
            return

        verbose(dryrun_msg(f'saving {self.name} as {self.name}.saved'))
        unix_out(f'mv {self.name} {self.name}.saved')

        if not synctool.lib.DRY_RUN:
            verbose(f'  os.rename({self.name}, {self.name}.saved)')
            try:
                os.rename(self.name, f'{self.name}.saved')
            except OSError as err:
                error(f'failed to save {self.name} as {self.name}.saved : {err.strerror}')
                terse(TERSE_FAIL, f'save {self.name}.saved')

    def harddelete(self) -> None:
        '''delete existing entry'''

        if synctool.lib.DRY_RUN:
            not_str = 'not '
        else:
            not_str = ''

        stdout(f'{not_str}deleting {self.name}')
        unix_out(f'rm {self.name}')
        terse(synctool.lib.TERSE_DELETE, self.name)

        if not synctool.lib.DRY_RUN:
            verbose(f'  os.unlink({self.name})')
            try:
                os.unlink(self.name)
            except OSError as err:
                error(f'failed to delete {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'delete {self.name}')
            else:
                log(f'deleted {self.name}')

    def quiet_delete(self) -> None:
        '''silently delete existing entry; only called by fix()'''

        if not synctool.lib.DRY_RUN and not synctool.param.BACKUP_COPIES:
            verbose(f'  os.unlink({self.name})')
            try:
                os.unlink(self.name)
            except OSError:
                pass

    def mkdir_basepath(self) -> None:
        '''call mkdir -p to create leading path'''

        if synctool.lib.DRY_RUN:
            return

        basedir = os.path.dirname(self.name)

        # be a bit quiet about it
        if synctool.lib.VERBOSE or synctool.lib.UNIX_CMD:
            verbose('making directory {}'.format(prettypath(basedir)))

        synctool.lib.mkdir_p(basedir)

    def compare(self, _src_path: str, _dest_stat: SyncStat) -> bool:
        '''compare content
        Return True when same, False when different
        '''

        return True

    def create(self) -> None:
        '''create a new entry'''

    def fix(self) -> None:
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

    def set_owner(self) -> None:
        '''set ownership equal to source'''

        verbose(dryrun_msg(f'  os.chown({self.name}, {self.stat.uid}, {self.stat.gid})'))
        unix_out(f'chown {self.stat.ascii_uid()}:{self.stat.ascii_gid()} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                os.chown(self.name, self.stat.uid, self.stat.gid)
            except OSError as err:
                error(f'failed to chown {self.stat.ascii_uid()}:{self.stat.ascii_gid()} {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'owner {self.name}')

    def set_permissions(self) -> None:
        '''set access permission bits equal to source'''

        verbose(dryrun_msg(f'  os.chmod({self.name}, {self.stat.mode & 0o7777:04o})'))
        unix_out(f'chmod 0{self.stat.mode & 0o7777:0o} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                os.chmod(self.name, self.stat.mode & 0o7777)
            except OSError as err:
                error(f'failed to chmod {self.stat.mode & 0o7777:04o} {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'mode {self.name}')

    def set_times(self) -> None:
        '''set access and modification times'''

        # only mtime is shown
        verbose(dryrun_msg(f'  os.utime({self.name}, {print_timestamp(self.stat.mtime)})'))
        # print timestamp in other format
        datet = datetime.datetime.fromtimestamp(self.stat.mtime).astimezone()
        time_str = datet.strftime('%Y%m%d%H%M.%S')
        unix_out(f'touch -t {time_str} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                os.utime(self.name, (self.stat.atime, self.stat.mtime))
            except OSError as err:
                error(f'failed to set utime on {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'utime {self.name}')


class VNodeFile(VNode):
    '''vnode for a regular file'''

    def __init__(self, filename: str, statbuf: SyncStat, exists: bool, src_path: str) -> None:
        '''initialize instance'''

        super().__init__(filename, statbuf, exists)
        self.src_path = src_path

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'regular file'

    def compare(self, src_path: str, dest_stat: SyncStat) -> bool:
        '''see if files are the same
        Return True if the same
        '''

        if self.stat.size != dest_stat.size:
            if synctool.lib.DRY_RUN:
                stdout(f'{self.name} mismatch (file size)')
            else:
                stdout(f'{self.name} updated (file size mismatch)')
            terse(synctool.lib.TERSE_SYNC, self.name)
            unix_out(f'# updating file {self.name}')
            return False

        return self._compare_checksums(src_path)

    def _compare_checksums(self, src_path: str) -> bool:
        '''compare checksum of src_path and dest: self.name
        Return True if the same'''

        sum1 = hashlib.md5()
        sum2 = hashlib.md5()

        src_is_open = False
        this_is_open = False
        try:
            with open(src_path, 'rb') as ffile1:
                src_is_open = True

                with open(self.name, 'rb') as ffile2:
                    this_is_open = True

                    ended = False
                    while not ended and (sum1.digest() == sum2.digest()):
                        data1 = ffile1.read(IO_SIZE)
                        data2 = ffile2.read(IO_SIZE)

                        if not data1:
                            ended = True
                        else:
                            sum1.update(data1)

                        if not data2:
                            ended = True
                        else:
                            sum2.update(data2)

        except OSError as err:
            if not src_is_open:
                error(f'failed to open {src_path} : {err.strerror}')
                # return True because we can't fix an error in src_path
                return True

            if not this_is_open:
                error(f'failed to open {self.name} : {err.strerror}')
                return False

            error(f'failed to read file {err.filename}: {err.strerror}')
            return False

        if sum1.digest() != sum2.digest():
            if synctool.lib.DRY_RUN:
                stdout(f'{self.name} mismatch (MD5 checksum)')
            else:
                stdout(f'{self.name} updated (MD5 mismatch)')

            unix_out(f'# updating file {self.name}')
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self) -> None:
        '''copy file'''

        if not self.exists:
            terse(synctool.lib.TERSE_NEW, self.name)

        verbose(dryrun_msg(f'  copy {self.src_path} {self.name}'))
        unix_out(f'cp {self.src_path} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                # copy file
                shutil.copy(self.src_path, self.name)
            except OSError as err:
                error(f'failed to copy {prettypath(self.src_path)} to {self.name}: {err.strerror}')
                terse(TERSE_FAIL, self.name)


class VNodeDir(VNode):
    '''vnode for a directory'''

#    def __init__(self, filename: str, statbuf: SyncStat, exists: bool) -> None:
#        '''initialize instance'''
#
#        super(VNodeDir, self).__init__(filename, statbuf, exists)

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'directory'

    def create(self) -> None:
        '''create directory'''

        if synctool.lib.path_exists(self.name):
            # it can happen that the dir already exists
            # due to recursion in visit() + VNode.mkdir_basepath()
            # So this is double checked for dirs that did not exist
            return

        verbose(dryrun_msg(f'  os.mkdir({self.name})'))
        unix_out(f'mkdir {self.name}')
        terse(synctool.lib.TERSE_MKDIR, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mkdir(self.name, self.stat.mode & 0o7777)
            except OSError as err:
                error(f'failed to make directory {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'mkdir {self.name}')

    def harddelete(self) -> None:
        '''delete directory'''

        if synctool.lib.DRY_RUN:
            not_str = 'not '
        else:
            not_str = ''

        stdout(f'{not_str}removing {self.name + os.sep}')
        unix_out(f'rmdir {self.name}')
        terse(synctool.lib.TERSE_DELETE, self.name + os.sep)
        if not synctool.lib.DRY_RUN:
            verbose(f'  os.rmdir({self.name})')
            try:
                os.rmdir(self.name)
            except OSError:
                # probably directory not empty
                # refuse to delete dir, just move it aside
                verbose(f'refusing to delete directory {self.name}')
                self.move_saved()

    def quiet_delete(self) -> None:
        '''silently delete directory; only called by fix()'''

        if not synctool.lib.DRY_RUN and not synctool.param.BACKUP_COPIES:
            verbose(f'  os.rmdir({self.name})')
            try:
                os.rmdir(self.name)
            except OSError:
                # probably directory not empty
                # refuse to delete dir, just move it aside
                verbose(f'refusing to delete directory {self.name}')
                self.move_saved()

    def set_times(self) -> None:
        '''set access and modification times'''

        # Note: should we raise RuntimeError here?


class VNodeLink(VNode):
    '''vnode for a symbolic link'''

    def __init__(self, filename: str, statbuf: SyncStat, exists: bool, oldpath: str) -> None:
        '''initialize instance'''

        super().__init__(filename, statbuf, exists)
        self.oldpath = oldpath

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'symbolic link'

    def compare(self, _src_path: str, _dest_stat: SyncStat) -> bool:
        '''compare symbolic links'''

        if not self.exists:
            return False

        try:
            link_to = os.readlink(self.name)
        except OSError as err:
            error(f'failed to read symlink {self.name} : {err.strerror}')
            return False

        if self.oldpath != link_to:
            stdout(f'{self.name} should point to {self.oldpath}, but points to {link_to}')
            terse(synctool.lib.TERSE_LINK, self.name)
            return False

        return True

    def create(self) -> None:
        '''create symbolic link'''

        verbose(dryrun_msg(f'  os.symlink({self.oldpath}, {self.name})'))
        unix_out(f'ln -s {self.oldpath} {self.name}')
        terse(synctool.lib.TERSE_LINK, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.symlink(self.oldpath, self.name)
            except OSError as err:
                error(f'failed to create symlink {self.name} -> {self.oldpath} : {err.strerror}')
                terse(TERSE_FAIL, f'link {self.name}')

    def set_owner(self) -> None:
        '''set ownership of symlink'''

        if not hasattr(os, 'lchown'):
            # you never know
            return

        verbose(dryrun_msg(f'  os.lchown({self.name}, {self.stat.uid}, {self.stat.gid})'))
        unix_out(f'lchown {self.stat.ascii_uid()}:{self.stat.ascii_gid()} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                os.lchown(self.name, self.stat.uid, self.stat.gid)
            except OSError as err:
                error(f'failed to lchown {self.stat.ascii_uid()}:{self.stat.ascii_gid()} {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'owner {self.name}')

    def set_permissions(self) -> None:
        '''set permissions of symlink (if possible)'''

        # pylint: disable=no-member

        # check if this platform supports lchmod()
        # Linux does not have lchmod: its symlinks are always mode 0777
        if not hasattr(os, 'lchmod'):
            return

        verbose(dryrun_msg(f'  os.lchmod({self.name}, {self.stat.mode & 0o7777:04o})'))
        unix_out(f'lchmod 0{self.stat.mode & 0o7777:0o} {self.name}')
        if not synctool.lib.DRY_RUN:
            try:
                os.lchmod(self.name, self.stat.mode & 0o7777)           # type: ignore # pyright false positive
            except OSError as err:
                error(f'failed to lchmod {self.stat.mode & 0o7777:04o} {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'mode {self.name}')

    def set_times(self) -> None:
        '''set access and modification times'''

        # Note: should we raise RuntimeError here?


class VNodeFifo(VNode):
    '''vnode for a fifo'''

#    def __init__(self, filename: str, statbuf: SyncStat, exists: bool) -> None:
#        '''initialize instance'''
#
#        super(VNodeFifo, self).__init__(filename, statbuf, exists)

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'fifo'

    def create(self) -> None:
        '''make a fifo'''

        verbose(dryrun_msg(f'  os.mkfifo({self.name})'))
        unix_out(f'mkfifo {self.name}')
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mkfifo(self.name, self.stat.mode & 0o777)
            except OSError as err:
                error(f'failed to create fifo {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'fifo {self.name}')


class VNodeChrDev(VNode):
    '''vnode for a character device file'''

    def __init__(self, filename: str, syncstat_obj: SyncStat, exists: bool,
                 src_stat: posix.stat_result) -> None:                  # type: ignore # pyright false positive
        '''initialize instance'''

        super().__init__(filename, syncstat_obj, exists)
        self.src_stat = src_stat

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'character device file'

    def compare(self, _src_path: str, dest_stat: SyncStat) -> bool:
        '''see if devs are the same'''

        if not self.exists:
            return False

        # dest_stat is a SyncStat object and it's useless here
        # I need a real, fresh statbuf that includes st_rdev field
        try:
            dest_stat = os.lstat(self.name)             # type: ignore
        except OSError as err:
            error(f'error checking {self.name} : {err.strerror}')
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
            stdout(f'{self.name} should have major,minor {src_major},{src_minor} but has {dest_major},{dest_minor}')
            unix_out(f'# updating major,minor {self.name}')
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self) -> None:
        '''make a character device file'''

        major = os.major(self.src_stat.st_rdev)         # type: ignore
        minor = os.minor(self.src_stat.st_rdev)         # type: ignore
        verbose(dryrun_msg(f'  os.mknod({self.name}, CHR {major},{minor})'))
        unix_out(f'mknod {self.name} c {major} {minor}')
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mknod(self.name,
                         (self.src_stat.st_mode & 0o777) | stat.S_IFCHR,
                         os.makedev(major, minor))
            except OSError as err:
                error(f'failed to create device {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'device {self.name}')


class VNodeBlkDev(VNode):
    '''vnode for a block device file'''

    def __init__(self, filename: str, syncstat_obj: SyncStat, exists: bool,
                 src_stat: posix.stat_result) -> None:                  # type: ignore # pyright false positive
        '''initialize instance'''

        super().__init__(filename, syncstat_obj, exists)
        self.src_stat = src_stat

    def typename(self) -> str:
        '''return file type as human readable string'''

        return 'block device file'

    def compare(self, _src_path: str, dest_stat: SyncStat) -> bool:
        '''see if devs are the same'''

        if not self.exists:
            return False

        # dest_stat is a SyncStat object and it's useless here
        # I need a real, fresh statbuf that includes st_rdev field
        try:
            dest_stat = os.lstat(self.name)             # type: ignore
        except OSError as err:
            error(f'error checking {self.name} : {err.strerror}')
            return False

        src_major = os.major(self.src_stat.st_rdev)     # type: ignore
        src_minor = os.minor(self.src_stat.st_rdev)     # type: ignore
        dest_major = os.major(dest_stat.st_rdev)        # type: ignore
        dest_minor = os.minor(dest_stat.st_rdev)        # type: ignore
        if src_major != dest_major or src_minor != dest_minor:
            stdout(f'{self.name} should have major,minor {src_major},{src_minor} but has {dest_major},{dest_minor}')
            unix_out(f'# updating major,minor {self.name}')
            terse(synctool.lib.TERSE_SYNC, self.name)
            return False

        return True

    def create(self) -> None:
        '''make a block device file'''

        major = os.major(self.src_stat.st_rdev)          # type: ignore
        minor = os.minor(self.src_stat.st_rdev)          # type: ignore
        verbose(dryrun_msg(f'  os.mknod({self.name}, BLK {major},{minor})'))
        unix_out(f'mknod {self.name} b {major} {minor}')
        terse(synctool.lib.TERSE_NEW, self.name)
        if not synctool.lib.DRY_RUN:
            try:
                os.mknod(self.name,
                         (self.src_stat.st_mode & 0o777) | stat.S_IFBLK,
                         os.makedev(major, minor))
            except OSError as err:
                error(f'failed to create device {self.name} : {err.strerror}')
                terse(TERSE_FAIL, f'device {self.name}')


class SyncObject:
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

    def __init__(self, src_name: str, dest_name: str, ov_type: int = 0) -> None:
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

    def make(self, src_dir: str, dest_dir: str) -> None:
        '''make() fills in the full paths and stat structures'''

        self.src_path = os.path.join(src_dir, self.src_path)
        self.src_stat = synctool.syncstat.SyncStat(self.src_path)
        self.dest_path = os.path.join(dest_dir, self.dest_path)
        self.dest_stat = synctool.syncstat.SyncStat(self.dest_path)

    def print_src(self) -> str:
        '''pretty print my source path'''

        if self.src_stat.is_dir():
            return prettypath(self.src_path) + os.sep

        return prettypath(self.src_path)

    def __repr__(self) -> str:
        '''return string representation'''

        return f'[<SyncObject>: ({self.src_path}) ({self.dest_path})]'

    def check(self) -> int:
        '''check differences between src and dest,
        Return a FIX_xxx code
        '''

        # src_path is under $overlay/
        # dest_path is in the filesystem

        vnode = None

        if not self.dest_stat.exists():
            stdout(f'{self.dest_path} does not exist')
            return SyncObject.FIX_CREATE

        src_type = self.src_stat.filetype()
        dest_type = self.dest_stat.filetype()
        if src_type != dest_type:
            # entry is of a different file type
            vnode = self.vnode_obj()
            if vnode is None:
                # error message already printed
                return SyncObject.FIX_UNDEF
            stdout(f'{self.dest_path} should be a {vnode.typename()}')
            terse(synctool.lib.TERSE_WARNING, f'wrong type {self.dest_path}')
            return SyncObject.FIX_TYPE

        vnode = self.vnode_obj()
        if vnode is None:
            # error message already printed
            return SyncObject.FIX_UNDEF

        if not vnode.compare(self.src_path, self.dest_stat):
            # content is different; change the entire object
            log(f'updating {self.dest_path}')
            return SyncObject.FIX_UPDATE

        # check ownership and permissions and time
        # rectify if needed
        fix_action = 0
        if ((self.src_stat.uid != self.dest_stat.uid) or
                (self.src_stat.gid != self.dest_stat.gid)):
            stdout('{} should have owner {}:{} ({}:{}), but has {}:{} ({}:{})'.format(self.dest_path,
                                                                                      self.src_stat.ascii_uid(), self.src_stat.ascii_gid(),
                                                                                      self.src_stat.uid, self.src_stat.gid,
                                                                                      self.dest_stat.ascii_uid(), self.dest_stat.ascii_gid(),
                                                                                      self.dest_stat.uid, self.dest_stat.gid))
            terse(synctool.lib.TERSE_OWNER, '{}:{} {}'.format(self.src_stat.ascii_uid(), self.src_stat.ascii_gid(), self.dest_path))
            fix_action = SyncObject.FIX_OWNER

        if self.src_stat.mode != self.dest_stat.mode:
            stdout(f'{self.dest_path} should have mode {self.src_stat.mode & 0o7777:04o}, but has {self.dest_stat.mode & 0o7777:04o}')
            terse(synctool.lib.TERSE_MODE, f'{self.src_stat.mode & 0o7777:04o} {self.dest_path}')
            fix_action |= SyncObject.FIX_MODE

        # check times, but not for symlinks, directories
        if (synctool.param.SYNC_TIMES and
                not self.src_stat.is_link() and not self.src_stat.is_dir() and
                self.src_stat.mtime != self.dest_stat.mtime):
            stdout(f'{self.dest_path} has wrong timestamp {print_timestamp(self.dest_stat.mtime)}')
            terse(synctool.lib.TERSE_MODE, f'{self.dest_path} has wrong timestamp')
            fix_action |= SyncObject.FIX_TIME

        return fix_action

    def fix(self, fix_action: int, pre_dict: dict[str, str], post_dict: dict[str, str]) -> bool:
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
            log(f'creating {self.dest_path}')
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_TYPE:
            self.run_script(pre_dict)
            log(f'fix type {self.dest_path}')
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_UPDATE:
            self.run_script(pre_dict)
            log(f'updating {self.dest_path}')
            vnode.fix()
            need_run = True

        elif fix_action == SyncObject.FIX_OWNER:
            log(f'set owner {self.src_stat.ascii_uid()}.{self.src_stat.ascii_gid()} ({self.src_stat.uid}.{self.src_stat.gid}) {self.dest_path}')
            vnode.set_owner()

        if fix_action & SyncObject.FIX_MODE:
            log(f'set mode {self.src_stat.mode & 0o7777:04o} {self.dest_path}')
            vnode.set_permissions()

        if fix_action & SyncObject.FIX_TIME:
            log(f'set time {self.dest_path}')
            # leave the atime intact
            vnode.stat.atime = self.dest_stat.atime
            vnode.set_times()

        # run .post script, if needed
        # Note: for dirs, it is run from overlay._walk_subtree()
        if need_run and not self.src_stat.is_dir():
            self.run_script(post_dict)

        return True

    def run_script(self, scripts_dict: dict[str, str]) -> None:
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

    def vnode_obj(self) -> VNode | None:
        '''create vnode object for this SyncObject
        Returns the new VNode, or None on error
        '''

        # pylint: disable=too-many-return-statements

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
                error(f'failed to read symlink {self.print_src()} : {err.strerror}')
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

    def vnode_dest_obj(self) -> VNode | None:
        '''create vnode object for this SyncObject's destination'''

        # pylint: disable=too-many-return-statements

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
                error(f'failed to read symlink {self.print_src()} : {err.strerror}')
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

    def check_purge_timestamp(self) -> bool:
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
            stdout(f'{self.dest_path} mismatch (only timestamp)')
            terse(synctool.lib.TERSE_WARNING,
                  f'{self.dest_path} (only timestamp)')

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
