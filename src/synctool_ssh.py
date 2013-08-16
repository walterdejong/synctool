#! /usr/bin/env python
#
#   synctool-ssh    WJ109
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
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
import time
import errno

import synctool.aggr
import synctool.config
import synctool.lib
from synctool.lib import verbose, unix_out
import synctool.nodeset
import synctool.param
import synctool.unbuffered

NODESET = synctool.nodeset.NodeSet()

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
MASTER_OPTS = None
SSH_OPTIONS = None

# ugly globals help parallelism
SSH_CMD_ARR = None
REMOTE_CMD_ARR = None

# boolean saying whether we should sync the script to the nodes
# before running it
# It allows you to edit a script on the master node, and then
# immediately run it using 'dsh' / 'synctool-ssh'
SYNC_IT = False


def run_dsh(address_list, remote_cmd_arr):
    '''run remote command to a set of nodes using ssh (param ssh_cmd)'''

    global SSH_CMD_ARR, REMOTE_CMD_ARR, SYNC_IT

    # if the command is under scripts/, assume its full path
    # This is nice because scripts/ isn't likely to be in PATH
    # It is moderately evil however, because it's not 100% correct
    # but it's reliable enough to keep in here
    full_path = synctool.lib.search_path(remote_cmd_arr[0])
    if not full_path:
        # command was not found in PATH
        # look under scripts/
        full_path = os.path.join(synctool.param.SCRIPT_DIR, remote_cmd_arr[0])
        if os.access(full_path, os.X_OK):
            # found the command under scripts/
            remote_cmd_arr[0] = full_path
            # sync the script to the node
            SYNC_IT = True
    elif (full_path[:len(synctool.param.SCRIPT_DIR)+1] ==
          synctool.param.SCRIPT_DIR + os.sep):
        SYNC_IT = True

    SSH_CMD_ARR = shlex.split(synctool.param.SSH_CMD)

    if SSH_OPTIONS:
        SSH_CMD_ARR.extend(shlex.split(SSH_OPTIONS))

    REMOTE_CMD_ARR = remote_cmd_arr

    synctool.lib.multiprocess(worker_ssh, address_list)


def worker_ssh(addr):
    '''worker process: sync script and run ssh+command to the node'''

    nodename = NODESET.get_nodename_from_address(addr)

    if (SYNC_IT and
        not (OPT_SKIP_RSYNC or nodename in synctool.param.NO_RSYNC)):
        # first, sync the script to the node using rsync
        # REMOTE_CMD_ARR[0] is the full path to the cmd in SCRIPT_DIR
        verbose('running rsync $SYNCTOOL/scripts/%s to node %s' %
                (os.path.basename(REMOTE_CMD_ARR[0]), nodename))
        unix_out('%s %s %s:%s' % (synctool.param.RSYNC_CMD, REMOTE_CMD_ARR[0],
                                  addr, REMOTE_CMD_ARR[0]))

        cmd_arr = shlex.split(synctool.param.RSYNC_CMD)
        cmd_arr.append('%s' % REMOTE_CMD_ARR[0])
        cmd_arr.append('%s:%s' % (addr, REMOTE_CMD_ARR[0]))
        synctool.lib.run_with_nodename(cmd_arr, nodename)

    cmd_str = ' '.join(REMOTE_CMD_ARR)

    # create local copy
    # or else parallelism may screw things up
    ssh_cmd_arr = SSH_CMD_ARR[:]

    if nodename == synctool.param.NODENAME:
        verbose('running %s' % cmd_str)

        # is this node the local node? Then do not use ssh
        ssh_cmd_arr = []
    else:
        verbose('running %s to %s %s' % (os.path.basename(SSH_CMD_ARR[0]),
                                         nodename, cmd_str))
        ssh_cmd_arr.append(addr)

    ssh_cmd_arr.extend(REMOTE_CMD_ARR)

    unix_out(' '.join(ssh_cmd_arr))

    # execute ssh+remote command and show output with the nodename
    synctool.lib.run_with_nodename(ssh_cmd_arr, nodename)


def check_cmd_config():
    '''check whether the commands as given in synctool.conf actually exist'''

    errors = 0

    (ok, synctool.param.SSH_CMD) = synctool.config.check_cmd_config(
                                        'ssh_cmd', synctool.param.SSH_CMD)
    if not ok:
        errors += 1

    if not OPT_SKIP_RSYNC:
        (ok, synctool.param.RSYNC_CMD) = synctool.config.check_cmd_config(
                                        'rsync_cmd', synctool.param.RSYNC_CMD)
        if not ok:
            errors += 1

    if errors > 0:
        sys.exit(-1)


