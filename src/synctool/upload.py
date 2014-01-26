#! /usr/bin/env python
#
#   synctool.upload.py    WJ113
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''implements upload functions for synctool-master'''

import os
import sys
import shlex
import subprocess

import synctool.config
import synctool.lib
from synctool.lib import verbose, stdout, stderr, terse, unix_out, prettypath
import synctool.overlay
import synctool.param

# UploadFile object, used in callback function for overlay.visit()
GLOBAL_UPLOAD_FILE = None


class UploadFile(object):
    '''class that holds information on requested upload'''

    def __init__(self):
        self.filename = None
        self.overlay = None
        self.purge = None
        self.suffix = None
        self.node = None
        self.address = None
        self.repos_path = None

    def make_repos_path(self):
        '''make $overlay repository path from elements'''

        if len(self.filename) > 1 and self.filename[-1] == '/':
            # strip trailing slash
            self.filename = self.filename[:-1]

        if self.purge:
            self._make_purge_path()
            return

        if not self.repos_path:
            fn = self.filename
            if fn[0] == '/':
                fn = fn[1:]

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
                                               overlay_dir, fn)
                return

            self.repos_path = os.path.join(synctool.param.OVERLAY_DIR,
                                           overlay_dir,
                                           fn + '._' + self.suffix)
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

    def _make_purge_path(self):
        '''make $purge repository path from elements'''

        self.repos_path = os.path.join(synctool.param.PURGE_DIR,
                                       self.purge) + self.filename


def _remote_isdir(up):
    '''See if the remote rsync source is a directory or a file
    Parameter 'up' is an instance of UploadFile
    Returns: tuple of booleans: (exists, isdir)'''

    cmd_arr = shlex.split(synctool.param.RSYNC_CMD)[:1]
    cmd_arr.append('--list-only')
    cmd_arr.append(up.address + ':' + up.filename)

    verbose('running rsync --list-only %s:%s' % (up.node, up.filename))
    unix_out(' '.join(cmd_arr))

    try:
        proc = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except OSError as err:
        stderr('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return False, False

    out, err = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == 255:
            stderr('failed to connect to %s' % up.node)
        elif proc.returncode == 23:
            stderr('error: no such file or directory')
        else:
            stderr('failed rsync %s:%s' % (up.node, up.filename))

        return False, False

    # output should be an 'ls -l' like line, with first a mode string
    for line in out.split('\n'):
        arr = line.split()
        mode = arr[0]
        if len(mode) == 10:     # crude test
            if mode[0] == 'd':
                # it's a directory
                verbose('remote rsync source is a directory')
                return True, True

            if mode[0] in '-lpcbs':
                # accept it as a file entry
                verbose('remote rsync source is a file entry')
                return True, False

        # some other line on stdout; just ignore it

    # got no good output
    stderr('failed to parse rsync --list-only output')
    return False, False


def _upload_callback(obj, post_dict, dir_changed=False):
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


def upload(up):
    '''copy a file from a node into the overlay/ tree'''

    # Note: this global is only needed because of callback fn ...
    global GLOBAL_UPLOAD_FILE

    if up.filename[0] != os.sep:
        stderr('error: the filename to upload must be an absolute path')
        sys.exit(-1)

    if up.suffix and not up.suffix in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.suffix)
        sys.exit(-1)

    if up.overlay and not up.overlay in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.overlay)
        sys.exit(-1)

    if up.purge and not up.purge in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.purge)
        sys.exit(-1)

    if synctool.lib.DRY_RUN and not synctool.lib.QUIET:
        stdout('DRY RUN, not uploading any files')
        terse(synctool.lib.TERSE_DRYRUN, 'not uploading any files')

    if up.purge != None:
        rsync_upload(up)
        return

    # pretend that the current node is now the given node;
    # this is needed for find() to find the best reference for the file
    orig_nodename = synctool.param.NODENAME
    synctool.param.NODENAME = up.node
    synctool.config.insert_group(up.node, up.node)

    orig_my_groups = synctool.param.MY_GROUPS[:]
    synctool.param.MY_GROUPS = synctool.config.get_my_groups()

    # see if file is already in the repository
    # Note: ugly global is needed because of callback function
    GLOBAL_UPLOAD_FILE = up
    synctool.overlay.visit(synctool.param.OVERLAY_DIR, _upload_callback)
    up = GLOBAL_UPLOAD_FILE

    synctool.param.NODENAME = orig_nodename
    synctool.param.MY_GROUPS = orig_my_groups

    rsync_upload(up)


def rsync_upload(up):
    '''upload a file/dir to $overlay/group/ or $purge/group/'''

    up.make_repos_path()

    # check whether the remote entry exists
    ok, isdir = _remote_isdir(up)
    if not ok:
        # error message was already printed
        return

    if isdir and synctool.param.REQUIRE_EXTENSION and not up.purge:
        stderr('error: remote is a directory')
        stderr('synctool can not upload directories to $overlay '
               'when require_extension is set')
        return

    if isdir:
        up.filename += os.sep
        up.repos_path += os.sep

    # make command: rsync [-n] [-v] node:/path/ $overlay/group/path/
    cmd_arr = shlex.split(synctool.param.RSYNC_CMD)

    # opts is just for the 'visual aspect'; it is displayed when --verbose
    opts = ' '
    if synctool.lib.DRY_RUN:
        cmd_arr.append('-n')
        opts += '-n '

    if synctool.lib.VERBOSE:
        cmd_arr.append('-v')
        opts += '-v '
        if '-q' in cmd_arr:
            cmd_arr.remove('-q')
        if '--quiet' in cmd_arr:
            cmd_arr.remove('--quiet')

    cmd_arr.append(up.address + ':' + up.filename)
    cmd_arr.append(up.repos_path)

    verbose_path = prettypath(up.repos_path)
    if synctool.lib.DRY_RUN:
        stdout('would be uploaded as %s' % verbose_path)
    else:
        dest_dir = os.path.dirname(up.repos_path)
        synctool.lib.mkdir_p(dest_dir)
        if not os.path.exists(dest_dir):
            stderr('error: failed to create %s/' % dest_dir)
            return

    # for $overlay, never do rsync --delete / --delete-excluded
    # for $purge, don't use rsync --delete on single files
    # because it would (inadvertently) delete all existing files in the repos
    if not up.purge or not isdir:
        if '--delete' in cmd_arr:
            cmd_arr.remove('--delete')
        if '--delete-excluded' in cmd_arr:
            cmd_arr.remove('--delete-excluded')

    verbose('running rsync%s%s:%s to %s' % (opts, up.node, up.filename,
                                            verbose_path))
    unix_out(' '.join(cmd_arr))

    if not synctool.lib.DRY_RUN:
        synctool.lib.run_with_nodename(cmd_arr, up.node)
        if not os.path.exists(up.repos_path):
            stderr('error: upload failed')
        else:
            stdout('uploaded %s' % verbose_path)


# EOB
