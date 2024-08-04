#
#   synctool.main.client.py WJ103
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool-client is the program that runs on the target node'''

import os
import sys
import time
import shlex
import getopt
import subprocess

from typing import List, Dict, Tuple, Callable

from synctool import config, param
import synctool.lib
from synctool.lib import verbose, stdout, stderr, error, warning, terse
from synctool.lib import unix_out, prettypath
from synctool.main.wrapper import catch_signals
import synctool.overlay
import synctool.syncstat
from synctool.object import SyncObject

# hardcoded name because otherwise we get "synctool_client.py"
PROGNAME = 'synctool-client'

# get_options() returns these action codes
ACTION_DEFAULT = 0
ACTION_DIFF = 1
ACTION_ERASE_SAVED = 2
ACTION_REFERENCE = 3

SINGLE_FILES = []   # type: List[str]


def generate_template(obj, post_dict):
    #pylint: disable=too-many-lines, too-many-branches
    #pylint: disable=too-many-statements, too-many-return-statements
    # type: (SyncObject, Dict[str, str]) -> bool
    '''run template .post script, generating a new file
    The script will run in the source dir (overlay tree) and
    it will run even in dry-run mode
    Returns: True or False on error
    '''

    # Note: this func modifies input parameter 'obj'
    # when it succesfully generates output, it will change obj's paths
    # and it will be picked up again in overlay._walk_subtree()

    if synctool.lib.NO_POST:
        verbose('skipping template generation of %s' % obj.src_path)
        obj.ov_type = synctool.overlay.OV_IGNORE
        return True

    if SINGLE_FILES and obj.dest_path not in SINGLE_FILES:
        verbose('skipping template generation of %s' % obj.src_path)
        obj.ov_type = synctool.overlay.OV_IGNORE
        return True

    verbose('generating template %s' % obj.print_src())

    src_dir = os.path.dirname(obj.src_path)
    newname = os.path.join(src_dir, os.path.basename(obj.dest_path))
    template = newname + '._template'
    # add most important extension
    newname += '._' + param.NODENAME

    verbose('generating template as %s' % newname)

    statbuf = synctool.syncstat.SyncStat(newname)
    if statbuf.exists():
        verbose('template destination %s already exists' % newname)

        if param.SYNC_TIMES and statbuf.mtime != obj.src_stat.mtime:
            # force the mtime of the template onto the existing output
            verbose('forcing mtime %s => %s' % (obj.src_path, newname))
            synctool.lib.set_filetimes(newname, statbuf.atime,
                                       obj.src_stat.mtime)

        # modify the object; set new src and dest filenames
        # later, visit() will call obj.make(), which will make full paths
        obj.src_path = newname
        obj.dest_path = os.path.basename(obj.dest_path)
        return True

    # get the .post script for the template file
    if template not in post_dict:
        if param.TERSE:
            terse(synctool.lib.TERSE_ERROR, 'no .post %s' % obj.src_path)
        else:
            error('template generator for %s not found' % obj.src_path)
        return False

    generator = post_dict[template]

    # chdir to source directory
    # Note: the change dir is not really needed
    # but the documentation promises that .post scripts run in
    # the dir where the new file will be put
    verbose('  os.chdir(%s)' % src_dir)
    unix_out('cd %s' % src_dir)
    cwd = os.getcwd()
    try:
        os.chdir(src_dir)
    except OSError as err:
        if param.TERSE:
            terse(synctool.lib.TERSE_ERROR, 'chdir %s' % src_dir)
        else:
            error('failed to change directory to %s: %s' % (src_dir,
                                                            err.strerror))
        return False

    # temporarily restore original umask
    # so the script runs with the umask set by the sysadmin
    os.umask(param.ORIG_UMASK)

    # run the script
    # pass template and newname as "$1" and "$2"
    cmd_arr = [generator, obj.src_path, newname]
    verbose('  os.system(%s, %s, %s)' % (prettypath(cmd_arr[0]),
                                         cmd_arr[1], cmd_arr[2]))
    unix_out('# run command %s' % os.path.basename(cmd_arr[0]))

    have_error = False
    if synctool.lib.exec_command(cmd_arr) == -1:
        have_error = True

    statbuf = synctool.syncstat.SyncStat(newname)
    if not statbuf.exists():
        if not have_error:
            if param.TERSE:
                terse(synctool.lib.TERSE_WARNING, 'no output %s' % newname)
            else:
                warning('expected output %s was not generated' % newname)
            obj.ov_type = synctool.overlay.OV_IGNORE
        else:
            # an error message was already printed when exec() failed earlier
            # so, only when --verbose is used, print additional debug info
            verbose('error: expected output %s was not generated' % newname)
    else:
        verbose('found generated output %s' % newname)
        if param.SYNC_TIMES:
            # force the mtime of the template onto the generated output
            verbose('forcing mtime %s => %s' % (obj.src_path, newname))
            synctool.lib.set_filetimes(newname, statbuf.atime,
                                       obj.src_stat.mtime)

    os.umask(0o77)

    # chdir back to original location
    # chdir to source directory
    verbose('  os.chdir(%s)' % cwd)
    unix_out('cd %s' % cwd)
    try:
        os.chdir(cwd)
    except OSError as err:
        if param.TERSE:
            terse(synctool.lib.TERSE_ERROR, 'chdir %s' % src_dir)
        else:
            error('failed to change directory to %s: %s' % (cwd,
                                                            err.strerror))
        return False

    if have_error:
        return False

    # modify the object; set new src and dest filenames
    # later, visit() will call obj.make(), which will make full paths
    obj.src_path = newname
    obj.dest_path = os.path.basename(obj.dest_path)
    return True


def purge_files():
    # type: () -> None
    '''run the purge function'''

    paths = []
    purge_groups = os.listdir(param.PURGE_DIR)

    # find the source purge paths that we need to copy
    # scan only the group dirs that apply
    for group in param.MY_GROUPS:
        if group in purge_groups:
            purge_root = os.path.join(param.PURGE_DIR, group)
            if not os.path.isdir(purge_root):
                continue

            for path, subdirs, files in os.walk(purge_root):
                # rsync only purge dirs that actually contain files
                # otherwise rsync --delete would wreak havoc
                if not files:
                    continue

                if path == purge_root:
                    # root contains files; guard against user mistakes
                    # rsync --delete would destroy the whole filesystem
                    warning('cowardly refusing to purge the root directory')
                    stderr('please remove any files directly under %s/' %
                           prettypath(purge_root))
                    return

                # paths has (src_dir, dest_dir)
                paths.append((path, path[len(purge_root):]))

                # do not recurse into this dir any deeper
                del subdirs[:]

    cmd_rsync, opts_string = _make_rsync_purge_cmd()

    # call rsync to copy the purge dirs
    for src, dest in paths:
        # trailing slash on source path is important for rsync
        src += os.sep
        dest += os.sep

        cmd_arr = cmd_rsync[:]
        cmd_arr.append(src)
        cmd_arr.append(dest)

        verbose('running rsync%s%s %s' % (opts_string, prettypath(src), dest))
        _run_rsync_purge(cmd_arr)


def _make_rsync_purge_cmd():
    # type: () -> Tuple[List[str], str]
    '''make command array for running rsync purge
    Returns pair: cmd_arr, options_string
    cmd_arr is the rsync command + arguments
    options_string is what options you show in verbose mode
    '''

    # make rsync command array with command line arguments
    cmd_rsync = shlex.split(param.RSYNC_CMD)
    # opts is just for the 'visual aspect';
    # it is displayed when --verbose is active
    # They aren't all options, just a couple I want to show
    opts = ' '
    if synctool.lib.DRY_RUN:
        # add rsync option -n (dry run)
        cmd_rsync.append('-n')
        opts += '-n '

    # remove certain options from rsync
    for opt in ('-q', '--quiet', '-v', '--verbose', '--human-readable',
                '--progress', '--daemon'):
        if opt in cmd_rsync:
            cmd_rsync.remove(opt)

    # add rsync option -i : itemized output
    if '-i' not in cmd_rsync and '--itemize-changes' not in cmd_rsync:
        cmd_rsync.append('-i')

    # it's purge; must have --delete
    if '--delete' not in cmd_rsync:
        cmd_rsync.append('--delete')

    # show the -i and --delete option (in verbose mode)
    opts += '-i --delete '
    return cmd_rsync, opts


def _run_rsync_purge(cmd_arr):
    #pylint: disable=consider-using-with
    # type: (List[str]) -> None
    '''run rsync for purging
    cmd_arr holds already prepared rsync command + arguments
    '''

    unix_out(' '.join(cmd_arr))

    sys.stdout.flush()
    sys.stderr.flush()
    try:
        # run rsync
        proc = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                                stdout=subprocess.PIPE, universal_newlines=True)
    except OSError as err:
        error('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return

    out, _ = proc.communicate()

    if synctool.lib.VERBOSE:
        print(out)

    lines = out.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        code, filename = line.split(' ', 1)

        if code[:6] == 'ERROR:' or code[:8] == 'WARNING:':
            # output rsync errors and warnings
            stderr(line)
            continue

        if filename == './':
            # rsync has a habit of displaying ugly "./" path
            # cmd_arr[-1] is the destination path
            path = cmd_arr[-1]
        else:
            # cmd_arr[-1] is the destination path
            path = os.path.join(cmd_arr[-1], filename)

        if code[0] == '*':
            # rsync has a message for us
            # most likely "deleting"
            msg = code[1:]
            msg = msg.strip()
            stdout('%s %s (purge)' % (msg, prettypath(path)))
        else:
            stdout('%s mismatch (purge)' % prettypath(path))


def _overlay_callback(obj, pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''compare files and run post-script if needed
    Returns pair: True (continue), updated (data or metadata)
    '''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    verbose('checking %s' % obj.print_src())
    fixup = obj.check()
    updated = obj.fix(fixup, pre_dict, post_dict)
    return True, updated


