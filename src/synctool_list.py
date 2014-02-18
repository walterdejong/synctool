#! /usr/bin/env python
#
#   synctool_list.py    WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''list directory entry, including leading directory entries
This is a helper program for synctool --upload
'''

import os
import sys
import stat
import pwd
import grp
import urllib

# Note: do not import synctool modules here
# They can't be found without the launcher, and this program is small anyway

# caches for usernames/groupnames by uid/gid
UID_CACHE = {}
GID_CACHE = {}


def do_stat(filename):
    '''list directory entry
    Returns string on success, None on error
    '''

    try:
        # FIXME if it's an "intermediate" symlinked dir, I really want
        # FIXME the mode of the linkdest instead
        # FIXME (this is easiest solved by rewriting as recursive func)
        statbuf = os.lstat(filename)
    except OSError as err:
        print 'error:', err.strerror
        return None

    owner = uid_username(statbuf.st_uid)
    group = gid_groupname(statbuf.st_gid)
    quoted_filename = urllib.quote(filename)

    # Note: linkdest isn't used
    # FIXME take this code out or not?
    # FIXME maybe change to "filename -> linkdest" ?
    if stat.S_ISLNK(statbuf.st_mode):
        try:
            linkdest = os.readlink(filename)
        except OSError as err:
            print 'error:', err.strerror
            return None
    else:
        linkdest = '.'
    quoted_linkdest = urllib.quote(linkdest)

    return ('%06o %u %s %u %s %u %s %s' %
            (statbuf.st_mode, statbuf.st_uid, owner, statbuf.st_gid, group,
             statbuf.st_size, quoted_filename, quoted_linkdest))


def uid_username(uid):
    '''Return username for numeric uid'''

    s_uid = '%u' % uid
    if s_uid in UID_CACHE:
        return UID_CACHE[s_uid]

    try:
        pw_entry = pwd.getpwuid(uid)
    except KeyError:
        # no such user
        UID_CACHE[s_uid] = s_uid
        return s_uid

    UID_CACHE[s_uid] = pw_entry.pw_name
    return pw_entry.pw_name


def gid_groupname(gid):
    '''Return group name for numeric gid'''

    s_gid = '%u' % gid
    if s_gid in GID_CACHE:
        return GID_CACHE[s_gid]

    try:
        grp_entry = grp.getgrgid(gid)
    except KeyError:
        # no such group
        GID_CACHE[s_gid] = s_gid
        return s_gid

    GID_CACHE[s_gid] = grp_entry.gr_name
    return grp_entry.gr_name



if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print 'usage: %s <filename>' % os.path.basename(sys.argv[0])
        sys.exit(1)

    fullpath = sys.argv[1]
    # strip trailing slashes
    while len(fullpath) > 1 and fullpath[-1] == os.sep:
        fullpath = fullpath[:-1]

    # FIXME rewrite as recursive func?
    while True:
        line = do_stat(fullpath)
        if line is None:
            # error exit
            # mind the exit code; do not use -1, 255, 127
            #  255 ssh failed to connect
            #  127 remote command does not exist
            sys.exit(2)

        print line

        path, _filename = os.path.split(fullpath)
        if not path:
            # filename without leading path
            break

        if not _filename:
            # reached root directory
            break

        fullpath = path

# EOB
