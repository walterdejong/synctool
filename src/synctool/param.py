#
#   synctool.param.py    WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''parameters and global vars'''

import os
import sys

try:
    from typing import Dict, List, Sequence, Set
except ImportError:
    pass

# Note: the release datetime should be set slightly in the future
# in regards to when the release tag is made in git
# For example, the next (half) hour
# This is so that synctool --check-update will work correctly
VERSION = '6.3-beta'                                # type: str
RELEASE_DATETIME = '2015-08-12T22:20:00'            # type: str

# location of default config file on the master node
DEFAULT_CONF = '/opt/synctool/etc/synctool.conf'    # type: str
CONF_FILE = DEFAULT_CONF                            # type: str

BOOLEAN_VALUE_TRUE = ('1', 'on', 'yes', 'true')     # type: Sequence[str]
BOOLEAN_VALUE_FALSE = ('0', 'off', 'no', 'false')   # type: Sequence[str]

#
# config variables
#
ROOTDIR = None              # type: str
VAR_DIR = None              # type: str
VAR_LEN = 0                 # type: int
OVERLAY_DIR = None          # type: str
OVERLAY_LEN = 0             # type: int
DELETE_DIR = None           # type: str
DELETE_LEN = 0              # type: int
PURGE_DIR = None            # type: str
PURGE_LEN = 0               # type: int
SCRIPT_DIR = None           # type: str
TEMP_DIR = '/tmp/synctool'  # type: str
HOSTNAME = None             # type: str
NODENAME = None             # type: str

DIFF_CMD = 'diff -u'                                    # type: str
PING_CMD = 'ping -q -c 1 -w 1'                          # type: str
SSH_CMD = 'ssh -o ConnectTimeout=10 -x -q'              # type: str
RSYNC_CMD = "rsync -ar --delete --delete-excluded -q"   # type: str
SYNCTOOL_CMD = None                                     # type: str
PKG_CMD = None                                          # type: str

PACKAGE_MANAGER = None      # type: str

NUM_PROC = 16               # type: int
SLEEP_TIME = 0              # type: int

CONTROL_PERSIST = '1h'      # type: str
REQUIRE_EXTENSION = True    # type: bool
BACKUP_COPIES = True        # type: bool
SYSLOGGING = True           # type: bool
FULL_PATH = False           # type: bool
TERSE = False               # type: bool
SYNC_TIMES = False          # type: bool
IGNORE_DOTFILES = False     # type: bool
IGNORE_DOTDIRS = False      # type: bool
IGNORE_FILES = set()                # type: Set[str]
IGNORE_FILES_WITH_WILDCARDS = []    # type: List[str]

# default_nodeset parameter in the config file
# warning: make_default_nodeset() is only called by commands that are
# supposed to run on the master node
# The client commands do not expand/set DEFAULT_NODESET
DEFAULT_NODESET = set(['all'])      # type: Set[str]

# the master's fqdn hostname
MASTER = None               # type: str

# set of slaves by nodename
SLAVES = set()              # type: Set[str]

# NODES is a dict of nodes
# each node is a list of groups, ordered by importance;
# first listed group is most important, last group is least important
#
#   NODES[node] -> [ list of groups ]
#
NODES = {}                  # type: Dict[str, List[str]]

# dict of ipaddresses by nodename
#
#   IPADDRESSES[node] -> ipaddress
#
IPADDRESSES = {}            # type: Dict[str, str]

# compound groups are lists of groups, in order of importance
#
#   GROUP_DEFS[compound] -> [ list of groups ]
#
GROUP_DEFS = {}             # type: Dict[str, List[str]]

# set of ignored groups and nodes
IGNORE_GROUPS = set()       # type: Set[str]

# list of my groups, ordered by importance
MY_GROUPS = None            # type: List[str]

# set of all known groups
ALL_GROUPS = set([])        # type: Set[str]

# set of nodes that don't want an rsync copy
NO_RSYNC = set()            # type: Set[str]

# colorize output
COLORIZE = True             # type: bool
COLORIZE_FULL_LINE = False  # type: bool
COLORIZE_BRIGHT = True      # type: bool

TERSE_COLORS = {
    'info'   : 'default',
    'warn'   : 'magenta',
    'error'  : 'red',
    'fail'   : 'red',
    'sync'   : 'default',
    'link'   : 'cyan',
    'mkdir'  : 'blue',      # I'd use yellow on a black background,
                            # blue on white
    'rm'     : 'yellow',
    'chown'  : 'cyan',
    'chmod'  : 'cyan',
    'exec'   : 'green',
    'upload' : 'magenta',
    'new'    : 'default',
    'type'   : 'magenta',
    'dryrun' : 'default',
    'fixing' : 'default',
    'ok'     : 'default',
}                           # type: Dict[str, str]

# list of supported package managers
KNOWN_PACKAGE_MANAGERS = ('apt-get', 'yum', 'zypper', 'brew', 'pacman',
                          # 'urpmi', 'portage', 'port', 'swaret',
                          'pkg', 'bsdpkg')  # type: Sequence[str]

ORIG_UMASK = 0o22    # type: int


def init():
    # type() -> None
    '''detect my rootdir and set default symlink mode'''

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