def overlay_files():
    # type: () -> None
    '''run the overlay function'''

    synctool.overlay.visit(param.OVERLAY_DIR, _overlay_callback)


def _delete_callback(obj, _pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''delete files
    Returns pair: True (continue), deleted
    '''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    # don't delete directories
    if obj.src_stat.is_dir():
#       verbose('refusing to delete directory %s' % (obj.dest_path + os.sep))
        return True, False

    if obj.dest_stat.is_dir():
        warning('destination is a directory: %s, skipped' % obj.print_src())
        return True, False

    verbose('checking %s' % obj.print_src())

    if obj.dest_stat.exists():
        vnode = obj.vnode_dest_obj()
        if vnode is None:
            # error message already printed
            return True, False
        vnode.harddelete()
        obj.run_script(post_dict)
        return True, True

    return True, False


def delete_files():
    # type: () -> None
    '''run the delete/ dir'''

    synctool.overlay.visit(param.DELETE_DIR, _delete_callback)


def _erase_saved_callback(obj, _pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''erase *.saved backup files
    Returns pair: True (continue), deleted
    '''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    obj.dest_path += '.saved'
    obj.dest_stat = synctool.syncstat.SyncStat(obj.dest_path)

    # .saved directories will be removed, but only when they are empty

    if obj.dest_stat.exists():
        vnode = obj.vnode_dest_obj()
        if vnode is None:
            # error message already printed
            return True, False
        vnode.harddelete()
        return True, True

    return True, False


def erase_saved():
    # type: () -> None
    '''List and delete *.saved backup files'''

    synctool.overlay.visit(param.OVERLAY_DIR, _erase_saved_callback)
    synctool.overlay.visit(param.DELETE_DIR, _erase_saved_callback)


def visit_purge_single(callback):
    # type: (Callable[[SyncObject, Dict[str, str], Dict[str, str]], Tuple[bool, bool]]) -> None
    '''look in the purge/ dir for SINGLE_FILES, and call callback'''

    if not SINGLE_FILES:
        return

    purge_groups = os.listdir(param.PURGE_DIR)

    # use a copy of SINGLE_FILES, because the callback will remove items
    for dest in SINGLE_FILES[:]:
        filepath = dest
        if filepath[0] == os.sep:
            filepath = filepath[1:]

        for group in param.MY_GROUPS:
            if group not in purge_groups:
                continue

            src = os.path.join(param.PURGE_DIR, group, filepath)
            if synctool.lib.path_exists(src):
                # make a SyncObject
                obj = synctool.object.SyncObject(src, dest)
                obj.src_stat = synctool.syncstat.SyncStat(obj.src_path)
                obj.dest_stat = synctool.syncstat.SyncStat(obj.dest_path)

                # call the callback function
                callback(obj, {}, {})
                break


def _match_single(path):
    # type: (str) -> bool
    '''Returns True if (terse) path is in SINGLE_FILES, else False'''

    if path in SINGLE_FILES:
        SINGLE_FILES.remove(path)
        return True

    idx = synctool.lib.terse_match_many(path, SINGLE_FILES)
    if idx >= 0:
        del SINGLE_FILES[idx]
        return True

    return False


def _single_overlay_callback(obj, pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''do overlay function for single files'''

    if not SINGLE_FILES:
        # proceed quickly
        return True, False

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    go_on = True
    updated = False

    if _match_single(obj.dest_path):
        _, updated = _overlay_callback(obj, pre_dict, post_dict)
        if not updated:
            stdout('%s is up to date' % obj.dest_path)
            terse(synctool.lib.TERSE_OK, obj.dest_path)
            unix_out('# %s is up to date\n' % obj.dest_path)

    return go_on, updated


def _single_delete_callback(obj, pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''do delete function for single files'''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    go_on = True
    updated = False

    if _match_single(obj.dest_path):
        _, updated = _delete_callback(obj, pre_dict, post_dict)

        if not SINGLE_FILES:
            return False, updated

    return go_on, updated


def _single_purge_callback(obj, pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''do purge function for single files'''

    # The same as _single_overlay_callback(), except that
    # purge entries may differ in timestamp. synctool has to report
    # this because pure rsync will as well (which is bloody annoying)
    #
    # For normal synctool overlay/, it's regarded as not important
    # and synctool will not complain about it
    #
    # This actually leaves a final wart; synctool --single may create
    # purge entries that rsync will complain about and sync again
    # Anyway, I don't think it's a big deal, and that's what you get
    # when you mix up synctool and rsync

    go_on = True
    updated = False

    if _match_single(obj.dest_path):
        _, updated = _overlay_callback(obj, pre_dict, post_dict)
        if not updated:
            if obj.check_purge_timestamp():
                stdout('%s is up to date' % obj.dest_path)
                terse(synctool.lib.TERSE_OK, obj.dest_path)
                unix_out('# %s is up to date\n' % obj.dest_path)
            # else: pass

        if not SINGLE_FILES:
            return False, updated

    return go_on, updated


def single_files():
    # type: () -> None
    '''check/update a list of single files'''

    synctool.overlay.visit(param.OVERLAY_DIR,
                           _single_overlay_callback)

    # For files that were not found, look in the purge/ tree
    # Any overlay-ed files have already been removed from SINGLE_FILES
    # So purge/ won't overrule overlay/
    visit_purge_single(_single_purge_callback)

    if SINGLE_FILES:
        # there are still single files left
        # maybe they are in the delete tree?
        synctool.overlay.visit(param.DELETE_DIR,
                               _single_delete_callback)

    for filename in SINGLE_FILES:
        stderr('%s is not in the overlay tree' % filename)


def _single_erase_saved_callback(obj, pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''do 'erase saved' function for single files'''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    go_on = True
    updated = False

    # if match(): dest = True; else dest = False
    is_dest = _match_single(obj.dest_path)

    # maybe the user supplied a '.saved' filename
    filename = obj.dest_path + '.saved'
    if filename in SINGLE_FILES:
        SINGLE_FILES.remove(filename)
        is_saved = True
    else:
        is_saved = False

    if is_dest or is_saved:
        _, updated = _erase_saved_callback(obj, pre_dict, post_dict)

        if not SINGLE_FILES:
            return False, updated

    return go_on, updated


def single_erase_saved():
    # type: () -> None
    '''erase single backup files'''

    synctool.overlay.visit(param.OVERLAY_DIR,
                           _single_erase_saved_callback)

    if SINGLE_FILES:
        # there are still single files left
        # maybe they are in the delete tree?
        synctool.overlay.visit(param.DELETE_DIR,
                               _single_erase_saved_callback)

    for filename in SINGLE_FILES:
        stderr('%s is not in the overlay tree' % filename)


def _reference_callback(obj, _pre_dict, _post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''callback for reference_files()'''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        if obj.dest_path in SINGLE_FILES:
            # this template generates the file
            print(obj.print_src())
            SINGLE_FILES.remove(obj.dest_path)
            if not SINGLE_FILES:
                return False, False

        return True, False

    if _match_single(obj.dest_path):
        print(obj.print_src())

    if not SINGLE_FILES:
        return False, False

    return True, False


def reference_files():
    # type: () -> None
    '''show which source file in the repository synctool uses'''

    synctool.overlay.visit(param.OVERLAY_DIR, _reference_callback)

    # look in the purge/ tree, too
    visit_purge_single(_reference_callback)

    for filename in SINGLE_FILES:
        stderr('%s is not in the overlay tree' % filename)


def _exec_diff(src, dest):
    # type: (str, str) -> None
    '''execute diff_cmd to display diff between dest and src'''

    verbose('%s %s %s' % (param.DIFF_CMD, dest, prettypath(src)))

    cmd_arr = shlex.split(param.DIFF_CMD)
    cmd_arr.append(dest)
    cmd_arr.append(src)

    synctool.lib.exec_command(cmd_arr)


def _diff_callback(obj, _pre_dict, post_dict):
    # type: (SyncObject, Dict[str, str], Dict[str, str]) -> Tuple[bool, bool]
    '''callback function for doing a diff on overlay/ files'''

    if obj.ov_type == synctool.overlay.OV_TEMPLATE:
        return generate_template(obj, post_dict), False

    if _match_single(obj.dest_path):
        _exec_diff(obj.src_path, obj.dest_path)

        if not SINGLE_FILES:
            return False, False

    return True, False


def diff_files():
    # type: () -> None
    '''display a diff of the single files'''

    synctool.overlay.visit(param.OVERLAY_DIR, _diff_callback)

    # look in the purge/ tree, too
    visit_purge_single(_diff_callback)

    for filename in SINGLE_FILES:
        stderr('%s is not in the overlay tree' % filename)


def option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
                        opt_upload, opt_suffix, opt_fix):
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

    if opt_suffix and not opt_upload:
        error("option --suffix can only be used together with --upload")
        sys.exit(1)

    if opt_diff and (opt_single or opt_reference or opt_fix):
        error("option --diff can not be combined with other actions")
        sys.exit(1)

    if opt_reference and (opt_single or opt_fix):
        error("option --reference can not be combined with other actions")
        sys.exit(1)


def check_cmd_config():
    # type: () -> None
    '''check whether the commands as given in synctool.conf actually exist'''

    okay, param.DIFF_CMD = config.check_cmd_config('diff_cmd', param.DIFF_CMD)
    if not okay:
        sys.exit(-1)


def usage():
    # type: () -> None
    '''print usage information'''

    print('usage: %s [options]' % PROGNAME)
    print('options:')
    print('  -h, --help            Display this information')
    print('  -c, --conf=FILE       Use this config file')
    print('                        (default: %s)' % param.DEFAULT_CONF)

    print('''  -d, --diff=FILE       Show diff for file
  -1, --single=PATH     Update a single file
  -r, --ref=PATH        Show which source file synctool chooses
  -e, --erase-saved     Erase *.saved backup files
  -f, --fix             Perform updates (otherwise, do dry-run)
      --no-post         Do not run any .post scripts
  -N, --nodename=NODE   Force nodename
  -F, --fullpath        Show full paths instead of shortened ones
  -T, --terse           Show terse, shortened paths
      --color           Use colored output (only for terse mode)
      --no-color        Do not color output
      --unix            Output actions as unix shell commands
  -v, --verbose         Be verbose
  -q, --quiet           Suppress informational startup messages
      --version         Print current version number

Note that synctool does a dry run unless you specify --fix
''')


def get_options():
    #pylint: disable=global-statement
    #pylint: disable=too-many-branches,too-many-statements
    # type: () -> int
    '''parse command-line options'''

    global SINGLE_FILES

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:d:1:r:efNFTvq',
                                   ['help', 'conf=', 'diff=', 'single=',
                                    'ref=', 'erase-saved', 'fix', 'no-post',
                                    'fullpath', 'terse', 'color', 'no-color',
                                    'masterlog', 'node=', 'nodename=',
                                    'verbose', 'quiet', 'unix', 'version'])
    except getopt.GetoptError as reason:
        print('%s: %s' % (PROGNAME, reason))
        usage()
        sys.exit(1)

    if args:
        error('excessive arguments on command line')
        sys.exit(1)

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

    # first read the config file
    config.read_config()
#    synctool.nodeset.make_default_nodeset()
    check_cmd_config()

    errors = 0

    action = ACTION_DEFAULT
    SINGLE_FILES = []

    # these are only used for checking the validity of option combinations
    opt_diff = False
    opt_single = False
    opt_reference = False
    opt_erase_saved = False
    opt_upload = False
    opt_suffix = False
    opt_fix = False

    for opt, arg in opts:
        if opt in ('-h', '--help', '-?', '-c', '--conf', '-T', '--terse',
                   '-F', '--fullpath', '--version'):
            # already done
            continue

        if opt in ('-f', '--fix'):
            opt_fix = True
            synctool.lib.DRY_RUN = False
            continue

        if opt == '--no-post':
            synctool.lib.NO_POST = True
            continue

        if opt == '--color':
            param.COLORIZE = True
            continue

        if opt == '--no-color':
            param.COLORIZE = False
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

        if opt == '--masterlog':
            # used by the master for message logging purposes
            synctool.lib.MASTERLOG = True
            continue

        if opt in ('-N', '--node', '--nodename'):
            # used by the master to set the client's nodename
            # or to force the nodename when running in stand-alone mode
            param.NODENAME = arg
            continue

        if opt in ('-d', '--diff'):
            opt_diff = True
            action = ACTION_DIFF
            filename = synctool.lib.strip_path(arg)
            if not filename:
                error('missing filename')
                sys.exit(1)

            if filename[0] != '/':
                error('filename must be a full path, starting with a slash')
                sys.exit(1)

            if filename not in SINGLE_FILES:
                SINGLE_FILES.append(filename)
            continue

        if opt in ('-1', '--single'):
            opt_single = True
            filename = synctool.lib.strip_path(arg)
            if not filename:
                error('missing filename')
                sys.exit(1)

            if filename[0] != '/':
                error('filename must be a full path, starting with a slash')
                sys.exit(1)

            if filename not in SINGLE_FILES:
                SINGLE_FILES.append(filename)
            continue

        if opt in ('-r', '--ref', '--reference'):
            opt_reference = True
            action = ACTION_REFERENCE
            filename = synctool.lib.strip_path(arg)
            if not filename:
                error('missing filename')
                sys.exit(1)

            if filename[0] != '/':
                error('filename must be a full path, starting with a slash')
                sys.exit(1)

            if filename not in SINGLE_FILES:
                SINGLE_FILES.append(filename)
            continue

        if opt in ('-e', '--erase-saved'):
            opt_erase_saved = True
            action = ACTION_ERASE_SAVED
            continue

        error("unknown command line option '%s'" % opt)
        errors += 1

    if errors:
        usage()
        sys.exit(1)

    # diff with fix works like single
    if opt_diff and opt_fix:
        opt_diff = False
        opt_single = True
        action = ACTION_DEFAULT

    option_combinations(opt_diff, opt_single, opt_reference, opt_erase_saved,
                        opt_upload, opt_suffix, opt_fix)
    return action


@catch_signals
def main():
    #pylint: disable=too-many-statements, too-many-branches
    # type: (...) -> int
    '''run the program'''

    param.init()

    action = get_options()

    config.init_mynodename()

    if not param.NODENAME:
        error('unable to determine my nodename (hostname: %s)' %
              param.HOSTNAME)
        stderr('please check %s' % param.CONF_FILE)
        sys.exit(-1)

    if param.NODENAME not in param.NODES:
        error("unknown node '%s'" % param.NODENAME)
        stderr('please check %s' % param.CONF_FILE)
        sys.exit(-1)

    if param.NODENAME in param.IGNORE_GROUPS:
        # this is only a warning ...
        # you can still run synctool-pkg on the client by hand
        warning('node %s is disabled in %s' %
                (param.NODENAME, param.CONF_FILE))

    if synctool.lib.UNIX_CMD:
        localt = time.localtime(time.time())

        unix_out('#')
        unix_out('# script generated by synctool on '
                 '%04d/%02d/%02d %02d:%02d:%02d' %
                 (localt[0], localt[1], localt[2],
		  localt[3], localt[4], localt[5]))
        unix_out('#')
        unix_out('# my hostname: %s' % param.HOSTNAME)
        unix_out('# SYNCTOOL_NODE=%s' % param.NODENAME)
        unix_out('# SYNCTOOL_ROOT=%s' % param.ROOTDIR)
        unix_out('#')

        if not synctool.lib.DRY_RUN:
            unix_out('# NOTE: --fix specified, applying updates')
            unix_out('#')

        unix_out('')
    else:
        if not synctool.lib.MASTERLOG:
            # only print this when running stand-alone
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

        verbose('my nodename: %s' % param.NODENAME)
        verbose('my hostname: %s' % param.HOSTNAME)
        verbose('rootdir: %s' % param.ROOTDIR)

    os.environ['SYNCTOOL_NODE'] = param.NODENAME
    os.environ['SYNCTOOL_ROOT'] = param.ROOTDIR

    unix_out('umask 077')
    unix_out('')
    os.umask(0o77)

    if action == ACTION_DIFF:
        diff_files()

    elif action == ACTION_REFERENCE:
        reference_files()

    elif action == ACTION_ERASE_SAVED:
        if SINGLE_FILES:
            single_erase_saved()
        else:
            erase_saved()

    elif SINGLE_FILES:
        single_files()

    else:
        purge_files()
        overlay_files()
        delete_files()

    unix_out('# EOB')
    return 0

# EOB
