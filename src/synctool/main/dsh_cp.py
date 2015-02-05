#
#   synctool.main.dsh_cp.py    WJ109
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''A command for copying files from master node to target nodes'''

import os
import sys
import getopt
import shlex

import synctool.aggr
import synctool.config
import synctool.lib
from synctool.lib import stdout, error, unix_out
import synctool.multiplex
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.parallel
import synctool.param
import synctool.unbuffered

# hardcoded name because otherwise we get "dsh_cp.py"
PROGNAME = 'dsh-cp'

NODESET = synctool.nodeset.NodeSet()

DESTDIR = None
OPT_AGGREGATE = False
MASTER_OPTS = None
DSH_CP_OPTIONS = None
OPT_PURGE = False

# ugly globals help parallelism
DSH_CP_CMD_ARR = None
SOURCE_LIST = None
FILES_STR = None


def run_remote_copy(address_list, files):
    '''copy files[] to nodes[]'''

    global DSH_CP_CMD_ARR, SOURCE_LIST, FILES_STR

    errs = 0
    sourcelist = []
    for filename in files:
        if not filename:
            continue

        if not synctool.lib.path_exists(filename):
            error('no such file or directory: %s' % filename)
            errs += 1
            continue

        # for directories, append a '/' slash
        if os.path.isdir(filename) and not filename[-1] == os.sep:
            sourcelist.append(filename + os.sep)
        else:
            sourcelist.append(filename)

    if errs > 0:
        sys.exit(-1)

    SOURCE_LIST = sourcelist
    FILES_STR = ' '.join(sourcelist)    # only used for printing

    DSH_CP_CMD_ARR = shlex.split(synctool.param.RSYNC_CMD)

    if not OPT_PURGE:
        if '--delete' in DSH_CP_CMD_ARR:
            DSH_CP_CMD_ARR.remove('--delete')
        if '--delete-excluded' in DSH_CP_CMD_ARR:
            DSH_CP_CMD_ARR.remove('--delete-excluded')

    if synctool.lib.VERBOSE:
        if '-q' in DSH_CP_CMD_ARR:
            DSH_CP_CMD_ARR.remove('-q')
        if '--quiet' in DSH_CP_CMD_ARR:
            DSH_CP_CMD_ARR.remove('--quiet')

    if synctool.lib.QUIET:
        if not '-q' in DSH_CP_CMD_ARR and not '--quiet' in DSH_CP_CMD_ARR:
            DSH_CP_CMD_ARR.append('-q')

    if DSH_CP_OPTIONS:
        DSH_CP_CMD_ARR.extend(shlex.split(DSH_CP_OPTIONS))

    synctool.parallel.do(worker_dsh_cp, address_list)


def worker_dsh_cp(addr):
    '''do remote copy to node'''

    nodename = NODESET.get_nodename_from_address(addr)
    if nodename == synctool.param.NODENAME:
        # do not copy to local node; files are already here
        return

    # the fileset already has been added to DSH_CP_CMD_ARR

    # use ssh connection multiplexing (if possible)
    use_multiplex = synctool.multiplex.use_mux(nodename, addr)

    # create local copy of DSH_CP_CMD_ARR
    # or parallelism may screw things up
    dsh_cp_cmd_arr = DSH_CP_CMD_ARR[:]

    # add ssh cmd
    ssh_cmd_arr = shlex.split(synctool.param.SSH_CMD)
    if use_multiplex:
        synctool.multiplex.ssh_args(ssh_cmd_arr, nodename)

    dsh_cp_cmd_arr.extend(['-e', ' '.join(ssh_cmd_arr)])
    dsh_cp_cmd_arr.append('--')
    dsh_cp_cmd_arr.extend(SOURCE_LIST)
    dsh_cp_cmd_arr.append('%s:%s' % (addr, DESTDIR))

    msg = 'copy %s to %s' % (FILES_STR, DESTDIR)
    if synctool.lib.DRY_RUN:
        msg += ' (dry run)'
    if synctool.lib.OPT_NODENAME:
        msg = ('%s: ' % nodename) + msg
    stdout(msg)

    if not synctool.lib.DRY_RUN:
        synctool.lib.run_with_nodename(dsh_cp_cmd_arr, nodename)
    else:
        unix_out(' '.join(dsh_cp_cmd_arr) + '    # dry run')


def check_cmd_config():
    '''check whether the commands as given in synctool.conf actually exist'''

    (ok, synctool.param.RSYNC_CMD) = synctool.config.check_cmd_config(
                                        'rsync_cmd', synctool.param.RSYNC_CMD)
    if not ok:
        sys.exit(-1)


def usage():
    '''print usage information'''

    print 'usage: %s [options] FILE [..] DESTDIR|:' % PROGNAME
    print ('''options:
  -h, --help                  Display this information
  -c, --conf=FILE             Use this config file
                              (default: %s)''' % synctool.param.DEFAULT_CONF)
    print '''  -n, --node=LIST             Execute only on these nodes
  -g, --group=LIST            Execute only on these groups of nodes
  -x, --exclude=LIST          Exclude these nodes from the selected group
  -X, --exclude-group=LIST    Exclude these groups from the selection
  -o, --options=options       Add options to rsync
  -p, --purge                 Delete extraneous files from dest dir
      --no-nodename           Do not prepend nodename to output
  -N, --numproc=NUM           Set number of concurrent procs
  -z, --zzz=NUM               Sleep NUM seconds between each run
      --unix                  Output actions as unix shell commands
  -v, --verbose               Be verbose
  -a, --aggregate             Condense output; list nodes per change
  -f, --fix                   Perform copy (otherwise, do dry-run)

