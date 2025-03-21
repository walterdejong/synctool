#
#   synctool.lib.py        WJ109
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''common functions/variables for synctool suite programs'''

import os
import sys
import datetime
import subprocess
import errno
import shlex
import syslog

from typing import List, Optional

from synctool import param

# options (mostly) set by command-line arguments
DRY_RUN = True
VERBOSE = False
QUIET = False
UNIX_CMD = False
NO_POST = False
MASTERLOG = False

# print nodename in output?
# This option is pretty useless except in synctool-ssh it may be useful
OPT_NODENAME = True

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

# enums for terse output
TERSE_INFO = 0
TERSE_WARNING = 1
TERSE_ERROR = 2
TERSE_FAIL = 3
TERSE_SYNC = 4
TERSE_LINK = 5
TERSE_MKDIR = 6
TERSE_DELETE = 7
TERSE_OWNER = 8
TERSE_MODE = 9
TERSE_EXEC = 10
TERSE_UPLOAD = 11
TERSE_NEW = 12
TERSE_TYPE = 13
TERSE_DRYRUN = 14
TERSE_FIXING = 15
TERSE_OK = 16

TERSE_TXT = ('info', 'WARN', 'ERROR', 'FAIL',
             'sync', 'link', 'mkdir', 'rm', 'chown', 'chmod', 'exec',
             'upload', 'new', 'type', 'DRYRUN', 'FIXING', 'OK')

COLORMAP = {'black': 30,
            'darkgray': 30,
            'red': 31,
            'green': 32,
            'yellow': 33,
            'blue': 34,
            'magenta': 35,
            'cyan': 36,
            'white': 37,
            'bold': 1,
            'default': 0}


def verbose(msg: str) -> None:
    '''do conditional output based on the verbose command line parameter'''

    if VERBOSE:
        print(msg)


def stdout(msg: str) -> None:
    '''print message to stdout (unless special output mode was selected)'''

    if not (UNIX_CMD or param.TERSE):
        print(msg)


def stderr(msg: str) -> None:
    '''print message to stderr
    I don't like stderr much, so it really prints to stdout
    '''

    print(msg)


def error(msg: str) -> None:
    '''print error message'''

    stderr('error: ' + msg)


def warning(msg: str) -> None:
    '''print warning message'''

    stderr('warning: ' + msg)


def terse(code: int, msg: str) -> None:
    '''print short message + shortened filename'''

    if param.TERSE:
        # convert any path to terse path
        if msg.find(' ') >= 0:
            arr = msg.split()
            if arr[-1][0] == os.sep:
                arr[-1] = terse_path(arr[-1])
                msg = ' '.join(arr)

        else:
            if msg[0] == os.sep:
                msg = terse_path(msg)

        if param.COLORIZE:        # and sys.stdout.isatty():
            txt = TERSE_TXT[code]
            color = COLORMAP[param.TERSE_COLORS[TERSE_TXT[code].lower()]]

            if param.COLORIZE_BRIGHT:
                bright = ';1'
            else:
                bright = ''

            if param.COLORIZE_FULL_LINE:
                print('\x1b[{}{}m{} {}\x1b[0m'.format(color, bright, txt, msg))
            else:
                print('\x1b[{}{}m{}\x1b[0m {}'.format(color, bright, txt, msg))
        else:
            print(TERSE_TXT[code], msg)


def unix_out(msg: str) -> None:
    '''output as unix shell command'''

    if UNIX_CMD:
        print(msg)


def prettypath(path: str) -> str:
    '''Return long path as "$overlay/path"'''

    if param.FULL_PATH:
        return path

    if param.TERSE:
        return terse_path(path)

    if path[:param.OVERLAY_LEN] == (param.OVERLAY_DIR + os.sep):
        return os.path.join('$overlay', path[param.OVERLAY_LEN:])

    if path[:param.DELETE_LEN] == (param.DELETE_DIR + os.sep):
        return os.path.join('$delete', path[param.DELETE_LEN:])

    if path[:param.PURGE_LEN] == (param.PURGE_DIR + os.sep):
        return os.path.join('$purge', path[param.PURGE_LEN:])

    return path


def terse_path(path: str, maxlen: int = 55) -> str:
    '''Return long path as "//overlay/.../dir/file"'''

    if param.FULL_PATH:
        return path

    # by the way, this function will misbehave a bit for a _destination_
    # path named "/opt/synctool/var/" again
    # because this function doesn't know whether it is working with
    # a source or a destination path and it treats them both in the same way

    if path[:param.VAR_LEN] == (param.VAR_DIR + os.sep):
        path = os.sep + os.sep + path[param.VAR_LEN:]

    if len(path) > maxlen:
        arr = path.split(os.sep)

        while len(arr) >= 3:
            idx = len(arr) // 2
            arr[idx] = '...'
            new_path = os.sep.join(arr)

            if len(new_path) > maxlen:
                arr.pop(idx)
            else:
                return new_path

    return path


def terse_match(a_terse_path: str, path: str) -> bool:
    '''Return True if it matches, else False'''

    if a_terse_path[:2] != os.sep + os.sep:
        # it's not a terse path
        return False

    idx = a_terse_path.find(os.sep + '...' + os.sep)
    if idx == -1:
        # apparently it's a very short terse path
        return a_terse_path[1:] == path

    # match last part of the path
    if a_terse_path[idx + 4:] != path[-len(a_terse_path[idx + 4:]):]:
        return False

    # match first part of the path
    # Note: this is OK for destination paths, but bugged for source paths;
    # in source paths, '//' should expand to $SYNCTOOL/var/
    # (But terse_match() is used with dest paths only anyway)
    return a_terse_path[1:idx + 1] == path[:len(a_terse_path[1:idx + 1])]


def terse_match_many(path: str, terse_path_list: List[str]) -> int:
    '''Return index of first path match in list of terse paths'''

    idx = 0
    for a_terse_path in terse_path_list:
        if terse_match(a_terse_path, path):
            return idx

        idx += 1

    return -1


def dryrun_msg(msg: str) -> str:
    '''print a "dry run" message filled to (almost) 80 chars'''

    if not DRY_RUN:
        return msg

    lmessage = len(msg) + 4

    add = '# dry run'
    laddition = len(add)

    i = 0
    while i < 4:
        # format output; align columns by steps of 20
        col = 79 + i * 20
        if lmessage + laddition <= col:
            return msg + (' ' * (col - (lmessage + laddition))) + add

        i += 1

    # else return a longer message
    return msg + '    ' + add


def openlog() -> None:
    '''start logging'''

    if DRY_RUN or not param.SYSLOGGING:
        return

    syslog.openlog('synctool', 0, syslog.LOG_USER)


def closelog() -> None:
    '''stop logging'''

    if DRY_RUN or not param.SYSLOGGING:
        return

    log('--')
    syslog.closelog()


def log(msg: str) -> None:
    '''log message to syslog'''

    if DRY_RUN or not param.SYSLOGGING:
        return

    if MASTERLOG:
        # print it with magic prefix,
        # synctool-master will pick it up
        print('%synctool-log%', msg)
    else:
        _masterlog(msg)


def _masterlog(msg: str) -> None:
    '''log only locally (on the master node)'''

    if DRY_RUN or not param.SYSLOGGING:
        return

    syslog.syslog(syslog.LOG_INFO | syslog.LOG_USER, msg)


def _pass_output(line: str, nodename: str) -> None:
    '''print output with nodename'''

    # line may be empty; that's okay

    # if output is a log line, pass it to the master's syslog
    if line[:15] == '%synctool-log% ':
        if line[15:] == '--':
            pass
        else:
            _masterlog('%s: %s' % (nodename, line[15:]))
    else:
        # pass output on; simply use 'print' rather than 'stdout()'
        if OPT_NODENAME:
            print('{}: {}'.format(nodename, line))
        else:
            # do not prepend the nodename of this node to the output
            # if option --no-nodename was given
            print(line)


def run_with_nodename(cmd_arr: List[str], nodename: str) -> int:
    '''run command and show output with nodename
    It will run regardless of what DRY_RUN is
    Returns process return code or -1 on error
    '''

    unix_out(' '.join(cmd_arr))

    sys.stdout.flush()
    sys.stderr.flush()

    try:
        with subprocess.Popen(cmd_arr,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True) as proc:
            assert proc.stdout is not None                          # this helps mypy
            for line in proc.stdout:
                line = line.rstrip()
                _pass_output(line, nodename)

            proc.wait()
            if proc.returncode != 0:
                verbose('exit code %d' % proc.returncode)

            return proc.returncode

    except OSError as err:
        stderr('failed to run command %s: %s' % (cmd_arr[0], err.strerror))

    return -1


def shell_command(cmd: str) -> int:
    '''run a shell command
    Unless DRY_RUN is set
    Returns: return code of shell command
    '''

    if DRY_RUN:
        not_str = 'not '
    else:
        not_str = ''

    # a command can have arguments
    cmd_arr = shlex.split(cmd)
    cmdfile = cmd_arr[0]

    if not QUIET:
        stdout('%srunning command %s' % (not_str, prettypath(cmd)))

    verbose(dryrun_msg('  os.system(%s)' % prettypath(cmd)))
    unix_out('# run command %s' % cmdfile)
    unix_out(cmd)
    terse(TERSE_EXEC, cmdfile)

    ret = 0
    if not DRY_RUN:
        sys.stdout.flush()
        sys.stderr.flush()

        try:
            completed = subprocess.run(cmd_arr, shell=False, check=False)
            ret = completed.returncode
        except OSError as err:
            stderr("failed to run shell command '%s' : %s" % (prettypath(cmdfile),
                                                              err.strerror))
            ret = -1
        else:
            verbose('exit code %d' % ret)

        sys.stdout.flush()
        sys.stderr.flush()

    return ret


def exec_command(cmd_arr: List[str], silent: bool = False) -> int:
    '''run a command given in cmd_arr, regardless of DRY_RUN
    Returns: return code of execute command or -1 on error
    '''

    unix_out(' '.join(cmd_arr))

    try:
        sys.stdout.flush()
        sys.stderr.flush()

        if silent and not VERBOSE:
            with open(os.devnull, 'w', encoding='utf-8') as fd_devnull:
                ret = subprocess.call(cmd_arr, shell=False,
                                      stdout=fd_devnull, stderr=fd_devnull)
        else:
            ret = subprocess.call(cmd_arr, shell=False)

        sys.stdout.flush()
        sys.stderr.flush()

        verbose('exit code %d' % ret)

    except OSError as err:
        error('failed to exec %s: %s' % (cmd_arr[0], err.strerror))
        ret = -1

    return ret


def run_command(cmd: str) -> None:
    '''run a shell command'''

    # a command can have arguments
    arr = shlex.split(cmd)
    cmdfile = arr[0]
    if not os.path.isfile(cmdfile):
        error('command %s not found' % prettypath(cmdfile))
        return

    if not os.access(cmdfile, os.X_OK):
        error("file '%s' is not executable" % prettypath(cmdfile))
        return

    # run the shell command
    shell_command(cmd)


def run_command_in_dir(dest_dir: str, cmd: str) -> None:
    '''change directory to dest_dir, and run the shell command'''

    verbose('  os.chdir(%s)' % dest_dir)
    unix_out('cd %s' % dest_dir)

    cwd = os.getcwd()

    # if dry run, the target directory may not exist yet
    # (mkdir has not been called for real, for a dry run)
    if DRY_RUN:
        run_command(cmd)

        verbose('  os.chdir(%s)' % cwd)
        unix_out('cd %s' % cwd)
        unix_out('')
        return

    try:
        os.chdir(dest_dir)
    except OSError as err:
        error('failed to change directory to %s: %s' % (dest_dir,
                                                        err.strerror))
    else:
        run_command(cmd)

        verbose('  os.chdir(%s)' % cwd)
        unix_out('cd %s' % cwd)
        unix_out('')

        try:
            os.chdir(cwd)
        except OSError as err:
            error('failed to change directory to %s: %s' % (cwd,
                                                            err.strerror))


def search_path(cmd: str) -> Optional[str]:
    '''search the PATH for the location of cmd'''

    # maybe a full path was given
    path, _ = os.path.split(cmd)
    if path and os.path.isfile(cmd) and os.access(cmd, os.X_OK):
        return cmd

    # search the PATH environment variable
    if 'PATH' not in os.environ:
        return None

    env_path = os.environ['PATH']
    if not env_path:
        return None

    for path in env_path.split(os.pathsep):
        fullpath = os.path.join(path, cmd)
        # check that the command is an executable file
        if os.path.isfile(fullpath) and os.access(fullpath, os.X_OK):
            return fullpath

    return None


def mkdir_p(path: str, mode: int = 0o700) -> bool:
    '''like mkdir -p; make directory and subdirectories
    Returns False on error, else True
    '''

    if path_exists(path):
        return True

    # temporarily restore admin's umask
    mask = os.umask(param.ORIG_UMASK)

    try:
        os.makedirs(path, mode)
    except OSError as err:
        error('failed to create directory %s: %s' % (path, err.strerror))
        os.umask(mask)
        return False
    unix_out('mkdir -p -m %04o %s' % (mode, path))

    os.umask(mask)
    return True


#
#   functions for straightening out paths that were given by the user
#

def strip_multiple_slashes(path: str) -> str:
    '''remove double slashes from path'''

    # like os.path.normpath(), but do not change symlinked paths

    if not path:
        return path

    double = os.sep + os.sep
    while path.find(double) != -1:
        path = path.replace(double, os.sep)

    if os.path.altsep:
        double = os.path.altsep + os.path.altsep
        while path.find(double) != -1:
            path = path.replace(double, os.sep)

    if path.find(os.sep + '...' + os.sep) >= 0:
        # a terse path is marked with '//' at the beginning
        path = os.sep + path

    return path


def strip_trailing_slash(path: str) -> str:
    '''remove trailing slash from path'''

    if not path:
        return path

    while len(path) > 1 and path[-1] == os.sep:
        path = path[:-1]

    return path


def strip_path(path: str) -> str:
    '''remove trailing and multiple slashes from path'''

    if not path:
        return path

    path = strip_multiple_slashes(path)
    path = strip_trailing_slash(path)

    return path


def strip_terse_path(path: str) -> str:
    '''strip a terse path'''

    if not path:
        return path

    if not param.TERSE:
        return strip_path(path)

    # terse paths may start with two slashes
    is_terse = len(path) >= 2 and path[:1] == '//'

    path = strip_multiple_slashes(path)
    path = strip_trailing_slash(path)

    # the first slash was accidentally stripped, so restore it
    if is_terse:
        path = os.sep + path

    return path


def prepare_path(path: str) -> str:
    '''strip path, and replace $SYNCTOOL by the installdir'''

    if not path:
        return path

    path = strip_multiple_slashes(path)
    path = strip_trailing_slash(path)
    path = path.replace('$SYNCTOOL/', param.ROOTDIR + os.sep)
    return path


def path_exists(filename: str) -> bool:
    '''Returns True if filename exists'''

    # Note that os.path.exists() returns False for dead symlinks

    if not filename:
        raise ValueError()

    try:
        os.lstat(filename)
    except OSError as err:
        if err.errno == errno.ENOENT:
            # No such file or directory
            return False
        if err.errno == errno.ENOTDIR:
            # path component is not a directory
            return False
        if err.errno == errno.EACCES:
            # Permission denied: it exists, but we don't have access
            return True

        error('stat(%s) failed: %s' % (filename, err.strerror))
        return False

    return True


def set_filetimes(filename: str, atime: float, mtime: float) -> None:
    '''set file atime and mtime'''

    # This func is used for forcing the mtime onto generated templates
    # The sync_times functionality is implemented in module object.py

    # only mtime is shown
    verbose('  os.utime(%s, %s)' % (filename, print_timestamp(mtime)))
    # print timestamp in other format
    datet = datetime.datetime.fromtimestamp(mtime)
    time_str = datet.strftime('%Y%m%d%H%M.%S')
    unix_out('touch -t %s %s' % (time_str, filename))

    # regardless of dry run
    try:
        os.utime(filename, (atime, mtime))
    except OSError as err:
        error('failed to set utime on %s : %s' % (filename, err.strerror))
        terse(TERSE_FAIL, 'utime %s' % filename)


def print_timestamp(stamp: float) -> str:
    '''Returns timestamp as string'''

    datet = datetime.datetime.fromtimestamp(stamp)
    return datet.strftime('%Y-%m-%d %H:%M:%S')


# EOB
