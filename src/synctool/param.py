#
#	synctool.param.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import sys

VERSION = '6.0-beta'

# location of default config file on the master node
DEFAULT_CONF = '/opt/synctool/etc/synctool.conf'
CONF_FILE = DEFAULT_CONF

BOOLEAN_VALUE_TRUE = ('1', 'on', 'yes', 'true')
BOOLEAN_VALUE_FALSE = ('0', 'off', 'no', 'false')

#
# config variables
#
ROOTDIR = None
VAR_DIR = None
VAR_LEN = 0
OVERLAY_DIR = None
OVERLAY_LEN = 0
DELETE_DIR = None
DELETE_LEN = 0
TEMP_DIR = '/tmp/synctool'
HOSTNAME = None
NODENAME = None
HOST_ID = None

DIFF_CMD = 'diff -u'
PING_CMD = 'ping -q -c 1 -t 1'
SSH_CMD = 'ssh -o ConnectTimeout=10 -x -q'
SCP_CMD = 'scp -o ConnectTimeout=10 -p'
RSYNC_CMD = ("rsync -ar --numeric-ids --delete --delete-excluded "
			"-e 'ssh -o ConnectTimeout=10 -x -q' -q")
SYNCTOOL_CMD = None
PKG_CMD = None

PACKAGE_MANAGER = None

LOGFILE = None
NUM_PROC = 16				# use sensible default

# default symlink mode
# Linux makes them 0777 no matter what umask you have ...
# but how do you like them on a different platform?
#
# The symlink mode can be set in the config file
# with keyword symlink_mode
#
# Changing this value here has no effect ...
# By default, detect_root() will set it to 0777 on Linux and 0755 otherwise
SYMLINK_MODE = 0755

REQUIRE_EXTENSION = True
FULL_PATH = False
TERSE = False
BACKUP_COPIES = True
IGNORE_DOTFILES = False
IGNORE_DOTDIRS = False
IGNORE_FILES = []
IGNORE_FILES_WITH_WILDCARDS = []

DEFAULT_NODESET = set(['all'])

# NODES is a dict of nodes
# each node is a list of groups, ordered by importance;
# first listed group is most important, last group is least important
#
#   NODES[node] -> [ list of groups ]
#
NODES = {}

# dict of ipaddresses by nodename
#
#   IPADDRESSES[node] -> ipaddress
#
IPADDRESSES = {}

# dict of nodes ... by hostname
#
#   HOSTNAMES[hostname] -> nodename
#
HOSTNAMES = {}

# dict of hostnames by nodename
#
#   HOSTNAMES_BY_NODE[node] -> hostname
#
HOSTNAMES_BY_NODE = {}

# compound groups are lists of groups, in order of importance
#
#   GROUP_DEFS[compound] -> [ list of groups ]
#
GROUP_DEFS = {}

# set of ignored groups and nodes
IGNORE_GROUPS = set()

# list of my groups, ordered by importance
MY_GROUPS = None

# set of all known groups
ALL_GROUPS = None

# set of nodes that don't want an rsync copy
NO_RSYNC = set()

# colorize output
COLORIZE = True
COLORIZE_FULL_LINE = False
COLORIZE_BRIGHT = True

TERSE_COLORS = {
	'info'   : 'default',
	'warn'   : 'magenta',
	'error'  : 'red',
	'fail'   : 'red',
	'sync'   : 'default',
	'link'   : 'cyan',
	'mkdir'  : 'blue',		# I'd use yellow on a black background,
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
}

# list of supported package managers
KNOWN_PACKAGE_MANAGERS = (
	'apt-get', 'yum', 'zypper', 'brew', 'pacman', 'bsdpkg',
#	'urpmi', 'portage', 'port', 'swaret',
)


def init():
	'''detect my rootdir and set default symlink mode'''

	global ROOTDIR, CONF_FILE
	global VAR_DIR, VAR_LEN, OVERLAY_DIR, OVERLAY_LEN, DELETE_DIR, DELETE_LEN

	base = os.path.abspath(os.path.dirname(sys.argv[0]))
	if not base:
		raise RuntimeError, 'unable to determine base dir'

	(ROOTDIR, bindir) = os.path.split(base)

	CONF_FILE = os.path.join(ROOTDIR, 'etc/synctool.conf')

	VAR_DIR = os.path.join(ROOTDIR, 'var')
	VAR_LEN = len(VAR_DIR) + 1
	OVERLAY_DIR = os.path.join(VAR_DIR, 'overlay')
	OVERLAY_LEN = len(OVERLAY_DIR) + 1
	DELETE_DIR = os.path.join(VAR_DIR, 'delete')
	DELETE_LEN = len(DELETE_DIR) + 1

	# the following only makes sense for synctool-client
	# but OK

	# detect symlink mode
	if sys.platform[:5] == 'linux':
		SYMLINK_MODE = 0777
	else:
		SYMLINK_MODE = 0755

	# add base dir (which is the bin/ dir) to PATH
	path = os.environ['PATH']
	if not path:
		# no path, set a sensible default
		path_arr = ['/bin', '/sbin', '/usr/bin', '/usr/sbin',
			'/usr/local/bin', '/usr/local/sbin']
 	else:
 		path_arr = string.split(path, os.pathsep)

 	# add the synctool/bin/ dir
 	path_arr.append(os.path.join(ROOTDIR, 'bin'))

 	os.environ['PATH'] = string.join(path_arr, os.pathsep)


# EOB
