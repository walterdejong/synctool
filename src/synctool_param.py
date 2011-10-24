#
#	synctool_param.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

VERSION = '5.2-beta'

DEFAULT_CONF = '/var/lib/synctool/synctool.conf'
CONF_FILE = DEFAULT_CONF

BOOLEAN_VALUE_TRUE = ('1', 'on', 'yes', 'true')
BOOLEAN_VALUE_FALSE = ('0', 'off', 'no', 'false')

#
#	config variables
#
MASTERDIR = None
OVERLAY_DIRS = []
DELETE_DIRS = []
TASKS_DIRS = []
SCRIPT_DIR = None
HOSTNAME = None
NODENAME = None
HOST_ID = None

DIFF_CMD = None
PING_CMD = None
SSH_CMD = None
SCP_CMD = None
RSYNC_CMD = None
SYNCTOOL_CMD = None
PKG_CMD = None

PACKAGE_MANAGER = None

LOGFILE = None
NUM_PROC = 16				# use sensible default

#
#	default symlink mode
#	Linux makes them 0777 no matter what umask you have ...
#	but how do you like them on a different platform?
#
#	The symlink mode can be set in the config file with keyword symlink_mode
#
SYMLINK_MODE = 0755

REQUIRE_EXTENSION = True
FULL_PATH = False
TERSE = False
BACKUP_COPIES = True
IGNORE_DOTFILES = False
IGNORE_DOTDIRS = False
IGNORE_FILES = []
IGNORE_FILES_WITH_WILDCARDS = []
IGNORE_GROUPS = []
ON_UPDATE = {}
ALWAYS_RUN = []

NODES = {}
INTERFACES = {}
HOSTNAMES = {}
HOSTNAMES_BY_NODE = {}

GROUP_DEFS = {}

# to be initialized externally ... (see synctool.py)
# these are lists of group names
MY_GROUPS = None
ALL_GROUPS = None

# string length of the 'MASTERDIR' variable
# although silly to keep this in a var, it makes it easier to print messages
MASTER_LEN = 0

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
	'mkdir'  : 'blue',		# I'd use yellow on a black background, blue on white
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

# EOB
