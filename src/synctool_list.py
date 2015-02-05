#! /usr/bin/env python
#
#   synctool_list.py    WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
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


def print_stat(filename, top=True):
    '''print directory entry and parent entries'''

    if top:
        # target might be a symlink; use lstat()
        statfunc = os.lstat
    else:
        # target might be a symlinked directory;
        # I want the destination mode, ownership
        statfunc = os.stat

    try:
        statbuf = statfunc(filename)
    except OSError as err:
        print 'error: %s: %s' % (filename, err.strerror)
        return

    owner = uid_username(statbuf.st_uid)
    group = gid_groupname(statbuf.st_gid)

    # filename is quoted like an URL to properly support nasty filenames
    # with spaces and newlines and such
    quoted_filename = urllib.quote(filename)

    # if it's a symlink, get the linkdest as well
    if stat.S_ISLNK(statbuf.st_mode):
        try:
            linkdest = os.readlink(filename)
        except OSError as err:
            print 'error: %s: %s' % (filename, err.strerror)
            return

        quoted_linkdest = urllib.quote(linkdest)

        # Be wary that a symlink has more fields
        print ('%06o %u %s %u %s %u %s -> %s' %
               (statbuf.st_mode, statbuf.st_uid, owner, statbuf.st_gid, group,
                statbuf.st_size, quoted_filename, quoted_linkdest))
    else:
        print ('%06o %u %s %u %s %u %s' %
               (statbuf.st_mode, statbuf.st_uid, owner, statbuf.st_gid, group,
                statbuf.st_size, quoted_filename))

    path, filename = os.path.split(filename)
    if not path:
        # no leading path
        return

    if not filename:
        # reached the root directory
        return

    # recurse
    print_stat(path, top=False)


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

    print_stat(fullpath)

# EOB
