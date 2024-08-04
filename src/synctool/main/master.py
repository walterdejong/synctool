#
#   synctool.main.master.py WJ109
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is synctool on the master node. It calls synctool-client
on the target nodes
'''

import os
import sys
import getopt
import shlex
import tempfile

from typing import List, IO

from synctool import config, param
import synctool.aggr
import synctool.lib
from synctool.lib import verbose, stdout, stderr, error, warning, terse
from synctool.lib import prettypath
import synctool.multiplex
from synctool.main.wrapper import catch_signals
import synctool.nodeset
import synctool.overlay
import synctool.parallel
import synctool.syncstat
import synctool.unbuffered
import synctool.update
import synctool.upload

# hardcoded name because otherwise we get "synctool_master.py"
PROGNAME = 'synctool'

NODESET = synctool.nodeset.NodeSet()

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
OPT_CHECK_UPDATE = False
OPT_DOWNLOAD = False

PASS_ARGS = []          # type: List[str]
MASTER_OPTS = []        # type: List[str]

UPLOAD_FILE = synctool.upload.UploadFile()


def run_remote_synctool(address_list):
    # type: (List[str]) -> None
    '''run synctool on target nodes'''

    synctool.parallel.do(worker_synctool, address_list)


def worker_synctool(addr):
    # type: (str) -> None
    '''run rsync of ROOTDIR to the nodes and ssh+synctool, in parallel'''

    nodename = NODESET.get_nodename_from_address(addr)

    if nodename == param.NODENAME:
        run_local_synctool()
        return

    # use ssh connection multiplexing (if possible)
    use_multiplex = synctool.multiplex.use_mux(nodename)

    ssh_cmd_arr = shlex.split(param.SSH_CMD)
    if use_multiplex:
        synctool.multiplex.ssh_args(ssh_cmd_arr, nodename)

    # rsync ROOTDIR/dirs/ to the node
    # if "it wants it"
    if not (OPT_SKIP_RSYNC or nodename in param.NO_RSYNC):
        verbose('running rsync $SYNCTOOL/ to node %s' % nodename)

        # make rsync filter to include the correct dirs
        tmp_filename = rsync_include_filter(nodename)

        cmd_arr = shlex.split(param.RSYNC_CMD)
        cmd_arr.append('--filter=. %s' % tmp_filename)

        # add "-e ssh_cmd" to rsync command
        cmd_arr.extend(['-e', ' '.join(ssh_cmd_arr)])

        cmd_arr.append('--')
        cmd_arr.append('%s/' % param.ROOTDIR)
        cmd_arr.append('%s:%s/' % (addr, param.ROOTDIR))

        # double check the rsync destination
        # our filters are like playing with fire
        if not param.ROOTDIR or (param.ROOTDIR == os.sep):
            warning('cowardly refusing to rsync with rootdir == %s' %
                    param.ROOTDIR)
            sys.exit(-1)

        synctool.lib.run_with_nodename(cmd_arr, nodename)

        # delete temp file
        try:
            os.unlink(tmp_filename)
        except OSError:
            # silently ignore unlink error
            pass

    # run 'ssh node synctool_cmd'
    cmd_arr = ssh_cmd_arr[:]
    cmd_arr.append('--')
    cmd_arr.append(addr)
    cmd_arr.extend(shlex.split(param.SYNCTOOL_CMD))
    cmd_arr.append('--nodename=%s' % nodename)
    cmd_arr.extend(PASS_ARGS)

    verbose('running synctool on node %s' % nodename)
    synctool.lib.run_with_nodename(cmd_arr, nodename)


def run_local_synctool():
    # type: () -> None
    '''run synctool on the master node itself'''

    cmd_arr = shlex.split(param.SYNCTOOL_CMD) + PASS_ARGS

    verbose('running synctool on node %s' % param.NODENAME)
    synctool.lib.run_with_nodename(cmd_arr, param.NODENAME)


def rsync_include_filter(nodename):
    # type: (str) -> str
    '''create temp file with rsync filter rules
    Include only those dirs that apply for this node
    Returns filename of the filter file
    '''

    try:
        (fdesc, filename) = tempfile.mkstemp(prefix='synctool-',
                                          dir=param.TEMP_DIR)
    except OSError as err:
        error('failed to create temp file: %s' % err.strerror)
        sys.exit(-1)

    try:
        ftemp = os.fdopen(fdesc, 'w')
    except OSError as err:
        error('failed to open temp file: %s' % err.strerror)
        sys.exit(-1)

    # include $SYNCTOOL/var/ but exclude
    # the top overlay/ and delete/ dir
    with ftemp:
        ftemp.write('# synctool rsync filter')

        # set mygroups for this nodename
        param.NODENAME = nodename
        param.MY_GROUPS = config.get_my_groups()

        # slave nodes get a copy of the entire tree
        # all other nodes use a specific rsync filter
        if nodename not in param.SLAVES:
            if not (_write_overlay_filter(ftemp) and
                    _write_delete_filter(ftemp) and
                    _write_purge_filter(ftemp)):
                # an error occurred;
                # delete temp file and exit
                ftemp.close()
                try:
                    os.unlink(filename)
                except OSError:
                    # silently ignore unlink error
                    pass

                sys.exit(-1)

        # Note: sbin/*.pyc is excluded to keep major differences in
        # Python versions (on master vs. client node) from clashing
        ftemp.write('- /sbin/*.pyc\n'
                '- /lib/synctool/*.pyc\n'
                '- /lib/synctool/pkg/*.pyc\n')

    # Note: remind to delete the temp file later

    return filename


def _write_rsync_filter(fio, overlaydir, label):
    # type: (IO, str, str) -> None
    '''helper function for writing rsync filter'''

    fio.write('+ /var/%s/\n' % label)

    groups = os.listdir(overlaydir)

    # add only the group dirs that apply
    for grp in param.MY_GROUPS:
        if grp in groups:
            fdir = os.path.join(overlaydir, grp)
            if os.path.isdir(fdir):
                fio.write('+ /var/%s/%s/\n' % (label, grp))

    fio.write('- /var/%s/*\n' % label)


def _write_overlay_filter(fio):
    # type: (IO) -> bool
    '''write rsync filter rules for overlay/ tree
    Returns False on error
    '''

    _write_rsync_filter(fio, param.OVERLAY_DIR, 'overlay')
    return True


def _write_delete_filter(fio):
    # type: (IO) -> bool
    '''write rsync filter rules for delete/ tree
    Returns False on error
    '''

    _write_rsync_filter(fio, param.DELETE_DIR, 'delete')
    return True


def _write_purge_filter(fio):
    # type: (IO) -> bool
    '''write rsync filter rules for purge/ tree
    Returns False on error
    '''

    fio.write('+ /var/purge/\n')

    purge_groups = os.listdir(param.PURGE_DIR)

    # add only the group dirs that apply
    for grp in param.MY_GROUPS:
        if grp in purge_groups:
            purge_root = os.path.join(param.PURGE_DIR, grp)
            if not os.path.isdir(purge_root):
                continue

            for path, _, files in os.walk(purge_root):
                if path == purge_root:
                    # guard against user mistakes;
                    # danger of destroying the entire filesystem
                    # if it would rsync --delete the root
                    if files:
                        warning('cowardly refusing to purge the root '
                                'directory')
                        stderr('please remove any files directly '
                               'under %s/' % prettypath(purge_root))
                        return False
                else:
                    fio.write('+ /var/purge/%s/' % grp)
                    break

    fio.write('- /var/purge/*\n')
    return True


def make_tempdir():
    # type: () -> None
    '''create temporary directory (for storing rsync filter files)'''

    if not os.path.isdir(param.TEMP_DIR):
        try:
            os.mkdir(param.TEMP_DIR, 0o750)
        except OSError as err:
            error('failed to create tempdir %s: %s' %
                  (param.TEMP_DIR, err.strerror))
            sys.exit(-1)


def _check_valid_overlaydirs():
    # type: () -> bool
    '''check that the group specific dirs are valid groups
    Returns True on OK, False on error
    '''

    def _check_valid_groupdir(overlaydir, label):
        # type: (str, str) -> bool
        '''local helper function for _check_valid_overlaydirs()'''

        errs = 0
        entries = os.listdir(overlaydir)
        for entry in entries:
            fullpath = os.path.join(overlaydir, entry)
            if os.path.isdir(fullpath) and entry not in param.ALL_GROUPS:
                error("$%s/%s/ exists, but there is no such group '%s'" %
                      (label, entry, entry))
                errs += 1
                continue

        return errs == 0

    errs = 0

    # check group dirs under overlay/
    if not _check_valid_groupdir(param.OVERLAY_DIR, 'overlay'):
        errs += 1

    # check group dirs under delete/
    if not _check_valid_groupdir(param.DELETE_DIR, 'delete'):
        errs += 1

    # check group dirs under purge/
    if not _check_valid_groupdir(param.PURGE_DIR, 'purge'):
        errs += 1

    return errs == 0


def check_cmd_config():
    # type: () -> None
    '''check whether the commands as given in synctool.conf actually exist'''

    # pretty lame code
    # Maybe the _CMD params should be a dict?

    errors = 0

#    ok, param.DIFF_CMD = config.check_cmd_config('diff_cmd', param.DIFF_CMD)
#    if not ok:
#        errors += 1

#    ok, param.PING_CMD = config.check_cmd_config('ping_cmd', param.PING_CMD)
#    if not ok:
#        errors += 1

    okay, param.SSH_CMD = config.check_cmd_config('ssh_cmd', param.SSH_CMD)
    if not okay:
        errors += 1

    if not OPT_SKIP_RSYNC:
        okay, param.RSYNC_CMD = config.check_cmd_config('rsync_cmd', param.RSYNC_CMD)
        if not okay:
            errors += 1

    okay, param.SYNCTOOL_CMD = config.check_cmd_config('synctool_cmd', param.SYNCTOOL_CMD)
    if not okay:
        errors += 1

#    okay, param.PKG_CMD = config.check_cmd_config('pkg_cmd', param.PKG_CMD)
#    if not okay:
#        errors += 1

    if errors > 0:
        sys.exit(1)


def be_careful_with_getopt():
    # type: () -> None
    '''check sys.argv for dangerous common typo's on the command-line'''

    # be extra careful with possible typo's on the command-line
    # because '-f' might run --fix because of the way that getopt() works

    for arg in sys.argv:

        # This is probably going to give stupid-looking output
        # in some cases, but it's better to be safe than sorry

        if arg[:2] == '-d' and arg.find('f') > -1:
            print("Did you mean '--diff'?")
            sys.exit(1)

        if arg[:2] == '-r' and arg.find('f') > -1:
            if arg.count('e') >= 2:
                print("Did you mean '--reference'?")
            else:
                print("Did you mean '--ref'?")
            sys.exit(1)


