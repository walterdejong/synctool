#! /usr/bin/env python
#
#   synctool_master.py    WJ109
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is synctool on the master node. It calls synctool-client
on the target nodes'''

import os
import sys
import getopt
import shlex
import subprocess
import time
import tempfile
import errno

import synctool.aggr
import synctool.config
import synctool.lib
from synctool.lib import verbose, stdout, stderr, terse, unix_out, prettypath
import synctool.nodeset
import synctool.overlay
import synctool.param
import synctool.syncstat
import synctool.unbuffered
import synctool.update

NODESET = synctool.nodeset.NodeSet()

OPT_SKIP_RSYNC = False
OPT_AGGREGATE = False
OPT_CHECK_UPDATE = False
OPT_DOWNLOAD = False

PASS_ARGS = None
MASTER_OPTS = None

UPLOAD_FILE = None


class UploadFile(object):
    '''class that holds information on requested upload'''

    def __init__(self):
        self.filename = None
        self.overlay = None
        self.purge = None
        self.suffix = None
        self.node = None
        self.address = None
        self.repos_path = None

    def make_repos_path(self):
        '''make $overlay repository path from elements'''

        if self.purge:
            self._make_purge_path()
            return

        if not self.repos_path:
            fn = self.filename
            if fn[0] == '/':
                fn = fn[1:]

            overlay_dir = self.overlay
            if not overlay_dir:
                overlay_dir = 'all'

            if not self.suffix and synctool.param.REQUIRE_EXTENSION:
                self.suffix = self.node

            if not self.suffix:
                self.repos_path = os.path.join(synctool.param.OVERLAY_DIR,
                                               overlay_dir, fn)
                return

            self.repos_path = os.path.join(synctool.param.OVERLAY_DIR,
                                           overlay_dir,
                                           fn + '._' + self.suffix)
            return

        if self.suffix:
            # remove the current group suffix
            # and add the specified suffix to the filename
            self.repos_path, _ = os.path.splitext(self.repos_path)
            self.repos_path += '._' + self.suffix

        if self.overlay:
            # user supplied (maybe a different) overlay group dir
            # so take repos_filename apart and insert a new group dir
            if (self.repos_path[:synctool.param.OVERLAY_LEN] ==
                synctool.param.OVERLAY_DIR + os.sep):
                arr = self.repos_path.split(os.sep)
                overlay_arr = synctool.param.OVERLAY_DIR.split(os.sep)
                # replace the group dir with what the user gave
                arr[len(overlay_arr)] = self.overlay
                # reassemble the full path with up.overlay as group dir
                self.repos_path = os.sep.join(arr)

    def _make_purge_path(self):
        '''make $purge repository path from elements'''

        if len(self.filename) > 1 and self.filename[-1] == '/':
            # strip trailing slash
            self.filename = self.filename[:-1]

        self.repos_path = (os.path.join(synctool.param.PURGE_DIR,
                           self.purge) + os.path.dirname(self.filename))


def run_remote_synctool(address_list):
    '''run synctool on target nodes'''

    synctool.lib.multiprocess(worker_synctool, address_list)


def worker_synctool(addr):
    '''run rsync of ROOTDIR to the nodes and ssh+synctool, in parallel'''

    nodename = NODESET.get_nodename_from_address(addr)

    if nodename == synctool.param.NODENAME:
        run_local_synctool()
        return

    # rsync ROOTDIR/dirs/ to the node
    # if "it wants it"
    if not (OPT_SKIP_RSYNC or nodename in synctool.param.NO_RSYNC):
        verbose('running rsync $SYNCTOOL/ to node %s' % nodename)
        unix_out('%s %s %s:%s/' % (synctool.param.RSYNC_CMD,
                                   synctool.param.ROOTDIR, addr,
                                   synctool.param.ROOTDIR))

        # make rsync filter to include the correct dirs
        tmp_filename = rsync_include_filter(nodename)

        cmd_arr = shlex.split(synctool.param.RSYNC_CMD)
        cmd_arr.append('--filter=. %s' % tmp_filename)
        cmd_arr.append('%s/' % synctool.param.ROOTDIR)
        cmd_arr.append('%s:%s/' % (addr, synctool.param.ROOTDIR))

        # double check the rsync destination
        # our filters are like playing with fire
        if not synctool.param.ROOTDIR or (
            synctool.param.ROOTDIR == os.sep):
            stderr('cowardly refusing to rsync with rootdir == %s' %
                   synctool.param.ROOTDIR)
            sys.exit(-1)

        synctool.lib.run_with_nodename(cmd_arr, nodename)

        # delete temp file
        try:
            os.unlink(tmp_filename)
        except OSError:
            # silently ignore unlink error
            pass

    # run 'ssh node synctool_cmd'
    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    cmd_arr.append(addr)
    cmd_arr.extend(shlex.split(synctool.param.SYNCTOOL_CMD))
    cmd_arr.append('--nodename=%s' % nodename)
    cmd_arr.extend(PASS_ARGS)

    verbose('running synctool on node %s' % nodename)
    unix_out(' '.join(cmd_arr))

    synctool.lib.run_with_nodename(cmd_arr, nodename)


def run_local_synctool():
    '''run synctool on the master node itself'''

    cmd_arr = shlex.split(synctool.param.SYNCTOOL_CMD) + PASS_ARGS

    verbose('running synctool on node %s' % synctool.param.NODENAME)
    unix_out(' '.join(cmd_arr))

    synctool.lib.run_with_nodename(cmd_arr, synctool.param.NODENAME)


def rsync_include_filter(nodename):
    '''create temp file with rsync filter rules
    Include only those dirs that apply for this node
    Returns filename of the filter file'''

    try:
        (fd, filename) = tempfile.mkstemp(prefix='synctool-',
                                          dir=synctool.param.TEMP_DIR)
    except OSError as err:
        stderr('failed to create temp file: %s' % err.strerror)
        sys.exit(-1)

    try:
        f = os.fdopen(fd, 'w')
    except OSError as err:
        stderr('failed to open temp file: %s' % err.strerror)
        sys.exit(-1)

    # include $SYNCTOOL/var/ but exclude
    # the top overlay/ and delete/ dir
    with f:
        f.write('# synctool rsync filter')

        # set mygroups for this nodename
        synctool.param.NODENAME = nodename
        synctool.param.MY_GROUPS = synctool.config.get_my_groups()

        overlay_groups = os.listdir(synctool.param.OVERLAY_DIR)
        delete_groups = os.listdir(synctool.param.DELETE_DIR)
        purge_groups = os.listdir(synctool.param.PURGE_DIR)

        f.write('+ /var/overlay/\n')

        # add only the group dirs that apply
        # use three loops; (workaround rsync bug?)
        for g in synctool.param.MY_GROUPS:
            if g in overlay_groups:
                d = os.path.join(synctool.param.OVERLAY_DIR, g)
                if os.path.isdir(d):
                    f.write('+ /var/overlay/%s/\n' % g)

        f.write('- /var/overlay/*\n'
                '+ /var/delete/\n')

        for g in synctool.param.MY_GROUPS:
            if g in delete_groups:
                d = os.path.join(synctool.param.DELETE_DIR, g)
                if os.path.isdir(d):
                    f.write('+ /var/delete/%s/\n' % g)

        f.write('- /var/delete/*\n'
                '+ /var/purge/\n')

        for g in synctool.param.MY_GROUPS:
            if g in purge_groups:
                purge_root = os.path.join(synctool.param.PURGE_DIR, g)
                if not os.path.isdir(purge_root):
                    continue

                for path, _, files in os.walk(purge_root):
                    if path == purge_root:
                        # guard against user mistakes;
                        # danger of destroying the entire filesystem
                        # if it would rsync --delete the root
                        if len(files) > 0:
                            stderr('cowardly refusing to purge the root '
                                   'directory')
                            stderr('please remove any files directly '
                                   'under %s/' % prettypath(purge_root))

                            # delete temp file and exit
                            f.close()
                            try:
                                os.unlink(filename)
                            except OSError:
                                # silently ignore unlink error
                                pass

                            sys.exit(-1)
                    else:
                        f.write('+ /var/purge/%s/' % g)
                        break

        # Note: sbin/*.pyc is excluded to keep major differences in
        # Python versions (on master vs. client node) from clashing
        f.write('- /var/purge/*\n'
                '- /sbin/*.pyc\n'
                '- /lib/synctool/*.pyc\n'
                '- /lib/synctool/pkg/*.pyc\n')

    # Note: remind to delete the temp file later

    return filename


def upload_purge():
    '''upload a file/dir to $purge/group/'''

    up = UPLOAD_FILE

    # make command: rsync [-n] [-v] node:/path/ $purge/group/path/
    cmd_arr = shlex.split(synctool.param.RSYNC_CMD)

    # opts is just for the 'visual aspect'; it is displayed when --verbose
    opts = ' '
    if synctool.lib.DRY_RUN:
        cmd_arr.append('-n')
        opts += '-n '

    if synctool.lib.VERBOSE:
        cmd_arr.append('-v')
        opts += '-v '

    up.make_repos_path()

    cmd_arr.append(up.address + ':' + up.filename)
    cmd_arr.append(up.repos_path)

    verbose_path = os.path.join(prettypath(up.repos_path),
                                os.path.basename(up.filename))
    if synctool.lib.DRY_RUN:
        stdout('would be uploaded as %s' % verbose_path)

    if not synctool.lib.DRY_RUN:
        unix_out('mkdir -p %s' % up.repos_path)
        synctool.lib.mkdir_p(up.repos_path)

    # check whether the remote entry exists
    ok, isdir = _remote_isdir(up)
    if not ok:
        return

    # when uploading a single file to purge/, do not use rsync --delete
    # because it would (inadvertently) delete all existing files in the repos
    if not isdir:
        if '--delete' in cmd_arr:
            cmd_arr.remove('--delete')
        if '--delete-excluded' in cmd_arr:
            cmd_arr.remove('--delete-excluded')

    verbose('running rsync%s%s:%s to %s' % (opts, up.node, up.filename,
                                            verbose_path))
    unix_out(' '.join(cmd_arr))

    if not synctool.lib.DRY_RUN and os.path.exists(up.repos_path):
        synctool.lib.run_with_nodename(cmd_arr, up.node)
        stdout('uploaded as %s' % verbose_path)


def _remote_isdir(up):
    '''Helper function for upload_purge()
    See if the remote rsync source is a directory or a file
    Parameter 'up' is an instance of UploadFile
    Returns: tuple of booleans: (exists, isdir)'''

    cmd_arr = shlex.split(synctool.param.RSYNC_CMD)[:1]
    cmd_arr.append('--list-only')
    cmd_arr.append(up.address + ':' + up.filename)

    verbose('running rsync --list-only %s:%s' % (up.node, up.filename))
    unix_out(' '.join(cmd_arr))

    try:
        proc = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except OSError as err:
        stderr('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return False, False

    out, err = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == 255:
            stderr('failed to connect to %s' % up.node)
        elif proc.returncode == 23:
            stderr('error: no such file or directory')
        else:
            stderr('failed rsync %s:%s' % (up.node, up.filename))

        return False, False

    # output should be an 'ls -l' like line, with first a mode string
    for line in out.split('\n'):
        arr = line.split()
        mode = arr[0]
        if len(mode) == 10:     # crude test
            if mode[0] == 'd':
                # it's a directory
                verbose('remote rsync source is a directory')
                return True, True

            if mode[0] in '-lpcbs':
                # accept it as a file entry
                verbose('remote rsync source is a file entry')
                return True, False

        # some other line on stdout; just ignore it

    # got no good output
    stderr('failed to parse rsync --list-only output')
    return False, False


def _upload_callback(obj, post_dict, dir_changed=False):
    '''find the overlay path for the destination in UPLOAD_FILE'''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE_POST:
        return False, False

    if obj.dest_path == UPLOAD_FILE.filename:
        UPLOAD_FILE.repos_path = obj.src_path
        return False, False

    if synctool.lib.terse_match(UPLOAD_FILE.filename, obj.dest_path):
        # it's a terse path ; 'expand' it
        UPLOAD_FILE.filename = obj.dest_path
        UPLOAD_FILE.repos_path = obj.src_path
        return False, False

    return True, False


def upload():
    '''copy a file from a node into the overlay/ tree'''

    up = UPLOAD_FILE

    if up.filename[0] != os.sep:
        stderr('error: the filename to upload must be an absolute path')
        sys.exit(-1)

    if up.suffix and not up.suffix in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.suffix)
        sys.exit(-1)

    if up.overlay and not up.overlay in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.overlay)
        sys.exit(-1)

    if up.purge and not up.purge in synctool.param.ALL_GROUPS:
        stderr("no such group '%s'" % up.purge)
        sys.exit(-1)

    if synctool.lib.DRY_RUN and not synctool.lib.QUIET:
        stdout('DRY RUN, not uploading any files')
        terse(synctool.lib.TERSE_DRYRUN, 'not uploading any files')

    if up.purge != None:
        upload_purge()
        return

    # pretend that the current node is now the given node;
    # this is needed for find() to find the best reference for the file
    orig_nodename = synctool.param.NODENAME
    synctool.param.NODENAME = up.node
    synctool.config.insert_group(up.node, up.node)

    orig_my_groups = synctool.param.MY_GROUPS[:]
    synctool.param.MY_GROUPS = synctool.config.get_my_groups()

    # see if file is already in the repository
    synctool.overlay.visit(synctool.param.OVERLAY_DIR, _upload_callback)

    up.make_repos_path()

    synctool.param.NODENAME = orig_nodename
    synctool.param.MY_GROUPS = orig_my_groups

    verbose('%s:%s uploaded as %s' % (up.node, up.filename, up.repos_path))
    terse(synctool.lib.TERSE_UPLOAD, up.repos_path)
    unix_out('%s %s:%s %s' % (synctool.param.SCP_CMD, up.address,
                              up.filename, up.repos_path))

    if synctool.lib.DRY_RUN:
        stdout('would be uploaded as %s' % prettypath(up.repos_path))
    else:
        # mkdir in the repos (just in case it didn't exist yet)
        # note: it may well make the dir with wrong ownership, mode
        # but rsync-ing the dest to here is rather dangerous if the dest
        # is a directory or something other than a regular file
        repos_dir = os.path.dirname(up.repos_path)
        unix_out('mkdir -p %s' % repos_dir)
        synctool.lib.mkdir_p(repos_dir)

        # make scp command array
        scp_cmd_arr = shlex.split(synctool.param.SCP_CMD)
        scp_cmd_arr.append('%s:%s' % (up.address, up.filename))
        scp_cmd_arr.append(up.repos_path)

        synctool.lib.run_with_nodename(scp_cmd_arr, up.node)

        if os.path.isfile(up.repos_path):
            stdout('uploaded %s' % prettypath(up.repos_path))


def make_tempdir():
    '''create temporary directory (for storing rsync filter files)'''

    if not os.path.isdir(synctool.param.TEMP_DIR):
        try:
            os.mkdir(synctool.param.TEMP_DIR, 0750)
        except OSError as err:
            stderr('failed to create tempdir %s: %s' %
                   (synctool.param.TEMP_DIR, err.strerror))
            sys.exit(-1)


def check_cmd_config():
    '''check whether the commands as given in synctool.conf actually exist'''

    # pretty lame code
    # Maybe the _CMD params should be a dict?

    errors = 0

#    (ok, synctool.param.DIFF_CMD) = synctool.config.check_cmd_config(
#                                       'diff_cmd', synctool.param.DIFF_CMD)
#    if not ok:
#        errors += 1

#    (ok, synctool.param.PING_CMD) = synctool.config.check_cmd_config(
#                                       'ping_cmd', synctool.param.PING_CMD)
#    if not ok:
#        errors += 1

    (ok, synctool.param.SSH_CMD) = synctool.config.check_cmd_config(
                                    'ssh_cmd', synctool.param.SSH_CMD)
    if not ok:
        errors += 1

#    (ok, synctool.param.SCP_CMD) = synctool.config.check_cmd_config(
#                                       'scp_cmd', synctool.param.SCP_CMD)
#    if not ok:
#        errors += 1

    if not OPT_SKIP_RSYNC:
        (ok, synctool.param.RSYNC_CMD) = synctool.config.check_cmd_config(
                                        'rsync_cmd', synctool.param.RSYNC_CMD)
        if not ok:
            errors += 1

    (ok, synctool.param.SYNCTOOL_CMD) = synctool.config.check_cmd_config(
                                'synctool_cmd', synctool.param.SYNCTOOL_CMD)
    if not ok:
        errors += 1

#    (ok, synctool.param.PKG_CMD) = synctool.config.check_cmd_config(
#                                       'pkg_cmd', synctool.param.PKG_CMD)
#    if not ok:
#        errors += 1

    if errors > 0:
        sys.exit(1)


def be_careful_with_getopt():
    '''check sys.argv for dangerous common typo's on the command-line'''

    # be extra careful with possible typo's on the command-line
    # because '-f' might run --fix because of the way that getopt() works

    for arg in sys.argv:

        # This is probably going to give stupid-looking output
        # in some cases, but it's better to be safe than sorry

        if arg[:2] == '-d' and arg.find('f') > -1:
            print "Did you mean '--diff'?"
            sys.exit(1)

        if arg[:2] == '-r' and arg.find('f') > -1:
            if arg.count('e') >= 2:
                print "Did you mean '--reference'?"
            else:
                print "Did you mean '--ref'?"
            sys.exit(1)


