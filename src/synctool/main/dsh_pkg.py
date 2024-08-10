#
#   synctool.main.dsh_pkg.py    WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is dsh-pkg on the master node. It calls synctool-client-pkg
on the target nodes
'''

import sys
import getopt
import shlex

from typing import List

from synctool import config, param
import synctool.aggr
import synctool.lib
from synctool.lib import verbose, error
import synctool.multiplex
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.parallel
import synctool.range
import synctool.unbuffered

# hardcoded name because otherwise we get "dsh_pkg.py"
PROGNAME = 'dsh-pkg'

NODESET = synctool.nodeset.NodeSet()

OPT_AGGREGATE = False

PASS_ARGS: List[str] = []
MASTER_OPTS: List[str] = []

# ugly global helps parallelism
SSH_CMD_ARR: List[str] = []


def run_remote_pkg(address_list: List[str]) -> None:
    '''run synctool-pkg on the target nodes'''

    global SSH_CMD_ARR                                              # pylint: disable=global-statement

    SSH_CMD_ARR = shlex.split(param.SSH_CMD)
    # if -N 1, force tty allocation
    if param.NUM_PROC <= 1 and '-t' not in SSH_CMD_ARR:
        SSH_CMD_ARR.append('-t')
        # remove option -T (disable tty allocation)
        if '-T' in SSH_CMD_ARR:
            SSH_CMD_ARR.remove('-T')

    synctool.parallel.do(worker_pkg, address_list)


def worker_pkg(addr: str) -> None:
    '''runs ssh + synctool-pkg to the nodes in parallel'''

    nodename = NODESET.get_nodename_from_address(addr)

    # use ssh connection multiplexing (if possible)
    use_multiplex = synctool.multiplex.use_mux(nodename)

    # make command array 'ssh node pkg_cmd'
    cmd_arr = SSH_CMD_ARR[:]

    # add extra arguments for ssh multiplexing (if OK to use)
    if use_multiplex:
        synctool.multiplex.ssh_args(cmd_arr, nodename)

    cmd_arr.append('--')
    cmd_arr.append(addr)
    cmd_arr.extend(shlex.split(param.PKG_CMD))
    cmd_arr.extend(PASS_ARGS)

    verbose('running synctool-pkg on node %s' % nodename)

    # execute ssh synctool-pkg and show output with the nodename
    if param.NUM_PROC <= 1:
        # run with -N 1 : wait on prompts, flush output
        print(nodename + ': ', end=' ')
        synctool.lib.exec_command(cmd_arr)
    else:
        # run_with_nodename() shows the nodename, but
        # does not expect any prompts while running the cmd
        synctool.lib.run_with_nodename(cmd_arr, nodename)


def rearrange_options() -> List[str]:
    '''rearrange command-line options so that getopt() behaves
    more logical for us
    '''

    # what this function does is move any arguments given after --list,
    # --install, or --remove to the back so that getopt() will treat them
    # as (loose) arguments
    # This way, you/the user can pass a package list and still append
    # a new option (like -f) at the end

    arglist = sys.argv[1:]

    new_argv = []
    pkg_list = []

    while arglist:
        arg = arglist.pop(0)

        new_argv.append(arg)

        if arg[0] == '-':
            opt = arg[1:]

            if opt in ('l', '-list', 'i', '-install', 'R', '-remove'):
                if len(arglist) <= 0:
                    break

                optional_arg = arglist[0]
                while optional_arg[0] != '-':
                    pkg_list.append(optional_arg)

                    arglist.pop(0)
                    if not arglist:
                        break

                    optional_arg = arglist[0]

    new_argv.extend(pkg_list)
    return new_argv


def check_cmd_config() -> None:
    '''check whether the commands as given in synctool.conf actually exist'''

    errors = 0

    okay, param.SSH_CMD = config.check_cmd_config('ssh_cmd', param.SSH_CMD)
    if not okay:
        errors += 1

    okay, param.PKG_CMD = config.check_cmd_config('pkg_cmd', param.PKG_CMD)
    if not okay:
        errors += 1

    if errors > 0:
        sys.exit(-1)


def there_can_be_only_one() -> None:
    '''print usage information about actions'''

    print('''Specify only one of these options:
  -l, --list   [PACKAGE ...]     List installed packages
  -i, --install PACKAGE [..]     Install package
  -R, --remove  PACKAGE [..]     Uninstall package
  -u, --update                   Update the database of available packages
  -U, --upgrade                  Upgrade all outdated packages
  -C, --clean                    Cleanup caches of downloaded packages''')
    sys.exit(1)


def usage() -> None:
    '''print usage information'''

    print('usage: %s [options] [package [..]]' % PROGNAME)
    print('options:')
    print('  -h, --help                     Display this information')
    print('  -c, --conf=FILE                Use this config file')
    print(('                                 (default: %s)' %
           param.DEFAULT_CONF))

    print('''  -n, --node=LIST                Execute only on these nodes
  -g, --group=LIST               Execute only on these groups of nodes
  -x, --exclude=LIST             Exclude these nodes from the selected group
  -X, --exclude-group=LIST       Exclude these groups from the selection
  -l, --list   [PACKAGE ...]     List installed packages
  -i, --install PACKAGE [..]     Install package
  -R, --remove  PACKAGE [..]     Uninstall package
  -u, --update                   Update the database of available packages
  -U, --upgrade                  Upgrade all outdated packages
  -C, --clean                    Cleanup caches of downloaded packages
  -N, --numproc=NUM              Set number of concurrent procs
  -z, --zzz=NUM                  Sleep NUM seconds between each run
      --unix                     Output actions as unix shell commands
  -v, --verbose                  Be verbose
  -a, --aggregate                Condense output
  -f, --fix                      Perform upgrade (otherwise, do dry-run)
  -m, --manager PACKAGE_MANAGER  (Force) select this package manager

