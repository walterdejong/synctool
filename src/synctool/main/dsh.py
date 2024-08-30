#
#   synctool.main.dsh.py    WJ109
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''A command for invoking remote commands on the synctool nodes'''

import os
import sys
import getopt
import shlex

from typing import List, Optional

from synctool import config, param
import synctool.aggr
import synctool.configparser
import synctool.lib
from synctool.lib import verbose, error
from synctool.main.wrapper import catch_signals
import synctool.multiplex
import synctool.nodeset
import synctool.parallel
import synctool.range
import synctool.unbuffered

# hardcoded name because otherwise we get "dsh.py"
PROGNAME = 'dsh'

# ugly globals in use by parallel worker
NODESET = synctool.nodeset.NodeSet()
SSH_CMD_ARR: List[str] = []
REMOTE_CMD_ARR: List[str] = []
SSH_CTL_CMD: Optional[str] = None
OPT_SKIP_RSYNC = False
# boolean saying whether we should sync the script to the nodes
# before running it
# It allows you to edit a script on the master node, and then
# immediately run it using 'dsh'
SYNC_IT = False


class Options:
    '''represents program options and arguments'''

    def __init__(self) -> None:
        '''initialize instance'''

        self.aggregate = False
        self.master_opts: List[str] = []
        self.cmd_argv: List[str] = []           # command to run remote
        self.ssh_options = ''
        self.ssh_multiplex = False
        self.ssh_persist: Optional[str] = None


def run_dsh(address_list: List[str], remote_cmd_arr: List[str], ssh_options: str = '') -> None:
    '''run remote command to a set of nodes using ssh (param ssh_cmd)'''

    global SSH_CMD_ARR, REMOTE_CMD_ARR, SYNC_IT                     # pylint: disable=global-statement

    if os.sep not in remote_cmd_arr[0]:
        # if the command is under scripts/, assume its full path
        # This is nice because scripts/ isn't likely to be in PATH
        # It is moderately evil however, because it's not 100% correct
        # but it's reliable enough to keep in here
        full_path = os.path.join(param.SCRIPT_DIR, remote_cmd_arr[0])
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            remote_cmd_arr[0] = full_path
            # sync the script to the node
            SYNC_IT = True

    elif remote_cmd_arr[0][:len(param.SCRIPT_DIR)+1] == param.SCRIPT_DIR + os.sep:
        # sync the script to the node
        SYNC_IT = True

    SSH_CMD_ARR = shlex.split(param.SSH_CMD)

    if ssh_options:
        SSH_CMD_ARR.extend(shlex.split(ssh_options))
        # if -N 1, force tty allocation
        if param.NUM_PROC <= 1 and '-t' not in SSH_CMD_ARR:
            SSH_CMD_ARR.append('-t')
            # remove option -T (disable tty allocation)
            if '-T' in SSH_CMD_ARR:
                SSH_CMD_ARR.remove('-T')

    REMOTE_CMD_ARR = remote_cmd_arr

    synctool.parallel.do(worker_ssh, address_list)


def worker_ssh(addr: str) -> None:
    '''worker process: sync script and run ssh+command to the node'''

    # Note that this func even runs ssh to the local node if
    # the master is also managed by synctool
    # This is completely intentional, and it resolves certain
    # issues with shell quoted commands on the dsh cmd line

    nodename = NODESET.get_nodename_from_address(addr)

    # use ssh connection multiplexing (if possible)
    use_multiplex = synctool.multiplex.use_mux(nodename)

    if SYNC_IT and not (OPT_SKIP_RSYNC or nodename in param.NO_RSYNC):
        # first, sync the script to the node using rsync
        # REMOTE_CMD_ARR[0] is the full path to the cmd in SCRIPT_DIR
        verbose('running rsync $SYNCTOOL/scripts/%s to node %s' %
                (os.path.basename(REMOTE_CMD_ARR[0]), nodename))

        cmd_arr = shlex.split(param.RSYNC_CMD)

        # add "-e ssh_cmd" to rsync command
        ssh_cmd_arr = shlex.split(param.SSH_CMD)
        if use_multiplex:
            synctool.multiplex.ssh_args(ssh_cmd_arr, nodename)
        cmd_arr.extend(['-e', ' '.join(ssh_cmd_arr)])

        # safety first; do not use --delete here
        if '--delete' in cmd_arr:
            cmd_arr.remove('--delete')
        if '--delete-excluded' in cmd_arr:
            cmd_arr.remove('--delete-excluded')

        cmd_arr.append('--')
        cmd_arr.append('%s' % REMOTE_CMD_ARR[0])
        cmd_arr.append('%s:%s' % (addr, REMOTE_CMD_ARR[0]))
        synctool.lib.run_with_nodename(cmd_arr, nodename)

    cmd_str = ' '.join(REMOTE_CMD_ARR)

    # create local copy
    # or else parallelism may screw things up
    ssh_cmd_arr = SSH_CMD_ARR[:]

    verbose('running %s to %s %s' % (os.path.basename(SSH_CMD_ARR[0]),
                                     nodename, cmd_str))

    # add extra arguments for ssh multiplexing (if OK to use)
    if use_multiplex:
        synctool.multiplex.ssh_args(ssh_cmd_arr, nodename)

    ssh_cmd_arr.append('--')
    ssh_cmd_arr.append(addr)
    ssh_cmd_arr.extend(REMOTE_CMD_ARR)

    # execute ssh+remote command and show output with the nodename
    if param.NUM_PROC <= 1:
        # run with -N 1 : wait on prompts, flush output
        print(nodename + ': ', end=' ')
        synctool.lib.exec_command(ssh_cmd_arr)
    else:
        # run_with_nodename() shows the nodename, but
        # does not expect any prompts while running the cmd
        synctool.lib.run_with_nodename(ssh_cmd_arr, nodename)


def start_multiplex(address_list: List[str], ssh_persist: Optional[str] = None) -> None:
    '''run ssh -M to each node in address_list'''

    # allow this only on the master node because of security considerations
    if param.MASTER != param.HOSTNAME:
        verbose('master %s != hostname %s' % (param.MASTER,
                                              param.HOSTNAME))
        error('not running on the master node')
        sys.exit(-1)

    if ssh_persist is None:
        # use default from synctool.conf
        ssh_persist = param.CONTROL_PERSIST
    else:
        # spellcheck the parameter
        mpar = synctool.configparser.PERSIST_TIME.match(ssh_persist)
        if not mpar:
            error("invalid persist value '%s'" % ssh_persist)
            return

    # make list of nodenames
    nodes = [NODESET.get_nodename_from_address(x) for x in address_list]

    # make list of pairs: (addr, nodename)
    pairs = list(zip(address_list, nodes))
    synctool.multiplex.setup_master(pairs, ssh_persist)


def control_multiplex(address_list: List[str], ssh_options: str = '') -> None:
    '''run ssh -O ctl_cmd to each node in address_list'''

    global SSH_CMD_ARR                                              # pylint: disable=global-statement

    assert SSH_CTL_CMD is not None

    synctool.multiplex.detect_ssh()
    assert synctool.multiplex.SSH_VERSION is not None
    if synctool.multiplex.SSH_VERSION < 39:
        error('unsupported version of ssh')
        sys.exit(-1)

    SSH_CMD_ARR = shlex.split(param.SSH_CMD)

    if ssh_options:
        SSH_CMD_ARR.extend(shlex.split(ssh_options))

    synctool.parallel.do(_ssh_control, address_list)


def _ssh_control(addr: str) -> None:
    '''run ssh -O CTL_CMD addr'''

    nodename = NODESET.get_nodename_from_address(addr)
    assert SSH_CTL_CMD is not None
    okay = synctool.multiplex.control(nodename, addr, SSH_CTL_CMD)

    if SSH_CTL_CMD == 'check':
        if okay:
            if not synctool.lib.QUIET:
                print('%s: ssh master running' % nodename)
        else:
            print('%s: ssh master not running' % nodename)

    elif SSH_CTL_CMD == 'stop':
        if not synctool.lib.QUIET:
            if okay:
                print('%s: ssh master stopped' % nodename)
            else:
                print('%s: ssh master not running' % nodename)

    elif SSH_CTL_CMD == 'exit':
        if not synctool.lib.QUIET:
            if okay:
                print('%s: ssh master exiting' % nodename)
            else:
                print('%s: ssh master not running' % nodename)


def check_cmd_config() -> None:
    '''check whether the commands as given in synctool.conf actually exist'''

    errors = 0

    okay, param.SSH_CMD = config.check_cmd_config('ssh_cmd', param.SSH_CMD)
    if not okay:
        errors += 1

    if not OPT_SKIP_RSYNC:
        okay, param.RSYNC_CMD = config.check_cmd_config('rsync_cmd', param.RSYNC_CMD)
        if not okay:
            errors += 1

    if errors > 0:
        sys.exit(-1)


def usage() -> None:
    '''print usage information'''

    print('usage: %s [options] <remote command>' % PROGNAME)
    print('options:')
    print('  -h, --help                  Display this information')
    print('  -c, --conf=FILE             Use this config file')
    print(('                              (default: %s)' %
           param.DEFAULT_CONF))
    print('''  -n, --node=LIST             Execute only on these nodes
  -g, --group=LIST            Execute only on these groups of nodes
  -x, --exclude=LIST          Exclude these nodes from the selected group
  -X, --exclude-group=LIST    Exclude these groups from the selection
  -a, --aggregate             Condense output
  -o, --options=SSH_OPTIONS   Set additional options for ssh
  -M, --master, --multiplex   Start ssh connection multiplexing
  -P, --persist=TIME          Pass ssh ControlPersist timeout
  -O CTL_CMD                  Control ssh master processes
  -N, --numproc=NUM           Set number of concurrent procs
  -z, --zzz=NUM               Sleep NUM seconds between each run
      --no-nodename           Do not prepend nodename to output
      --unix                  Output actions as unix shell commands
  -v, --verbose               Be verbose
  -a, --aggregate             Condense output; list nodes per change
      --skip-rsync            Do not sync commands from the scripts/ dir
                              (eg. when it is on a shared filesystem)

