#
#   synctool.pwdgrp.py  WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''pwd/grp functions'''

import pwd
import grp

CACHE_BY_UID = {}
CACHE_BY_GID = {}
CACHE_BY_USER = {}
CACHE_BY_GROUP = {}


def pw_name(uid):
    '''Returns username for uid, or "uid" when not found'''

    if uid < 0:
        raise ValueError()

    s_uid = '%u' % uid
    if s_uid in CACHE_BY_UID:
        return CACHE_BY_UID[s_uid]

    try:
        pwd_entry = pwd.getpwuid(uid)
    except KeyError:
        CACHE_BY_UID[s_uid] = s_uid
        return s_uid

    CACHE_BY_UID[s_uid] = pwd_entry.pw_name
    return pwd_entry.pw_name


def grp_name(gid):
    '''Returns group for gid, or "gid" when not found'''

    if gid < 0:
        raise ValueError()

    s_gid = '%u' % gid
    if s_gid in CACHE_BY_GID:
        return CACHE_BY_GID[s_gid]

    try:
        grp_entry = grp.getgrgid(gid)
    except KeyError:
        CACHE_BY_GID[s_gid] = s_gid
        return s_gid

    CACHE_BY_GID[s_gid] = grp_entry.gr_name
    return grp_entry.gr_name


def pw_uid(username):
    '''Returns uid for a given username
    Throws KeyError when not found
    '''

    if not username:
        raise ValueError()

    if username in CACHE_BY_USER:
        return CACHE_BY_USER[username]

    try:
        pwd_entry = pwd.getpwnam(username)
    except KeyError:
        raise

    CACHE_BY_USER[username] = pwd_entry.pw_uid
    return pwd_entry.pw_uid


def grp_gid(group):
    '''Returns gid for a given group
    Throws KeyError when not found
    '''

    if not group:
        raise ValueError()

    if group in CACHE_BY_GROUP:
        return CACHE_BY_GROUP[group]

    try:
        grp_entry = grp.getgrnam(group)
    except KeyError:
        raise

    CACHE_BY_GROUP[group] = grp_entry.gr_gid
    return grp_entry.gr_gid


# unit test
if __name__ == '__main__':
    print 'uid 501:   ', pw_name(501)
    print 'gid 20:    ', grp_name(20)
    print 'uid walter:', pw_uid('walter')
    print 'gid staff: ', grp_gid('staff')

# EOB