def option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
                        opt_upload, opt_fix, opt_group):
    #pylint: disable=too-many-arguments
    # type: (bool, bool, bool, bool, bool, bool, bool) -> None
    '''some combinations of command-line options don't make sense;
    alert the user and abort
    '''

    if opt_erase_saved and (opt_diff or opt_reference or opt_upload):
        error("option --erase-saved can not be combined with other actions")
        sys.exit(1)

    if opt_upload and (opt_diff or opt_single or opt_reference):
        error("option --upload can not be combined with other actions")
        sys.exit(1)

    if opt_upload and opt_group:
        print('option --upload and --group can not be combined')
        sys.exit(1)

    if opt_diff and (opt_single or opt_reference or opt_fix):
        error("option --diff can not be combined with other actions")
        sys.exit(1)

    if opt_reference and (opt_single or opt_fix):
        error("option --reference can not be combined with other actions")
        sys.exit(1)


def usage():
    # type: () -> None
    '''print usage information'''

    print('usage: %s [options]' % PROGNAME)
    print('options:')
    print('  -h, --help                  Display this information')
    print('  -c, --conf=FILE             Use this config file')
    print(('                              (default: %s)' %
           param.DEFAULT_CONF))
    print('''  -n, --node=LIST             Execute only on these nodes
  -g, --group=LIST            Execute only on these groups of nodes
  -x, --exclude=LIST          Exclude these nodes from the selected group
  -X, --exclude-group=LIST    Exclude these groups from the selection
  -d, --diff=FILE             Show diff for file
  -1, --single=PATH           Update a single file
  -r, --ref=PATH              Show which source file synctool chooses
  -u, --upload=PATH           Pull a remote file into the overlay tree
  -s, --suffix=GROUP          Give group suffix for the uploaded file
  -o, --overlay=GROUP         Upload file to $overlay/group/
  -p, --purge=GROUP           Upload file or directory to $purge/group/
  -e, --erase-saved           Erase *.saved backup files
      --no-post               Do not run any .post scripts
  -N, --numproc=NUM           Number of concurrent procs
  -F, --fullpath              Show full paths instead of shortened ones
  -T, --terse                 Show terse, shortened paths
      --color                 Use colored output (only for terse mode)
      --no-color              Do not color output
  -S, --skip-rsync            Do not sync the repository
      --version               Show current version number
      --check-update          Check for availibility of newer version
      --download              Download latest version
      --unix                  Output actions as unix shell commands
  -v, --verbose               Be verbose
  -q, --quiet                 Suppress informational startup messages
  -a, --aggregate             Condense output; list nodes per change
  -f, --fix                   Perform updates (otherwise, do dry-run)

Note that synctool does a dry run unless you specify --fix

Written by Walter de Jong <walter@heiho.net> (c) 2003-2015''')