CTL_CMD can be: check, stop, exit
''')


def get_options() -> Options:
    '''parse command-line options'''

    # pylint: disable=too-many-statements,too-many-branches

    global SSH_CTL_CMD, OPT_SKIP_RSYNC                                  # pylint: disable=global-statement

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:n:g:x:X:o:MP:O:N:z:vqa',
                                   ['help', 'conf=', 'node=', 'group=',
                                    'exclude=', 'exclude-group=', 'aggregate',
                                    'options=', 'master', 'multiplex',
                                    'persist=', 'numproc=', 'zzz=',
                                    'no-nodename', 'unix', 'verbose',
                                    'aggregate', 'skip-rsync', 'quiet'])
    except getopt.GetoptError as reason:
        print('%s: %s' % (PROGNAME, reason))
        # usage()
        sys.exit(1)

    # first read the config file
    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            param.CONF_FILE = arg
            continue

        # these options influence program output, so process them
        # as soon as possible, even before reading the config file
        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

    config.read_config()
    synctool.nodeset.make_default_nodeset()
    check_cmd_config()

    # then process the other options
    options = Options()
    options.master_opts = [sys.argv[0], ]

    for opt, arg in opts:
        if opt:
            options.master_opts.append(opt)
        if arg:
            options.master_opts.append(arg)

        if opt in ('-h', '--help', '-?', '-c', '--conf'):
            continue

        if opt in ('-n', '--node'):
            NODESET.add_node(arg)
            continue

        if opt in ('-g', '--group'):
            NODESET.add_group(arg)
            continue

        if opt in ('-x', '--exclude'):
            NODESET.exclude_node(arg)
            continue

        if opt in ('-X', '--exclude-group'):
            NODESET.exclude_group(arg)
            continue

        if opt in ('-o', '--options'):
            options.ssh_options = arg
            continue

        if opt in ('-M', '--master', '--multiplex'):
            options.ssh_multiplex = True
            continue

        if opt in ('-P', '--persist'):
            options.ssh_persist = arg
            # spellcheck it later
            continue

        if opt == '-O':
            if SSH_CTL_CMD is not None:
                print("%s: only a single '-O' option can be given" % PROGNAME)
                sys.exit(1)

            if arg not in ('check', 'stop', 'exit'):
                print("%s: unknown control command '%s'" % (PROGNAME, arg))
                sys.exit(1)

            SSH_CTL_CMD = arg
            continue

        if opt in ('-N', '--numproc'):
            try:
                param.NUM_PROC = int(arg)
            except ValueError:
                print(("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt)))
                sys.exit(1)

            if param.NUM_PROC < 1:
                print('%s: invalid value for numproc' % PROGNAME)
                sys.exit(1)

            continue

        if opt in ('-z', '--zzz'):
            try:
                param.SLEEP_TIME = int(arg)
            except ValueError:
                print(("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt)))
                sys.exit(1)

            if param.SLEEP_TIME < 0:
                print('%s: invalid value for sleep time' % PROGNAME)
                sys.exit(1)

            if not param.SLEEP_TIME:
                # (temporarily) set to -1 to indicate we want
                # to run serialized
                # synctool.parallel.do() will use this
                param.SLEEP_TIME = -1

            continue

        if opt in ('-a', '--aggregate'):
            options.aggregate = True
            continue

        if opt == '--no-nodename':
            synctool.lib.OPT_NODENAME = False
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

        if opt == '--skip-rsync':
            OPT_SKIP_RSYNC = True
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
            continue

    if not options.ssh_multiplex and options.ssh_persist is not None:
        print('%s: option --persist requires option --master' % PROGNAME)
        sys.exit(1)

    if options.ssh_multiplex and SSH_CTL_CMD is not None:
        print('%s: options --master and -O can not be combined' % PROGNAME)
        sys.exit(1)

    if options.ssh_multiplex or SSH_CTL_CMD is not None:
        if args:
            print('%s: excessive arguments on command-line' % PROGNAME)
            sys.exit(1)

    elif not args:
        print('%s: missing remote command' % PROGNAME)
        sys.exit(1)

    if args:
        options.master_opts.extend(args)

    options.cmd_argv = args
    return options


@catch_signals
def main() -> int:
    '''run the program'''

    param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)             # type: ignore
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)             # type: ignore

    try:
        opts = get_options()
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if opts.aggregate:
        if not synctool.aggr.run(opts.master_opts):
            sys.exit(-1)

        sys.exit(0)

    config.init_mynodename()

    address_list = NODESET.addresses()
    if not address_list:
        error('no valid nodes specified')
        sys.exit(1)

    if opts.ssh_multiplex:
        start_multiplex(address_list, opts.ssh_persist)
    elif SSH_CTL_CMD is not None:
        control_multiplex(address_list, opts.ssh_options)
    else:
        run_dsh(address_list, opts.cmd_argv, opts.ssh_options)
    return 0

# EOB
