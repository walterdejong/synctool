#
#	synctool_param.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

VERSION = '5.0-beta'

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

DIFF_CMD = None
PING_CMD = None
SSH_CMD = None
SCP_CMD = None
RSYNC_CMD = None
SYNCTOOL_CMD = None
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
ERASE_SAVED = False
IGNORE_DOTFILES = False
IGNORE_DOTDIRS = False
IGNORE_FILES = []
IGNORE_GROUPS = []
ON_UPDATE = {}
ALWAYS_RUN = []

NODES = {}
INTERFACES = {}

GROUP_DEFS = {}

# to be initialized externally ... (see synctool.py)
# these are lists of group names
MY_GROUPS = None
ALL_GROUPS = None

# string length of the 'MASTERDIR' variable
# although silly to keep this in a var, it makes it easier to print messages
MASTER_LEN = 0


# EOB