def option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
    opt_upload, opt_fix, opt_group):

    '''some combinations of command-line options don't make sense;
    alert the user and abort'''

    if opt_erase_saved and (opt_diff or opt_reference or opt_upload):
        stderr("option --erase-saved can not be combined with other actions")
        sys.exit(1)

    if opt_upload and (opt_diff or opt_single or opt_reference):
        stderr("option --upload can not be combined with other actions")
        sys.exit(1)

    if opt_upload and opt_group:
        print 'option --upload and --group can not be combined'
        sys.exit(1)

    if opt_diff and (opt_single or opt_reference or opt_fix):
        stderr("option --diff can not be combined with other actions")
        sys.exit(1)

    if opt_reference and (opt_single or opt_fix):
        stderr("option --reference can not be combined with other actions")
        sys.exit(1)


def usage():
    '''print usage information'''

    print 'usage: %s [options]' % os.path.basename(sys.argv[0])
    print 'options:'
    print '  -h, --help                  Display this information'
    print '  -c, --conf=FILE             Use this config file'
    print ('                              (default: %s)' %
        synctool.param.DEFAULT_CONF)
    print '''  -n, --node=LIST             Execute only on these nodes
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
  -f, --fix                   Perform updates (otherwise, do dry-run)
      --no-post               Do not run any .post scripts
  -N, --numproc=NUM           Number of concurrent procs
  -F, --fullpath              Show full paths instead of shortened ones
  -T, --terse                 Show terse, shortened paths
      --color                 Use colored output (only for terse mode)
      --no-color              Do not color output
      --unix                  Output actions as unix shell commands
      --skip-rsync            Do not sync the repository
                              (eg. when it is on a shared filesystem)
      --version               Show current version number
      --check-update          Check for availibility of newer version
      --download              Download latest version
  -v, --verbose               Be verbose
  -q, --quiet                 Suppress informational startup messages
  -a, --aggregate             Condense output; list nodes per change

Note that synctool does a dry run unless you specify --fix

Written by Walter de Jong <walter@heiho.net> (c) 2003-2013'''