def get_options():
    #pylint: disable=too-many-statements, too-many-branches
    #pylint: disable=global-statement
    # type: () -> None
    '''parse command-line options'''

    global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE
    global OPT_CHECK_UPDATE, OPT_DOWNLOAD, MASTER_OPTS
    global UPLOAD_FILE

    # check for typo's on the command-line;
    # things like "-diff" will trigger "-f" => "--fix"
    be_careful_with_getopt()

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'hc:vn:g:x:X:d:1:r:u:s:o:p:efN:FTqaS',
                                   ['help', 'conf=', 'verbose', 'node=',
                                    'group=', 'exclude=', 'exclude-group=',
                                    'diff=', 'single=', 'ref=', 'upload=',
                                    'suffix=', 'overlay=', 'purge=',
                                    'erase-saved', 'fix', 'no-post',
                                    'numproc=', 'fullpath', 'terse', 'color',
                                    'no-color', 'quiet', 'aggregate', 'unix',
                                    'skip-rsync', 'version', 'check-update',
                                    'download'])
    except getopt.GetoptError as reason:
        print('%s: %s' % (PROGNAME, reason))
#        usage()
        sys.exit(1)

    if args:
        error('excessive arguments on command line')
        sys.exit(1)

    UPLOAD_FILE = synctool.upload.UploadFile()

    # these are only used for checking the validity of option combinations
    opt_diff = False
    opt_single = False
    opt_reference = False
    opt_erase_saved = False
    opt_upload = False
    opt_suffix = False
    opt_overlay = False
    opt_purge = False
    opt_fix = False
    opt_group = False

    PASS_ARGS = []
    MASTER_OPTS = [sys.argv[0],]

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

        if opt in ('-T', '--terse'):
            param.TERSE = True
            param.FULL_PATH = False
            continue

        if opt in ('-F', '--fullpath'):
            param.FULL_PATH = True
            continue

        if opt == '--version':
            print(param.VERSION)
            sys.exit(0)

    config.read_config()
    synctool.nodeset.make_default_nodeset()
    check_cmd_config()

    # then process all the other options
    #
    # Note: some options are passed on to synctool on the node, while
    # others are not. Therefore some 'continue', while others don't

    for opt, arg in opts:
        if opt:
            MASTER_OPTS.append(opt)

        if arg:
            MASTER_OPTS.append(arg)

        if opt in ('-h', '--help', '-?', '-c', '--conf', '--version'):
            # already done
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True

        if opt in ('-n', '--node'):
            NODESET.add_node(arg)

            if not UPLOAD_FILE.node:
                UPLOAD_FILE.node = arg

            continue

        if opt in ('-g', '--group'):
            NODESET.add_group(arg)
            opt_group = True
            continue

        if opt in ('-x', '--exclude'):
            NODESET.exclude_node(arg)
            continue

        if opt in ('-X', '--exclude-group'):
            NODESET.exclude_group(arg)
            continue

        if opt in ('-d', '--diff'):
            opt_diff = True

        if opt in ('-1', '--single'):
            opt_single = True

        if opt in ('-r', '--ref'):
            opt_reference = True

        if opt in ('-u', '--upload'):
            opt_upload = True
            UPLOAD_FILE.filename = arg
            continue

        if opt in ('-s', '--suffix'):
            opt_suffix = True
            UPLOAD_FILE.suffix = arg
            continue

        if opt in ('-o', '--overlay'):
            opt_overlay = True
            UPLOAD_FILE.overlay = arg
            continue

        if opt in ('-p', '--purge'):
            opt_purge = True
            UPLOAD_FILE.purge = arg
            continue

        if opt in ('-e', '--erase-saved'):
            opt_erase_saved = True

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True

        if opt in ('-f', '--fix'):
            opt_fix = True
            synctool.lib.DRY_RUN = False

        if opt == '--no-post':
            synctool.lib.NO_POST = True

        if opt in ('-N', '--numproc'):
            try:
                param.NUM_PROC = int(arg)
            except ValueError:
                print("option '%s' requires a numeric value" % opt)
                sys.exit(1)

            if param.NUM_PROC < 1:
                print('invalid value for numproc')
                sys.exit(1)

            continue

        if opt in ('-F', '--fullpath'):
            param.FULL_PATH = True
            param.TERSE = False

        if opt in ('-T', '--terse'):
            param.TERSE = True
            param.FULL_PATH = False

        if opt == '--color':
            param.COLORIZE = True

        if opt == '--no-color':
            param.COLORIZE = False

        if opt in ('-a', '--aggregate'):
            OPT_AGGREGATE = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True

        if opt in ('-S', '--skip-rsync'):
            OPT_SKIP_RSYNC = True
            continue

        if opt == '--check-update':
            OPT_CHECK_UPDATE = True
            continue

        if opt == '--download':
            OPT_DOWNLOAD = True
            continue

        if opt:
            PASS_ARGS.append(opt)

        if arg:
            PASS_ARGS.append(arg)

    # diff with fix works like single
    if opt_diff and opt_fix:
        opt_diff = False
        opt_single = True

    # do basic checks for uploading and sub options
    if opt_suffix and not opt_upload:
        print('option --suffix must be used in conjunction with --upload')
        sys.exit(1)

    if opt_overlay and not opt_upload:
        print('option --overlay must be used in conjunction with --upload')
        sys.exit(1)

    if opt_purge:
        if not opt_upload:
            print('option --purge must be used in conjunction with --upload')
            sys.exit(1)

        if opt_overlay:
            print('option --overlay and --purge can not be combined')
            sys.exit(1)

        if opt_suffix:
            print('option --suffix and --purge can not be combined')
            sys.exit(1)

    # enable logging at the master node
    PASS_ARGS.append('--masterlog')

    if args is not None:
        MASTER_OPTS.extend(args)
        PASS_ARGS.extend(args)

    option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
                        opt_upload, opt_fix, opt_group)