Supported package managers are:''')

    # print list of supported package managers
    # format it at 78 characters wide
    print(' ', end=' ')
    nmgr = 2
    for pkg in param.KNOWN_PACKAGE_MANAGERS:
        if nmgr + len(pkg) + 1 <= 78:
            nmgr = nmgr + len(pkg) + 1
            print(pkg, end=' ')
        else:
            nmgr = 2 + len(pkg) + 1
            print()
            print(' ', pkg, end=' ')

    print('''

The package list must be given last
Note that --upgrade does a dry run unless you specify --fix
''')


def get_options() -> None:
    '''parse command-line options'''

    # pylint: disable=too-many-statements,too-many-branches

    global MASTER_OPTS, PASS_ARGS, OPT_AGGREGATE                    # pylint: disable=global-statement

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    # getopt() assumes that all options given after the first non-option
    # argument are all arguments (this is standard UNIX behavior, not GNU)
    # but in this case, I like the GNU way better, so re-arrange the options
    # This has odd consequences when someone gives a 'stale' --install or
    # --remove option without any argument, but hey ...

    arglist = rearrange_options()

    try:
        opts, args = getopt.getopt(arglist, 'hc:n:g:x:X:iRluUCm:fN:z:vqa',
                                   ['help', 'conf=', 'node=', 'group=',
                                    'exclude=', 'exclude-group=', 'list',
                                    'install', 'remove', 'update', 'upgrade',
                                    'clean', 'cleanup', 'manager=',
                                    'numproc=', 'zzz=', 'fix', 'verbose',
                                    'quiet', 'unix', 'aggregate'])
    except getopt.GetoptError as reason:
        print('%s: %s' % (PROGNAME, reason))
        # usage()
        sys.exit(1)

    PASS_ARGS = []
    MASTER_OPTS = [sys.argv[0], ]

    # first read the config file
    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            param.CONF_FILE = arg
            PASS_ARGS.append(opt)
            PASS_ARGS.append(arg)
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

    # then process all the other options
    #
    # Note: some options are passed on to synctool-pkg on the node, while
    #       others are not. Therefore some 'continue', while others don't

    action = 0
    needs_package_list = False

    for opt, arg in opts:
        if opt:
            MASTER_OPTS.append(opt)

        if arg:
            MASTER_OPTS.append(arg)

        if opt in ('-h', '--help', '-?', '-c', '--conf'):
            # already done
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

        if opt in ('-i', '--install'):
            action += 1
            needs_package_list = True

        if opt in ('-R', '--remove'):
            action += 1
            needs_package_list = True

        if opt in ('-l', '--list'):
            action += 1

        if opt in ('-u', '--update'):
            action += 1

        if opt in ('-U', '--upgrade'):
            action += 1

        if opt in ('-C', '--clean', '--cleanup'):
            action += 1

        if opt in ('-m', '--manager'):
            if arg not in param.KNOWN_PACKAGE_MANAGERS:
                error("unknown or unsupported package manager '%s'" % arg)
                sys.exit(1)

            param.PACKAGE_MANAGER = arg

        if opt in ('-f', '--fix'):
            synctool.lib.DRY_RUN = False

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
                # synctool.lib.multiprocess() will use this
                param.SLEEP_TIME = -1

            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True

        if opt in ('-a', '--aggregate'):
            OPT_AGGREGATE = True
            continue

        if opt:
            PASS_ARGS.append(opt)

        if arg:
            PASS_ARGS.append(arg)

    # enable logging at the master node
    PASS_ARGS.append('--masterlog')

    if args:
        MASTER_OPTS.extend(args)
        PASS_ARGS.extend(args)
    else:
        if needs_package_list:
            error('options --install and --remove require a package name')
            sys.exit(1)

    if not action:
        usage()
        sys.exit(1)

    if action > 1:
        there_can_be_only_one()


@catch_signals
def main() -> int:
    '''run the program'''

    param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)             # type: ignore
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)             # type: ignore

    try:
        get_options()
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if OPT_AGGREGATE:
        if not synctool.aggr.run(MASTER_OPTS):
            sys.exit(-1)

        sys.exit(0)

    config.init_mynodename()

    if param.MASTER != param.HOSTNAME:
        verbose('master %s != hostname %s' % (param.MASTER,
                                              param.HOSTNAME))
        error('not running on the master node')
        sys.exit(-1)

    synctool.lib.openlog()

    address_list = NODESET.addresses()
    if not address_list:
        print('no valid nodes specified')
        sys.exit(1)

    run_remote_pkg(address_list)

    synctool.lib.closelog()
    return 0

# EOB