def get_options():
    '''parse command-line options'''

    global PASS_ARGS, OPT_SKIP_RSYNC, OPT_AGGREGATE
    global OPT_CHECK_UPDATE, OPT_DOWNLOAD, MASTER_OPTS
    global UPLOAD_FILE

    # check for typo's on the command-line;
    # things like "-diff" will trigger "-f" => "--fix"
    be_careful_with_getopt()

    try:
        opts, args = getopt.getopt(sys.argv[1:],
            'hc:vn:g:x:X:d:1:r:u:s:o:p:efN:FTqa',
            ['help', 'conf=', 'verbose', 'node=', 'group=',
            'exclude=', 'exclude-group=', 'diff=', 'single=', 'ref=',
            'upload=', 'suffix=', 'overlay=', 'purge=', 'erase-saved', 'fix',
            'no-post', 'numproc=', 'fullpath', 'terse', 'color', 'no-color',
            'quiet', 'aggregate', 'unix', 'skip-rsync',
            'version', 'check-update', 'download'])
    except getopt.GetoptError as reason:
        print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#        usage()
        sys.exit(1)

    if args != None and len(args) > 0:
        stderr('error: excessive arguments on command line')
        sys.exit(1)

    UPLOAD_FILE = UploadFile()

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
    MASTER_OPTS = [ sys.argv[0] ]

    # first read the config file
    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            synctool.param.CONF_FILE = arg
            PASS_ARGS.append(opt)
            PASS_ARGS.append(arg)
            continue

        if opt == '--version':
            print synctool.param.VERSION
            sys.exit(0)

    synctool.config.read_config()
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
                synctool.param.NUM_PROC = int(arg)
            except ValueError:
                print "option '%s' requires a numeric value" % opt
                sys.exit(1)

            if synctool.param.NUM_PROC < 1:
                print 'invalid value for numproc'
                sys.exit(1)

            continue

        if opt in ('-F', '--fullpath'):
            synctool.param.FULL_PATH = True
            synctool.param.TERSE = False

        if opt in ('-T', '--terse'):
            synctool.param.TERSE = True
            synctool.param.FULL_PATH = False

        if opt == '--color':
            synctool.param.COLORIZE = True

        if opt == '--no-color':
            synctool.param.COLORIZE = False

        if opt in ('-a', '--aggregate'):
            OPT_AGGREGATE = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True

        if opt == '--skip-rsync':
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

    # do basic checks for uploading and sub options
    if opt_suffix and not opt_upload:
        print 'option --suffix must be used in conjunction with --upload'
        sys.exit(1)

    if opt_overlay and not opt_upload:
        print 'option --overlay must be used in conjunction with --upload'
        sys.exit(1)

    if opt_purge:
        if not opt_upload:
            print 'option --purge must be used in conjunction with --upload'
            sys.exit(1)

        if opt_overlay:
            print 'option --overlay and --purge can not be combined'
            sys.exit(1)

        if opt_suffix:
            print 'option --suffix and --purge can not be combined'
            sys.exit(1)

    # enable logging at the master node
    PASS_ARGS.append('--masterlog')

    if args != None:
        MASTER_OPTS.extend(args)
        PASS_ARGS.extend(args)

    option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
                        opt_upload, opt_fix, opt_group)


def main():
    '''run the program'''

    synctool.param.init()

    sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
    sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

    get_options()

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

    synctool.config.init_mynodename()
    synctool.lib.openlog()

    address_list = NODESET.addresses()
    if not address_list:
        print 'no valid nodes specified'
        sys.exit(1)

    if UPLOAD_FILE.filename:
        # upload a file
        if len(address_list) != 1:
            print 'The option --upload can only be run on just one node'
            print ('Please use --node=nodename to specify the node '
                   'to upload from')
            sys.exit(1)

        UPLOAD_FILE.address = address_list[0]
        upload()

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
