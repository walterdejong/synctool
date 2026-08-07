#
#   synctool.param.py    WJ111
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''parameters and global vars'''

from __future__ import annotations

import os
import sys

# Note: the release datetime should be set slightly in the future
# in regards to when the release tag is made in git
# For example, the next (half) hour
# This is so that synctool --check-update will work correctly
# RELEASE_DATETIME is in GMT/UTC
VERSION = '7.2.2'
RELEASE_DATETIME = '2026-08-07T22:22:22'

# location of default config file on the master node
DEFAULT_CONF = '/opt/synctool/etc/synctool.conf'
CONF_FILE = DEFAULT_CONF

BOOLEAN_VALUE_TRUE = ('1', 'on', 'yes', 'true')
BOOLEAN_VALUE_FALSE = ('0', 'off', 'no', 'false')

#
# config variables
#
ROOTDIR = ''
VAR_DIR = ''
VAR_LEN = 0
OVERLAY_DIR = ''
OVERLAY_LEN = 0
DELETE_DIR = ''
DELETE_LEN = 0
PURGE_DIR = ''
PURGE_LEN = 0
SCRIPT_DIR = ''
TEMP_DIR = '/tmp/synctool'
HOSTNAME = ''
NODENAME = ''

DIFF_CMD = 'diff -u'
PING_CMD = 'ping -q -c 1 -w 1'
SSH_CMD = 'ssh -o ConnectTimeout=10 -x -q'
RSYNC_CMD = "rsync -ar --delete --delete-excluded -q"
SYNCTOOL_CMD = ''
PKG_CMD = ''

PACKAGE_MANAGER = ''

NUM_PROC = 16
SLEEP_TIME = 0

CONTROL_PERSIST = '1h'
REQUIRE_EXTENSION = True
BACKUP_COPIES = True
SYSLOGGING = True
FULL_PATH = False
TERSE = False
SYNC_TIMES = False
IGNORE_DOTFILES = False
IGNORE_DOTDIRS = False
IGNORE_FILES: set[str] = set()
IGNORE_FILES_WITH_WILDCARDS: list[str] = []

# default_nodeset parameter in the config file
# warning: make_default_nodeset() is only called by commands that are
# supposed to run on the master node
# The client commands do not expand/set DEFAULT_NODESET
DEFAULT_NODESET: set[str] = {'all'}

# the master's fqdn hostname
MASTER = ''

# set of slaves by nodename
SLAVES: set[str] = set()

# NODES is a dict of nodes
# each node is a list of groups, ordered by importance;
# first listed group is most important, last group is least important
#
#   NODES[node] -> [ list of groups ]
#
NODES: dict[str, list[str]] = {}

# dict of ipaddresses by nodename
#
#   IPADDRESSES[node] -> ipaddress
#
IPADDRESSES: dict[str, str] = {}

# compound groups are lists of groups, in order of importance
#
#   GROUP_DEFS[compound] -> [ list of groups ]
#   GROUP_DEFS[compound] may be None
#
GROUP_DEFS: dict[str, list[str] | None] = {}

# set of ignored groups and nodes
IGNORE_GROUPS: set[str] = set()

# list of my groups, ordered by importance
MY_GROUPS: list[str] = []

# set of all known groups
ALL_GROUPS: set[str] = set()

# set of nodes that don't want an rsync copy
NO_RSYNC: set[str] = set()

# colorize output
COLORIZE = True
COLORIZE_FULL_LINE = False
COLORIZE_BRIGHT = True

TERSE_COLORS = {'info': 'default',
                'warn': 'magenta',
                'error': 'red',
                'fail': 'red',
                'sync': 'default',
                'link': 'cyan',
                'mkdir': 'blue',        # I'd use yellow on a black background, blue on white
                'rm': 'yellow',
                'chown': 'cyan',
                'chmod': 'cyan',
                'exec': 'green',
                'upload': 'magenta',
                'new': 'default',
                'type': 'magenta',
                'dryrun': 'default',
                'fixing': 'default',
                'ok': 'default'}

# list of supported package managers
KNOWN_PACKAGE_MANAGERS = ('apk', 'apt-get', 'brew', 'bsdpkg', 'dnf',
                          'pacman', 'pkg', 'yum', 'zypper')
# 'urpmi', 'portage', 'port', 'swaret', 'xbps', 'nix'

ORIG_UMASK = 0o22


def init() -> None:
    '''detect my rootdir and set default symlink mode'''

    # pylint: disable=global-statement

    global ROOTDIR, CONF_FILE
    global VAR_DIR, VAR_LEN, OVERLAY_DIR, OVERLAY_LEN, DELETE_DIR, DELETE_LEN
    global PURGE_DIR, PURGE_LEN, SCRIPT_DIR, ORIG_UMASK

    base = os.path.abspath(os.path.dirname(sys.argv[0]))
    if not base:
        raise RuntimeError('unable to determine base dir')

    (ROOTDIR, bindir) = os.path.split(base)

    CONF_FILE = os.path.join(ROOTDIR, 'etc/synctool.conf')

    VAR_DIR = os.path.join(ROOTDIR, 'var')
    VAR_LEN = len(VAR_DIR) + 1
    OVERLAY_DIR = os.path.join(VAR_DIR, 'overlay')
    OVERLAY_LEN = len(OVERLAY_DIR) + 1
    DELETE_DIR = os.path.join(VAR_DIR, 'delete')
    DELETE_LEN = len(DELETE_DIR) + 1
    PURGE_DIR = os.path.join(VAR_DIR, 'purge')
    PURGE_LEN = len(PURGE_DIR) + 1
    SCRIPT_DIR = os.path.join(ROOTDIR, 'scripts')

    # the following only makes sense for synctool-client, but OK

    # add base dir (which is the bin/ dir) to PATH
    path = os.environ['PATH']
    if not path:
        # no path, set a sensible default
        path_arr = ['/bin', '/sbin', '/usr/bin', '/usr/sbin',
                    '/usr/local/bin', '/usr/local/sbin']
    else:
        path_arr = path.split(os.pathsep)

    # add the synctool/bin/ dir
    bindir = os.path.join(ROOTDIR, 'bin')
    if bindir not in path_arr:
        path_arr.append(bindir)
        os.environ['PATH'] = os.pathsep.join(path_arr)

    # save original umask (and restore it)
    ORIG_UMASK = os.umask(0o77)
    os.umask(ORIG_UMASK)


# EOB
