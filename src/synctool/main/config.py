#
#   synctool.main.config.py WJ109
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''show elements of the synctool.conf file
This program is nice for shell scripting around synctool
'''

import sys
import getopt
import socket

from typing import List

from synctool import config, param
from synctool.lib import stderr, error
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.range

# hardcoded name because otherwise we get "config.py"
PROGNAME = 'config'

# these are enums for the "list" command-line options
ACTION_LIST_NODES = 1
ACTION_LIST_GROUPS = 2
ACTION_NODES = 3
ACTION_GROUPS = 4
ACTION_CMDS = 5
ACTION_PKGMGR = 6
ACTION_NUMPROC = 7
ACTION_LIST_DIRS = 8
ACTION_PREFIX = 9
ACTION_MASTER = 10
ACTION_SLAVE = 11
ACTION_NODENAME = 12
ACTION_FQDN = 13
ACTION_EXPAND = 14
ACTION_VERSION = 15


class Options:
    '''represents program options and arguments'''

    def __init__(self) -> None:
        '''initialize instance'''

        self.arg_nodenames = ''
        self.arg_groups = ''
        self.arg_cmds: List[str] = []
        self.arg_expand = ''
        self.filter_ignored = False
        self.ipaddress = False
        self.rsync = False
        self.action = 0
        self.action_option_str = ''

    def set_action(self, action: int, opt_str: str) -> None:
        '''set the action to perform
        This is a helper function for the command-line parser
        and exits the program on error
        '''

        assert opt_str

        if self.action > 0:
            error('options %s and %s can not be combined' % (self.action_option_str, opt_str))
            sys.exit(1)

        self.action = action
        self.action_option_str = opt_str


def list_all_nodes(opts: Options) -> None:
    '''display a list of all nodes'''

    nodes = config.get_all_nodes()
    nodes.sort()

    for node in nodes:
        ignored = set(config.get_groups(node))
        ignored &= param.IGNORE_GROUPS

        if opts.filter_ignored and ignored:
            continue

        if opts.ipaddress:
            node += ' ' + config.get_node_ipaddress(node)

        if opts.rsync:
            if node in param.NO_RSYNC:
                node += ' no'
            else:
                node += ' yes'

        if ignored:
            node += ' (ignored)'

        print(node)


def list_all_groups(opts: Options) -> None:
    '''display a list of all groups'''

    groups = list(param.GROUP_DEFS.keys())
    groups.sort()

    for group in groups:
        if opts.filter_ignored and group in param.IGNORE_GROUPS:
            continue

        if group in param.IGNORE_GROUPS:
            group += ' (ignored)'

        print(group)


def list_nodes(nodelist: str, opts: Options) -> None:
    '''display node definition'''

    # pylint: disable=too-many-branches

    nodeset = synctool.nodeset.NodeSet()
    try:
        nodeset.add_node(nodelist)
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if nodeset.addresses() is None:
        # error message already printed
        sys.exit(1)

    groups: List[str] = []
    for node in nodeset.nodelist:
        if opts.ipaddress or opts.rsync:
            out = ''
            if opts.ipaddress:
                out += ' ' + config.get_node_ipaddress(node)

            if opts.rsync:
                if node in param.NO_RSYNC:
                    out += ' no'
                else:
                    out += ' yes'

            print(out[1:])
        else:
            for group in config.get_groups(node):
                # extend groups, but do not have duplicates
                if group not in groups:
                    groups.append(group)

    # group order is important, so don't sort
    # however, when you list multiple nodes at once, the groups will have
    # been added to the end
    # So the order is important, but may be incorrect when listing
    # multiple nodes at once
#    groups.sort()

    for group in groups:
        if opts.filter_ignored and group in param.IGNORE_GROUPS:
            continue

        if group in param.IGNORE_GROUPS:
            group += ' (ignored)'

        print(group)


def list_nodegroups(grouplist: str, opts: Options) -> None:
    '''display list of nodes that are member of group'''

    nodeset = synctool.nodeset.NodeSet()
    try:
        nodeset.add_group(grouplist)
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if nodeset.addresses() is None:
        # error message already printed
        sys.exit(1)

    arr = list(nodeset.nodelist)
    arr.sort()

    for node in arr:
        ignored = set(config.get_groups(node))
        ignored &= param.IGNORE_GROUPS

        if opts.filter_ignored and ignored:
            continue

        if opts.ipaddress:
            node += ' ' + config.get_node_ipaddress(node)

        if opts.rsync:
            if node in param.NO_RSYNC:
                node += ' no'
            else:
                node += ' yes'

        if ignored:
            node += ' (ignored)'

        print(node)


def list_commands(cmds: List[str]) -> None:
    '''display command setting'''

    # pylint: disable=too-many-branches

    for cmd in cmds:
        if cmd == 'diff':
            okay, _ = config.check_cmd_config('diff_cmd', param.DIFF_CMD)
            if okay:
                print(param.DIFF_CMD)

        if cmd == 'ping':
            okay, _ = config.check_cmd_config('ping_cmd', param.PING_CMD)
            if okay:
                print(param.PING_CMD)

        elif cmd == 'ssh':
            okay, _ = config.check_cmd_config('ssh_cmd', param.SSH_CMD)
            if okay:
                print(param.SSH_CMD)

        elif cmd == 'rsync':
            okay, _ = config.check_cmd_config('rsync_cmd', param.RSYNC_CMD)
            if okay:
                print(param.RSYNC_CMD)

        elif cmd == 'synctool':
            okay, _ = config.check_cmd_config('synctool_cmd', param.SYNCTOOL_CMD)
            if okay:
                print(param.SYNCTOOL_CMD)

        elif cmd == 'pkg':
            okay, _ = config.check_cmd_config('pkg_cmd', param.PKG_CMD)
            if okay:
                print(param.PKG_CMD)

        else:
            error("no such command '%s' available in synctool" % cmd)


def list_dirs() -> None:
    '''display directory settings'''

    print('rootdir', param.ROOTDIR)
    print('overlaydir', param.OVERLAY_DIR)
    print('deletedir', param.DELETE_DIR)
    print('scriptdir', param.SCRIPT_DIR)
    print('tempdir', param.TEMP_DIR)


def expand(nodelist: str) -> None:
    '''display expanded argument'''

    nodeset = synctool.nodeset.NodeSet()
    try:
        nodeset.add_node(nodelist)
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    # don't care if the nodes do not exist

    arr = list(nodeset.nodelist)
    arr.sort()

    for elem in arr:
        print(elem, end=' ')
    print()


def usage() -> None:
    '''print usage information'''

    print('usage: %s [options]' % PROGNAME)
    print('options:')
    print('  -h, --help                  Display this information')
    print('  -c, --conf=FILE             Use this config file')
    print('                              (default: %s)' % param.DEFAULT_CONF)

    print('''  -l, --list-nodes            List all configured nodes
  -L, --list-groups           List all configured groups
  -n, --node=LIST             List all groups this node is in
  -g, --group=LIST            List all nodes in this group
  -i, --ipaddress             List selected nodes' IP address
  -r, --rsync                 List selected nodes' rsync qualifier
  -f, --filter-ignored        Do not list ignored nodes and groups
  -C, --command=COMMAND       Display setting for command
  -P, --package-manager       Display configured package manager
  -N, --numproc               Display numproc setting
  -d, --list-dirs             Display directory settings
      --prefix                Display installation prefix
      --master                Display configured master fqdn
      --slave                 Display configured slave nodes
      --nodename              Display my nodename
      --fqdn                  Display my FQDN (fully qualified domain name)
  -x, --expand=LIST           Expand given node list
  -v, --version               Display synctool version