def usage():
    '''print usage information'''

    print ('usage: %s [options] <remote command>' %
        os.path.basename(sys.argv[0]))
    print 'options:'
    print '  -h, --help                     Display this information'
    print '  -c, --conf=FILE                Use this config file'
    print ('                                 (default: %s)' %
        synctool.param.DEFAULT_CONF)
    print '''  -n, --node=LIST                Execute only on these nodes
  -g, --group=LIST               Execute only on these groups of nodes
  -x, --exclude=LIST             Exclude these nodes from the selected group
  -X, --exclude-group=LIST       Exclude these groups from the selection
  -a, --aggregate                Condense output
  -o, --options=SSH_OPTIONS      Set additional options for ssh
  -N, --numproc=NUM              Set number of concurrent procs
  -z, --zzz=NUM                  Sleep NUM seconds between each run

      --no-nodename              Do not prepend nodename to output
  -v, --verbose                  Be verbose
      --unix                     Output actions as unix shell commands
      --skip-rsync               Do not sync commands from the scripts/ dir
                                 (eg. when it is on a shared filesystem)
'''


def get_options():
    '''parse command-line options'''

    global MASTER_OPTS, OPT_SKIP_RSYNC, OPT_AGGREGATE, SSH_OPTIONS

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:ao:qN:z:',
            ['help', 'conf=', 'verbose', 'node=', 'group=', 'exclude=',
            'exclude-group=', 'aggregate', 'options=', 'no-nodename',
            'unix', 'skip-rsync', 'quiet', 'numproc=', 'zzz='])
    except getopt.GetoptError as reason:
        print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#        usage()
        sys.exit(1)

    # first read the config file
    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            synctool.param.CONF_FILE = arg
            continue

    synctool.config.read_config()
    check_cmd_config()

    # then process the other options
    MASTER_OPTS = [ sys.argv[0] ]

    for opt, arg in opts:
        if opt:
            MASTER_OPTS.append(opt)
        if arg:
            MASTER_OPTS.append(arg)

        if opt in ('-h', '--help', '-?', '-c', '--conf'):
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

        if opt in ('-N', '--numproc'):
            try:
                synctool.param.NUM_PROC = int(arg)
            except ValueError:
                print ("%s: option '%s' requires a numeric value" %
                       (os.path.basename(sys.argv[0]), opt))
                sys.exit(1)

            if synctool.param.NUM_PROC < 1:
                print ('%s: invalid value for numproc' %
                       os.path.basename(sys.argv[0]))
                sys.exit(1)

            continue

        if opt in ('-z', '--zzz'):
            try:
                synctool.param.SLEEP_TIME = int(arg)
            except ValueError:
                print ("%s: option '%s' requires a numeric value" %
                       (os.path.basename(sys.argv[0]), opt))
                sys.exit(1)

            if synctool.param.SLEEP_TIME < 0:
                print ('%s: invalid value for sleep time' %
                       os.path.basename(sys.argv[0]))
                sys.exit(1)

            if not synctool.param.SLEEP_TIME:
                # (temporarily) set to -1 to indicate we want
                # to run serialized
                # synctool.lib.multiprocess() will use this
                synctool.param.SLEEP_TIME = -1

            continue

        if opt in ('-a', '--aggregate'):
            OPT_AGGREGATE = True
            continue

        if opt in ('-o', '--options'):
            SSH_OPTIONS = arg
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

        if opt in ('-q', '--quiet'):
            # silently ignore this option
            continue

    if not args:
        print '%s: missing remote command' % os.path.basename(sys.argv[0])
        sys.exit(1)

    if args != None:
        MASTER_OPTS.extend(args)

    return args


def main():
    '''run the program'''

    synctool.param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

    cmd_args = get_options()

    if OPT_AGGREGATE:
        if not synctool.aggr.run(MASTER_OPTS):
            sys.exit(-1)

        sys.exit(0)

    synctool.config.init_mynodename()

    address_list = NODESET.addresses()
    if not address_list:
        print 'no valid nodes specified'
        sys.exit(1)

    run_dsh(address_list, cmd_args)


if __name__ == '__main__':
    try:
        main()

        # workaround exception in QueueFeederThread at exit
        # which is a Python bug, really
        time.sleep(0.01)
    except IOError as ioerr:
        if ioerr.errno == errno.EPIPE:  # Broken pipe
            pass
        else:
            print ioerr.strerror

    except KeyboardInterrupt:        # user pressed Ctrl-C
        print

# EOB
