#! /usr/bin/env python3
#
#   synctool.upload.py    WJ113
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''implements upload functions for synctool-master'''

import os
import sys
import shlex
import stat
import subprocess
import urllib.request
import urllib.parse
import urllib.error

from typing import List, Dict, Tuple, Optional

import synctool.config
import synctool.lib
from synctool.lib import verbose, stdout, stderr, error, warning
from synctool.lib import terse, unix_out, prettypath
import synctool.multiplex
import synctool.overlay
import synctool.param
import synctool.pwdgrp

from synctool.object import SyncObject


class UploadFile:
    '''class that holds information on requested upload'''

    # pylint: disable=too-few-public-methods

    def __init__(self) -> None:
        self.filename = ''
        self.overlay = ''
        self.purge = ''
        self.suffix = ''
        self.node = ''
        self.address = ''
        self.repos_path = ''

    def make_repos_path(self) -> None:
        '''make $overlay repository path from elements'''
        if len(self.filename) > 1 and self.filename[-1] == '/':
            # strip trailing slash
            self.filename = self.filename[:-1]

        if self.purge:
            self._make_purge_path()
            return

        if not self.repos_path:
            filenm = self.filename
            if filenm[0] == '/':
                filenm = filenm[1:]

            overlay_dir = self.overlay
            if not overlay_dir:
                overlay_dir = 'all'

            if not self.suffix and synctool.param.REQUIRE_EXTENSION:
                if self.overlay:
                    self.suffix = 'all'
                else:
                    self.suffix = self.node

            if not self.suffix:
                self.repos_path = os.path.join(synctool.param.OVERLAY_DIR,
                                               overlay_dir, filenm)
                return

            self.repos_path = os.path.join(synctool.param.OVERLAY_DIR,
                                           overlay_dir,
                                           filenm + '._' + self.suffix)
            return

        if self.suffix:
            # remove the current group suffix
            # and add the specified suffix to the filename
            self.repos_path, _ = os.path.splitext(self.repos_path)
            self.repos_path += '._' + self.suffix

        if self.overlay:
            # user supplied (maybe a different) overlay group dir
            # so take repos_filename apart and insert a new group dir
            if (self.repos_path[:synctool.param.OVERLAY_LEN] ==
                    synctool.param.OVERLAY_DIR + os.sep):
                arr = self.repos_path.split(os.sep)
                overlay_arr = synctool.param.OVERLAY_DIR.split(os.sep)
                # replace the group dir with what the user gave
                arr[len(overlay_arr)] = self.overlay
                # reassemble the full path with up.overlay as group dir
                self.repos_path = os.sep.join(arr)

    def _make_purge_path(self) -> None:
        '''make $purge repository path from elements'''

        self.repos_path = os.path.join(synctool.param.PURGE_DIR,
                                       self.purge) + self.filename


class RemoteStat:
    '''represent stat() info of a remote file'''

    # pylint: disable=too-many-instance-attributes

    def __init__(self, arr: List[str]) -> None:
        '''initialize instance
        May throw ValueError
        '''

        if not arr:
            raise ValueError()

        if arr[0] == 'error:':
            raise ValueError()

        if len(arr) < 7:
            raise ValueError()

        self.mode = int(arr[0], 8)
        self.uid = int(arr[1])
        self.owner = arr[2]
        self.gid = int(arr[3])
        self.group = arr[4]
        self.size = int(arr[5])
        self.filename = urllib.parse.unquote(arr[6])

        if self.is_symlink():
            if len(arr) != 9:
                raise ValueError()

            self.linkdest = urllib.parse.unquote(arr[8])
        else:
            self.linkdest = ''

    def is_dir(self) -> bool:
        '''Returns True if it's a directory'''

        return stat.S_ISDIR(self.mode)

    def is_symlink(self) -> bool:
        '''Returns True if it's a symbolic link'''

        return stat.S_ISLNK(self.mode)

    def translate_uid(self) -> int:
        '''Return local numeric uid corresponding to remote owner'''

        try:
            local_uid = synctool.pwdgrp.pw_uid(self.owner)
        except KeyError:
            return self.uid

        return local_uid

    def translate_gid(self) -> int:
        '''Return local numeric gid corresponding to remote group'''

        try:
            local_gid = synctool.pwdgrp.grp_gid(self.group)
        except KeyError:
            return self.gid

        return local_gid

    def __repr__(self) -> str:
        '''Returns string representation'''

        return ('<RemoteStat: %06o %u %s %u %s %u %r %r>' %
                (self.mode, self.uid, self.owner, self.gid, self.group,
                 self.size, self.filename, self.linkdest))


