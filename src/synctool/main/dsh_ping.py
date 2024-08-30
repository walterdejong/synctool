#
#   synctool.main.dsh_ping.py   WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''ping the synctool nodes'''

import sys
import subprocess
import getopt
import shlex

from typing import List, Tuple

from synctool import config, param
import synctool.aggr
import synctool.lib
from synctool.lib import verbose, error, unix_out
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.parallel
import synctool.range
import synctool.unbuffered

# hardcoded name because otherwise we get "dsh_ping.py"
PROGNAME = 'dsh-ping'

# ugly global in use by parallel worker
NODESET = synctool.nodeset.NodeSet()


class Options:
    '''represents program options'''

    def __init__(self) -> None:
        '''initialize instance'''

        self.aggregate = False
        self.master_opts: List[str] = []


def ping_nodes(address_list: List[str]) -> None:
    '''ping nodes in parallel'''

    synctool.parallel.do(ping_node, address_list)


def ping_node(addr: str) -> None:
    '''ping a single node'''

    node = NODESET.get_nodename_from_address(addr)
    verbose('pinging %s' % node)
    unix_out('%s %s' % (param.PING_CMD, addr))

    packets_received = 0

    # execute ping command
    cmd = '%s %s' % (param.PING_CMD, addr)
    cmd_arr = shlex.split(cmd)
    try:
        with subprocess.Popen(cmd_arr,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True) as proc:
            assert proc.stdout is not None                          # this helps mypy
            for line in proc.stdout:
                packets_received, done = _parse_ping_output(line)
                if done:
                    break

        if packets_received > 0:
            print('%s: up' % node)
        else:
            print('%s: not responding' % node)

    except OSError as err:
        error('failed to run command %s: %s' % (cmd_arr[0], err.strerror))


def _parse_ping_output(line: str) -> Tuple[int, bool]:
    '''parses output of the ping command
    Returns tuple: packets_received, found

    where 'found' indicates whether the text matched at all
    When found is True, packets_received indicates
    the state of the host:
        > 0  : host is up
        <= 0 : host is down
    '''

    # on BSD, ping says something like:
    # "2 packets transmitted, 0 packets received, 100.0% packet loss"
    #
    # on Linux, ping says something like:
    # "2 packets transmitted, 0 received, 100.0% packet loss, " \
    # "time 1001ms"

    line = line.strip()
    if not line:
        return 0, False

    arr = line.split()
    if len(arr) > 3 and arr[1] == 'packets' and arr[2] == 'transmitted,':
        try:
            packets_received = int(arr[3])
            return packets_received, True
        except ValueError:
            pass

    # some ping implementations say "hostname is alive"
    # or "hostname is unreachable"
    if len(arr) == 3 and arr[1] == 'is':
        if arr[2] == 'alive':
            return 100, True

        if arr[2] == 'unreachable':
            return -1, True

    # line not recognized
    return 0, False


def check_cmd_config() -> None:
    '''check whether the commands as given in synctool.conf actually exist'''

    okay, param.PING_CMD = config.check_cmd_config('ping_cmd', param.PING_CMD)
    if not okay:
        sys.exit(-1)


def usage() -> None:
    '''print usage information'''

    print('usage: %s [options]' % PROGNAME)
    print('options:')
    print('  -h, --help                     Display this information')
    print('  -c, --conf=FILE                Use this config file')
    print(('                                 (default: %s)' %
           param.DEFAULT_CONF))

    print('''  -n, --node=LIST                Execute only on these nodes
  -g, --group=LIST               Execute only on these groups of nodes
  -x, --exclude=LIST             Exclude these nodes from the selected group
  -X, --exclude-group=LIST       Exclude these groups from the selection
  -a, --aggregate                Condense output
  -N, --numproc=NUM              Set number of concurrent procs
  -z, --zzz=NUM                  Sleep NUM seconds between each run
      --unix                     Output actions as unix shell commands
  -v, --verbose                  Be verbose
''')


def get_options() -> Options:
    '''parse command-line options'''

    # pylint: disable=too-many-statements,too-many-branches

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aN:qp:z:',
                                   ['help', 'conf=', 'verbose', 'node=',
                                    'group=', 'exclude=', 'exclude-group=',
                                    'aggregate', 'unix', 'quiet', 'numproc=',
                                    'zzz='])
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
            # already done
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
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

        if opt in ('-a', '--aggregate'):
            options.aggregate = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
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

    if args:
        print('%s: too many arguments' % PROGNAME)
        sys.exit(1)

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
        print('no valid nodes specified')
        sys.exit(1)

    ping_nodes(address_list)
    return 0

# EOB
