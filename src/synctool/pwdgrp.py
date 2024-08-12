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

from typing import Dict

CACHE_BY_UID: Dict[str, str] = {}
CACHE_BY_GID: Dict[str, str] = {}
CACHE_BY_USER: Dict[str, int] = {}
CACHE_BY_GROUP: Dict[str, int] = {}


def pw_name(uid: int) -> str:
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


def grp_name(gid: int) -> str:
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


def pw_uid(username: str) -> int:
    '''Returns uid for a given username
    Raises KeyError when not found
    '''

    if not username:
        raise ValueError('invalid username (empty)')

    try:
        return CACHE_BY_USER[username]
    except KeyError:
        pwd_entry = pwd.getpwnam(username)                  # this may raise KeyError
        CACHE_BY_USER[username] = pwd_entry.pw_uid          # this may raise KeyError
        return pwd_entry.pw_uid


def grp_gid(group: str) -> int:
    '''Returns gid for a given group
    Raises KeyError when not found
    '''

    if not group:
        raise ValueError('invalid group (empty name)')

    try:
        return CACHE_BY_GROUP[group]
    except KeyError:
        grp_entry = grp.getgrnam(group)                     # this may raise KeyError
        CACHE_BY_GROUP[group] = grp_entry.gr_gid            # this may raise KeyError
        return grp_entry.gr_gid


# unit test
if __name__ == '__main__':
    print('uid 501:   ', pw_name(501))
    print('gid 20:    ', grp_name(20))
    print('uid walter:', pw_uid('walter'))
    print('gid staff: ', grp_gid('staff'))

# EOB