DESTDIR may be ':' (colon) meaning the directory of the first source file
'''


def get_options():
    '''parse command-line options'''

    global DESTDIR, MASTER_OPTS, OPT_AGGREGATE, DSH_CP_OPTIONS, OPT_PURGE

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    DESTDIR = None
    DSH_CP_OPTIONS = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:n:g:x:X:o:pN:z:vqaf',
            ['help', 'conf=', 'node=', 'group=', 'exclude=', 'exclude-group=',
             'options=', 'purge', 'no-nodename', 'numproc=', 'zzz=',
             'unix', 'verbose', 'quiet', 'aggregate', 'fix'])
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
            synctool.param.CONF_FILE = arg
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

    synctool.config.read_config()
    synctool.nodeset.make_default_nodeset()
    check_cmd_config()

    # then process the other options
    MASTER_OPTS = [ sys.argv[0] ]

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

        if opt in ('-o', '--options'):
            DSH_CP_OPTIONS = arg
            continue

        if opt in ('-p', '--purge'):
            OPT_PURGE = True
            continue

        if opt == '--no-nodename':
            synctool.lib.OPT_NODENAME = False
            continue

        if opt in ('-N', '--numproc'):
            try:
                synctool.param.NUM_PROC = int(arg)
            except ValueError:
                print ("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt))
                sys.exit(1)

            if synctool.param.NUM_PROC < 1:
                print '%s: invalid value for numproc' % PROGNAME
                sys.exit(1)

            continue

        if opt in ('-z', '--zzz'):
            try:
                synctool.param.SLEEP_TIME = int(arg)
            except ValueError:
                print ("%s: option '%s' requires a numeric value" %
                       (PROGNAME, opt))
                sys.exit(1)

            if synctool.param.SLEEP_TIME < 0:
                print '%s: invalid value for sleep time' % PROGNAME
                sys.exit(1)

            if not synctool.param.SLEEP_TIME:
                # (temporarily) set to -1 to indicate we want
                # to run serialized
                # synctool.lib.multiprocess() will use this
                synctool.param.SLEEP_TIME = -1

            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
            continue

        if opt in ('-a', '--aggregate'):
            OPT_AGGREGATE = True
            continue

        if opt in ('-f', '--fix'):
            synctool.lib.DRY_RUN = False
            continue

    if not args:
        print '%s: missing file to copy' % PROGNAME
        sys.exit(1)

    if len(args) < 2:
        print '%s: missing destination' % PROGNAME
        sys.exit(1)

    MASTER_OPTS.extend(args)

    DESTDIR = args.pop(-1)

    # dest may be ':' meaning that we want to copy the source dirname
    if DESTDIR == ':':
        if os.path.isdir(args[0]):
            DESTDIR = args[0]
        else:
            DESTDIR = os.path.dirname(args[0])

    # DESTDIR[0] == ':' would create "rsync to node::module"
    # which is something we don't want
    if not DESTDIR or DESTDIR[0] == ':':
        print '%s: invalid destination' % PROGNAME
        sys.exit(1)

    # ensure trailing slash
    if DESTDIR[-1] != os.sep:
        DESTDIR += os.sep

    return args


@catch_signals
def main():
    '''run the program'''

    synctool.param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

    try:
        files = get_options()
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if OPT_AGGREGATE:
        if not synctool.aggr.run(MASTER_OPTS):
            sys.exit(-1)

        sys.exit(0)

    synctool.config.init_mynodename()

    address_list = NODESET.addresses()
    if not address_list:
        error('no valid nodes specified')
        sys.exit(1)

    run_remote_copy(address_list, files)

# EOB
