#
#   synctool.multiplex.py   WJ114
#
#   synctool Copyright 2026 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''multiplexing ssh connections'''

from __future__ import annotations

import os
import re
import shlex
import subprocess

import synctool.lib
import synctool.param
import synctool.syncstat
from synctool.lib import error, unix_out, verbose, warning

SSH_VERSION: int | None = None


def _make_control_path(nodename: str) -> str | None:
    '''Returns a control pathname for nodename
    or None on error
    It does not create the control path; just the fullpath filename
    '''

    # make subdir /tmp/synctool/sshmux/ if it doesn't already exist

    control_dir = os.path.join(synctool.param.TEMP_DIR, 'sshmux')
    if not synctool.lib.mkdir_p(control_dir):
        # error message already printed
        return None

    return os.path.join(control_dir, nodename)


def use_mux(nodename: str) -> bool:
    '''Returns True if it's OK to use a master connection to node
    Otherwise returns False -> don't use multiplexing
    '''

    control_path = _make_control_path(nodename)
    if control_path is None:
        # error message already printed
        return False

    # see if the control path already exists
    statbuf = synctool.syncstat.SyncStat(control_path)
    if statbuf.exists():
        if not statbuf.is_sock():
            warning(f'control path {control_path}: not a socket file')
            return False

        if statbuf.uid != os.getuid():
            warning(f'control path: {control_path}: incorrect owner uid {statbuf.uid}')
            return False

        if statbuf.mode & 0o77 != 0:
            warning(f'control path {control_path}: suspicious file mode {statbuf.mode & 0o777:04o}')
            return False

        verbose(f'control path {control_path} already exists')
        return True

    verbose('there is no ssh control path')
    return False


def control(nodename: str, remote_addr: str, ctl_cmd: str) -> bool:
    '''Tell the ssh mux process the ctl_cmd
    Returns True on success, False otherwise
    '''

    if ctl_cmd not in ('check', 'stop', 'exit'):
        raise RuntimeError(f"unsupported control command '{ctl_cmd}'")

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return False

    verbose(f'sending control command {ctl_cmd} to {nodename}')

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    cmd_arr.extend(['-N', '-n',
                    '-O', ctl_cmd,
                    '-o', 'ControlPath=' + control_path])

    # if VERBOSE: don't care about ssh -v options here

    cmd_arr.append('--')
    cmd_arr.append(remote_addr)

    exitcode = synctool.lib.exec_command(cmd_arr, silent=True)
    return exitcode == 0


def ssh_args(ssh_cmd_arr: list[str], nodename: str) -> None:
    '''add multiplexing arguments to ssh_cmd_arr'''

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return

    ssh_cmd_arr.extend(['-o', 'ControlPath=' + control_path])


def setup_master(node_list: list[tuple[str, str]], persist: str | None) -> bool:
    '''setup master connections to all nodes in node_list
    node_list is a list of pairs: (addr, nodename)
    Argument 'persist' is the SSH ControlPersist parameter
    Returns True on success, False on error
    '''

    # pylint: disable=too-many-statements,too-many-branches

    detect_ssh()
    assert SSH_VERSION is not None
    if SSH_VERSION < 39:
        error('unsupported version of ssh')
        return False

    if persist == 'none':
        persist = None

    procs = []

    ssh_cmd_arr = shlex.split(synctool.param.SSH_CMD)
    ssh_cmd_arr.extend(['-M', '-N', '-n'])
    if SSH_VERSION >= 56 and persist is not None:
        ssh_cmd_arr.extend(['-o', 'ControlPersist=' + persist])

    verbose('spawning ssh master connections')
    errors = 0
    for addr, nodename in node_list:
        control_path = _make_control_path(nodename)
        if not control_path:
            # error message already printed
            return False

        # see if the control path already exists
        statbuf = synctool.syncstat.SyncStat(control_path)
        if statbuf.exists():
            if not statbuf.is_sock():
                warning(f'control path {control_path}: not a socket file')
                errors += 1
                continue

            if statbuf.uid != os.getuid():
                warning(f'control path: {control_path}: incorrect owner uid {statbuf.uid}')
                errors += 1
                continue

            if statbuf.mode & 0o77 != 0:
                warning(f'control path {control_path}: suspicious file mode {statbuf.mode & 0o777:04o}')
                errors += 1
                continue

            verbose(f'control path {control_path} already exists')
            continue

        # start ssh in master mode to create a new control path
        verbose(f'creating master control path to {nodename}')

        cmd_arr = ssh_cmd_arr[:]
        cmd_arr.extend(['-o', 'ControlPath=' + control_path, '--', addr])

        # start in background
        unix_out(' '.join(cmd_arr))
        try:
            # pylint: disable=consider-using-with
            # Note, we can not use the with-statement here
            # because we make a list of process pipes
            # and the context manager would close the pipe too early

            proc = subprocess.Popen(cmd_arr)
            procs.append(proc)

        except OSError as err:
            error(f'failed to execute {cmd_arr[0]}: {err.strerror}')
            errors += 1
            continue

    # print some info to the user about what's going on
    if len(procs) > 0:
        if SSH_VERSION < 56 or persist is None:
            print('''waiting for ssh master processes to terminate
Meanwhile, you may background this process or continue working
in another terminal
''')
        else:
            print('ssh master processes started')

        for proc in procs:
            if errors > 0:
                proc.terminate()

            proc.wait()
    else:
        if errors == 0:
            print('ssh master processes already running')

    return errors == 0


MATCH_SSH_VERSION = re.compile(r'^OpenSSH\_(\d+)\.(\d+)')


def detect_ssh() -> int:
    '''detect ssh version
    Set global SSH_VERSION to 2-digit int number:
    eg. version "5.6p1" -> SSH_VERSION = 56

    Returns: SSH_VERSION
    This routine only works for OpenSSH; otherwise return -1
    '''

    # pylint: disable=global-statement

    global SSH_VERSION

    if SSH_VERSION is not None:
        return SSH_VERSION

    data = ''

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    # only use first item: the path to the ssh command
    cmd_arr = cmd_arr[:1]
    cmd_arr.append('-V')
    unix_out(' '.join(cmd_arr))
    try:
        # note, OpenSSH may print version information on stderr
        completed = subprocess.run(cmd_arr,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   text=True, check=False)
    except OSError as err:
        error(f'failed to execute {cmd_arr[0]}: {err.strerror}')
        SSH_VERSION = -1
        return SSH_VERSION

    data = completed.stdout
    if not data:
        SSH_VERSION = -1
        return SSH_VERSION

    data = data.strip()
    verbose('ssh version string: ' + data)

    # data should be a single line matching "OpenSSH_... SSL ... date\n"
    matchssl = MATCH_SSH_VERSION.match(data)
    if not matchssl:
        SSH_VERSION = -1
        return SSH_VERSION

    groups = matchssl.groups()
    SSH_VERSION = int(groups[0]) * 10 + int(groups[1])
    verbose(f'SSH_VERSION: {SSH_VERSION}')
    return SSH_VERSION


if __name__ == '__main__':
    synctool.lib.VERBOSE = True
    detect_ssh()

# EOB