@catch_signals
def main():
    #pylint: disable=too-many-statements, too-many-branches
    # type: (...) -> int
    '''run the program'''

    param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout) # type: ignore
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr) # type: ignore

    try:
        get_options()
    except synctool.range.RangeSyntaxError as err:
        error(str(err))
        sys.exit(1)

    if OPT_CHECK_UPDATE:
        if not synctool.update.check():
            # no newer version available
            sys.exit(0)

        sys.exit(1)

    if OPT_DOWNLOAD:
        if not synctool.update.download():
            # download error
            sys.exit(-1)

        sys.exit(0)

    if OPT_AGGREGATE:
        if not synctool.aggr.run(MASTER_OPTS):
            sys.exit(-1)

        sys.exit(0)

    config.init_mynodename()

    if param.MASTER != param.HOSTNAME:
        verbose('master %s != hostname %s' % (param.MASTER, param.HOSTNAME))
        error('not running on the master node')
        sys.exit(-1)

    if not _check_valid_overlaydirs():
        # error message already printed
        sys.exit(-1)

    synctool.lib.openlog()

    address_list = NODESET.addresses()
    if not address_list:
        print('no valid nodes specified')
        sys.exit(1)

    if UPLOAD_FILE.filename:
        # upload a file
        if len(address_list) != 1:
            error('option --upload can only be run on just one node')
            stderr('Please use --node=nodename to specify the node '
                   'to upload from')
            sys.exit(1)

        UPLOAD_FILE.address = address_list[0]
        synctool.upload.upload(UPLOAD_FILE)

    else:
        # do regular synctool run
        # first print message about DRY RUN
        if not synctool.lib.QUIET:
            if synctool.lib.DRY_RUN:
                stdout('DRY RUN, not doing any updates')
                terse(synctool.lib.TERSE_DRYRUN, 'not doing any updates')
            else:
                stdout('--fix specified, applying changes')
                terse(synctool.lib.TERSE_FIXING, ' applying changes')
        else:
            if synctool.lib.DRY_RUN:
                verbose('DRY RUN, not doing any updates')
            else:
                verbose('--fix specified, applying changes')

        make_tempdir()
        run_remote_synctool(address_list)

    synctool.lib.closelog()
    return 0

# EOB