def _remote_stat(upfile: UploadFile) -> Optional[List[RemoteStat]]:
    '''Get stat info of the remote object
    Returns array of RemoteStat data, or None on error
    '''

    # use ssh connection multiplexing (if possible)
    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    use_multiplex = synctool.multiplex.use_mux(upfile.node)
    if use_multiplex:
        synctool.multiplex.ssh_args(cmd_arr, upfile.node)

    list_cmd = os.path.join(synctool.param.ROOTDIR, 'sbin',
                            'synctool_list.py')
    cmd_arr.extend(['--', upfile.address, list_cmd, upfile.filename])

    verbose('running synctool_list %s:%s' % (upfile.node, upfile.filename))
    unix_out(' '.join(cmd_arr))
    try:
        with subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              universal_newlines=True) as proc:
            out, err_output = proc.communicate()
            proc.wait()

            if proc.returncode == 255:
                error('ssh connection to %s failed' % upfile.node)
                if err_output:
                    verbose('error output: %s' % err_output)
                return None

            if proc.returncode == 127:
                error('remote list command failed')
                if err_output:
                    verbose('error output: %s' % err_output)
                return None

    except OSError as err:
        error('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return None

    # parse synctool_list output into array of RemoteStat info
    data = []
    for line in out.split('\n'):
        if not line:
            continue

        arr = line.split()
        if arr[0] == 'error:':
            # relay error message
            error(' '.join(arr[1:]))
            return None

        try:
            remote_stat = RemoteStat(arr)
        except ValueError:
            error('unexpected output from synctool_list %s:%s' %
                  (upfile.node, upfile.filename))
            return None

        verbose('remote: %r' % remote_stat)
        data.append(remote_stat)

    return data


def _makedir(path: str, remote_stats: List[RemoteStat]) -> bool:
    '''make directory in repository, copying over mode and ownership
    of the directories as they are on the remote side
    remote_stats is array holding stat info of the remote side
    Returns True on success, False on error

    Note that this function creates directories even if the remote
    path component may be a symbolic link
    '''

    if not path or not remote_stats:
        error("recursion too deep")
        return False

    if synctool.lib.path_exists(path):
        return True

    verbose('_makedir %s %r' % (path, remote_stats))

    # recursively make parent directory
    if not _makedir(os.path.dirname(path), remote_stats[1:]):
        return False

    # do a simple check against the names of the dir
    # (are we still 'in sync' with remote_stats?)
    basename = os.path.basename(path)
    remote_basename = os.path.basename(remote_stats[0].filename)
    if remote_basename and basename != remote_basename:
        error("out of sync with remote stat information, I'm lost")
        return False

    # temporarily restore admin's umask
    mask = os.umask(synctool.param.ORIG_UMASK)
    mode = remote_stats[0].mode & 0o777
    try:
        os.mkdir(path, mode)
    except OSError as err:
        error('failed to create directory %s: %s' % (path, err.strerror))
        os.umask(mask)
        return False

    unix_out('mkdir -p -m %04o %s' % (mode, path))

    os.umask(mask)

    # the mkdir mode is affected by umask
    # so set the mode the way we want it
    try:
        os.chmod(path, mode)
    except OSError as err:
        warning('failed to chmod %04o %s: %s' % (mode, path, err.strerror))

    # also set the owner & group
    # uid/gid are translated from remote owner/group,
    # unless --numeric-ids is wanted
    rsync_cmd_arr = shlex.split(synctool.param.RSYNC_CMD)
    if '--numeric-ids' in rsync_cmd_arr:
        uid = remote_stats[0].uid
        gid = remote_stats[0].gid
    else:
        uid = remote_stats[0].translate_uid()
        gid = remote_stats[0].translate_gid()
    try:
        os.lchown(path, uid, gid)
    except OSError as err:
        warning('failed to chown %s.%s %s: %s' %
                (synctool.pwdgrp.pw_name(uid), synctool.pwdgrp.grp_name(gid),
                 path, err.strerror))

    return True


# UploadFile object, used in callback function for overlay.visit()
GLOBAL_UPLOAD_FILE = UploadFile()


def _upload_callback(obj: SyncObject, _pre_dict: Dict[str, str], _post_dict: Dict[str, str]) -> Tuple[bool, bool]:
    '''find the overlay path for the destination in UPLOAD_FILE'''

    # this callback modifies the global GLOBAL_UPLOAD_FILE object

    if obj.ov_type == synctool.overlay.OV_TEMPLATE_POST:
        return False, False

    if obj.dest_path == GLOBAL_UPLOAD_FILE.filename:
        GLOBAL_UPLOAD_FILE.repos_path = obj.src_path
        return False, False

    if synctool.lib.terse_match(GLOBAL_UPLOAD_FILE.filename, obj.dest_path):
        # it's a terse path ; 'expand' it
        GLOBAL_UPLOAD_FILE.filename = obj.dest_path
        GLOBAL_UPLOAD_FILE.repos_path = obj.src_path
        return False, False

    return True, False


def upload(upfile: UploadFile) -> None:
    '''copy a file from a node into the overlay/ tree'''

    # Note: this global is only needed because of callback fn ...
    global GLOBAL_UPLOAD_FILE                               # pylint: disable=global-statement

    if upfile.filename[0] != os.sep:
        error('the filename to upload must be an absolute path')
        sys.exit(-1)

    if upfile.suffix and upfile.suffix not in synctool.param.ALL_GROUPS:
        error("no such group '%s'" % upfile.suffix)
        sys.exit(-1)

    if upfile.overlay and upfile.overlay not in synctool.param.ALL_GROUPS:
        error("no such group '%s'" % upfile.overlay)
        sys.exit(-1)

    if upfile.purge and upfile.purge not in synctool.param.ALL_GROUPS:
        error("no such group '%s'" % upfile.purge)
        sys.exit(-1)

    if synctool.lib.DRY_RUN and not synctool.lib.QUIET:
        stdout('DRY RUN, not uploading any files')
        terse(synctool.lib.TERSE_DRYRUN, 'not uploading any files')

    if upfile.purge:
        rsync_upload(upfile)
        return

    # pretend that the current node is now the given node;
    # this is needed for find() to find the best reference for the file
    orig_nodename = synctool.param.NODENAME
    synctool.param.NODENAME = upfile.node
    synctool.config.insert_group(upfile.node, upfile.node)

    orig_my_groups = synctool.param.MY_GROUPS[:]
    synctool.param.MY_GROUPS = synctool.config.get_my_groups()

    # see if file is already in the repository
    # Note: ugly global is needed because of callback function
    GLOBAL_UPLOAD_FILE = upfile
    synctool.overlay.visit(synctool.param.OVERLAY_DIR, _upload_callback)
    upfile = GLOBAL_UPLOAD_FILE

    synctool.param.NODENAME = orig_nodename
    synctool.param.MY_GROUPS = orig_my_groups

    rsync_upload(upfile)


def rsync_upload(upfile: UploadFile) -> None:
    '''upload a file/dir to $overlay/group/ or $purge/group/'''

    # pylint: disable=too-many-branches,too-many-statements

    upfile.make_repos_path()

    # check whether the remote entry exists
    remote_stats = _remote_stat(upfile)
    if remote_stats is None:
        # error message was already printed
        return

    # first element in array is our 'target'
    isdir = remote_stats[0].is_dir()
    if isdir and synctool.param.REQUIRE_EXTENSION and not upfile.purge:
        error('remote is a directory')
        stderr('synctool can not upload directories to $overlay '
               'when require_extension is set')
        return

    if isdir:
        upfile.filename += os.sep
        upfile.repos_path += os.sep

    # make command: rsync [-n] [-v] node:/path/ $overlay/group/path/
    cmd_arr = shlex.split(synctool.param.RSYNC_CMD)

    # opts is just for the 'visual aspect'; it is displayed when --verbose
    opts = ' '
    if synctool.lib.DRY_RUN:
        # cmd_arr.append('-n')
        opts += '-n '

    if synctool.lib.VERBOSE:
        cmd_arr.append('-v')
        opts += '-v '
        if '-q' in cmd_arr:
            cmd_arr.remove('-q')
        if '--quiet' in cmd_arr:
            cmd_arr.remove('--quiet')

    # use ssh connection multiplexing (if possible)
    ssh_cmd_arr = shlex.split(synctool.param.SSH_CMD)
    use_multiplex = synctool.multiplex.use_mux(upfile.node)
    if use_multiplex:
        synctool.multiplex.ssh_args(ssh_cmd_arr, upfile.node)
    cmd_arr.extend(['-e', ' '.join(ssh_cmd_arr)])
    cmd_arr.extend(['--', upfile.address + ':' + upfile.filename, upfile.repos_path])

    verbose_path = prettypath(upfile.repos_path)
    if synctool.lib.DRY_RUN:
        stdout('would be uploaded as %s' % verbose_path)
    else:
        dest_dir = os.path.dirname(upfile.repos_path)
        _makedir(dest_dir, remote_stats[1:])
        if not synctool.lib.path_exists(dest_dir):
            error('failed to create %s/' % dest_dir)
            return

    # for $overlay, never do rsync --delete / --delete-excluded
    # for $purge, don't use rsync --delete on single files
    # because it would (inadvertently) delete all existing files in the repos
    if not upfile.purge or not isdir:
        if '--delete' in cmd_arr:
            cmd_arr.remove('--delete')
        if '--delete-excluded' in cmd_arr:
            cmd_arr.remove('--delete-excluded')

    verbose('running rsync%s%s:%s to %s' % (opts, upfile.node, upfile.filename,
                                            verbose_path))
    if not synctool.lib.DRY_RUN:
        synctool.lib.run_with_nodename(cmd_arr, upfile.node)

        if not synctool.lib.path_exists(upfile.repos_path):
            error('upload failed')
        else:
            stdout('uploaded %s' % verbose_path)
    else:
        # in dry-run mode, show the command anyway
        unix_out('# dry run, rsync not performed')
        unix_out(' '.join(cmd_arr))

# EOB
