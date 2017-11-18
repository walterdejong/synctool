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

try:
    from typing import List
except ImportError:
    pass

from synctool import config, param
import synctool.aggr
import synctool.lib
from synctool.lib import verbose, error, unix_out
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.parallel
import synctool.unbuffered

# hardcoded name because otherwise we get "dsh_ping.py"
PROGNAME = 'dsh-ping'

NODESET = synctool.nodeset.NodeSet()

OPT_AGGREGATE = False

MASTER_OPTS = []    # type: List[str]


def ping_nodes(address_list):
    # type: (List[str]) -> None
    '''ping nodes in parallel'''

    synctool.parallel.do(ping_node, address_list)


def ping_node(addr):
    # type: (str) -> None
    '''ping a single node'''

    node = NODESET.get_nodename_from_address(addr)
    verbose('pinging %s' % node)
    unix_out('%s %s' % (param.PING_CMD, addr))

    packets_received = 0

    # execute ping command and show output with the nodename
    cmd = '%s %s' % (param.PING_CMD, addr)
    cmd_arr = shlex.split(cmd)

    try:
        f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT).stdout
    except OSError as err:
        error('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return

    with f:
        for line in f:
            line = line.strip()

            # argh, we have to parse output here
            #
            # on BSD, ping says something like:
            # "2 packets transmitted, 0 packets received, 100.0% packet loss"
            #
            # on Linux, ping says something like:
            # "2 packets transmitted, 0 received, 100.0% packet loss, " \
            # "time 1001ms"

            arr = line.split()
            if len(arr) > 3 and (arr[1] == 'packets' and
                                 arr[2] == 'transmitted,'):
                try:
                    packets_received = int(arr[3])
                except ValueError:
                    pass

                break

            # some ping implementations say "hostname is alive"
            # or "hostname is unreachable"
            elif len(arr) == 3 and arr[1] == 'is':
                if arr[2] == 'alive':
                    packets_received = 100

                elif arr[2] == 'unreachable':
                    packets_received = -1

    if packets_received > 0:
        print '%s: up' % node
    else:
        print '%s: not responding' % node


def check_cmd_config():
    # type: () -> None
    '''check whether the commands as given in synctool.conf actually exist'''

    ok, param.PING_CMD = config.check_cmd_config('ping_cmd', param.PING_CMD)
    if not ok:
        sys.exit(-1)


def usage():
    # type: () -> None
    '''print usage information'''

    print 'usage: %s [options]' % PROGNAME
    print 'options:'
    print '  -h, --help                     Display this information'
    print '  -c, --conf=FILE                Use this config file'
    print ('                                 (default: %s)' %
           param.DEFAULT_CONF)

    print '''  -n, --node=LIST                Execute only on these nodes
  -g, --group=LIST               Execute only on these groups of nodes
  -x, --exclude=LIST             Exclude these nodes from the selected group
  -X, --exclude-group=LIST       Exclude these groups from the selection
  -a, --aggregate                Condense output
  -N, --numproc=NUM              Set number of concurrent procs
  -z, --zzz=NUM                  Sleep NUM seconds between each run
      --unix                     Output actions as unix shell commands
  -v, --verbose                  Be verbose
'''


def get_options():
    # type: () -> None
    '''parse command-line options'''

    global MASTER_OPTS, OPT_AGGREGATE

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aN:qp:z:',
                                   ['help', 'conf=', 'verbose', 'node=',
                                    'group=', 'exclude=', 'exclude-group=',
                                    'aggregate', 'unix', 'quiet', 'numproc=',
                                    'zzz='])
    except getopt.GetoptError as reason:
        print '%s: %s' % (PROGNAME, reason)
#        usage()
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
    MASTER_OPTS = [sys.argv[0],]

    for opt, arg in opts:
        if opt:
            MASTER_OPTS.append(opt)
        if arg:
            MASTER_OPTS.append(arg)

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
            OPT_AGGREGATE = True
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
                print ("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt))
                sys.exit(1)

            if param.NUM_PROC < 1:
                print '%s: invalid value for numproc' % PROGNAME
                sys.exit(1)

            continue

        if opt in ('-z', '--zzz'):
            try:
                param.SLEEP_TIME = int(arg)
            except ValueError:
                print ("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt))
                sys.exit(1)

            if param.SLEEP_TIME < 0:
                print '%s: invalid value for sleep time' % PROGNAME
                sys.exit(1)

            if not param.SLEEP_TIME:
                # (temporarily) set to -1 to indicate we want
                # to run serialized
                # synctool.parallel.do() will use this
                param.SLEEP_TIME = -1

            continue

    if args:
        print '%s: too many arguments' % PROGNAME
        sys.exit(1)


@catch_signals
def main():
    # type: () -> None
    '''run the program'''

    param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout) # type: ignore
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr) # type: ignore

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

    address_list = NODESET.addresses()
    if not address_list:
        print 'no valid nodes specified'
        sys.exit(1)

    ping_nodes(address_list)

# EOB