COMMAND is a list of these: diff,ping,ssh,rsync,synctool,pkg
''')


def get_options() -> Options:
    '''parse command-line options'''

    # pylint: disable=too-many-statements,too-many-branches

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:lLn:g:irfC:PNdx:v',
                                   ['help', 'conf=', 'list-nodes',
                                    'list-groups', 'node=', 'group=',
                                    'ipaddress', 'rsync', 'filter-ignored',
                                    'command', 'package-manager', 'numproc',
                                    'list-dirs', 'prefix', 'master', 'slave',
                                    'nodename', 'fqdn', 'expand', 'version'])
    except getopt.GetoptError as reason:
        print()
        print('%s: %s' % (PROGNAME, reason))
        print()
        usage()
        sys.exit(1)

    if args:
        error('excessive arguments on command-line')
        sys.exit(1)

    options = Options()
    errors = 0

    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            param.CONF_FILE = arg
            continue

        if opt in ('-l', '--list-nodes'):
            options.set_action(ACTION_LIST_NODES, '--list-nodes')
            continue

        if opt in ('-L', '--list-groups'):
            options.set_action(ACTION_LIST_GROUPS, '--list-groups')
            continue

        if opt in ('-n', '--node'):
            options.set_action(ACTION_NODES, '--node')
            options.arg_nodenames = arg
            continue

        if opt in ('-g', '--group'):
            options.set_action(ACTION_GROUPS, '--group')
            options.arg_groups = arg
            continue

        if opt in ('-i', 'ipaddress'):
            options.ipaddress = True
            continue

        if opt in ('-r', '--rsync'):
            options.rsync = True
            continue

        if opt in ('-f', '--filter-ignored'):
            options.filter_ignored = True
            continue

        if opt in ('-C', '--command'):
            options.set_action(ACTION_CMDS, '--command')
            options.arg_cmds = arg.split(',')
            continue

        if opt in ('-P', '--package-manager'):
            options.set_action(ACTION_PKGMGR, '--package-manager')
            continue

        if opt in ('-N', '--numproc'):
            options.set_action(ACTION_NUMPROC, '--numproc')
            continue

        if opt in ('-d', '--list-dirs'):
            options.set_action(ACTION_LIST_DIRS, '--list-dirs')
            continue

        if opt == '--prefix':
            options.set_action(ACTION_PREFIX, '--prefix')
            continue

        if opt == '--master':
            options.set_action(ACTION_MASTER, '--master')
            continue

        if opt == '--slave':
            options.set_action(ACTION_SLAVE, '--slave')
            continue

        if opt == '--nodename':
            options.set_action(ACTION_NODENAME, '--nodename')
            continue

        if opt == '--fqdn':
            options.set_action(ACTION_FQDN, '--fqdn')
            continue

        if opt in ('-x', '--expand'):
            options.set_action(ACTION_EXPAND, '--expand')
            options.arg_expand = arg
            continue

        if opt in ('-v', '--version'):
            options.set_action(ACTION_VERSION, '--version')
            continue

        error("unknown command line option '%s'" % opt)
        errors += 1

    if errors:
        usage()
        sys.exit(1)

    if not options.action:
        usage()
        sys.exit(1)

    return options


@catch_signals
def main() -> int:
    '''do your thing'''

    # pylint: disable=too-many-statements,too-many-branches

    param.init()

    opts = get_options()

    if opts.action == ACTION_VERSION:
        print(param.VERSION)
        sys.exit(0)

    if opts.action == ACTION_FQDN:
        print(socket.getfqdn())
        sys.exit(0)

    config.read_config()
#    synctool.nodeset.make_default_nodeset()

    if opts.action == ACTION_LIST_NODES:
        list_all_nodes(opts)

    elif opts.action == ACTION_LIST_GROUPS:
        list_all_groups(opts)

    elif opts.action == ACTION_NODES:
        if not opts.arg_nodenames:
            error("option '--node' requires an argument; the node name")
            sys.exit(1)

        list_nodes(opts.arg_nodenames, opts)

    elif opts.action == ACTION_GROUPS:
        if not opts.arg_groups:
            error("option '--node-group' requires an argument; "
                  "the node group name")
            sys.exit(1)

        list_nodegroups(opts.arg_groups, opts)

    elif opts.action == ACTION_CMDS:
        list_commands(opts.arg_cmds)

    elif opts.action == ACTION_PKGMGR:
        print(param.PACKAGE_MANAGER)

    elif opts.action == ACTION_NUMPROC:
        print(param.NUM_PROC)

    elif opts.action == ACTION_LIST_DIRS:
        list_dirs()

    elif opts.action == ACTION_PREFIX:
        print(param.ROOTDIR)

    elif opts.action == ACTION_NODENAME:
        config.init_mynodename()

        if not param.NODENAME:
            error('unable to determine my nodename (%s)' %
                  param.HOSTNAME)
            stderr('please check %s' % param.CONF_FILE)
            sys.exit(1)

        print(param.NODENAME)

    elif opts.action == ACTION_MASTER:
        print(param.MASTER)

    elif opts.action == ACTION_SLAVE:
        if not param.SLAVES:
            print('(none)')
        else:
            for node in param.SLAVES:
                print(node, end=' ')
            print()

    elif opts.action == ACTION_EXPAND:
        if not opts.arg_expand:
            print('none')
        else:
            expand(opts.arg_expand)

    else:
        raise RuntimeError('bug: unknown ACTION code %d' % opts.action)
    return 0

# EOB
