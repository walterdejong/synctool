#
#   synctool.multiplex.py   WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''multiplexing ssh connections'''

import os
import re
import shlex
import subprocess

import synctool.lib
from synctool.lib import verbose, error, warning, unix_out
import synctool.param
import synctool.syncstat

SSH_VERSION = None
MATCH_SSH_VERSION = re.compile(r'^OpenSSH\_(\d+)\.(\d+)')


def _make_control_path(nodename):
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


def use_mux(nodename, remote_addr):
    '''Returns True if it's OK to use a master connection to node
    Otherwise returns False -> don't use multiplexing
    '''

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return False

    # see if the control path already exists
    statbuf = synctool.syncstat.SyncStat(control_path)
    if statbuf.exists():
        if not statbuf.is_sock():
            warning('control path %s: not a socket file' %
                    control_path)
            return False

        if statbuf.uid != os.getuid():
            warning('control path: %s: incorrect owner uid %u' %
                    (control_path, statbuf.uid))
            return False

        if statbuf.mode & 077 != 0:
            warning('control path %s: suspicious file mode %04o' %
                    (control_path, statbuf.mode & 0777))
            return False

        verbose('control path %s already exists' % control_path)
        return True

    verbose('there is no ssh control path')
    return False


def control(nodename, remote_addr, ctl_cmd):
    '''Tell the ssh mux process the ctl_cmd
    Returns True on success, False otherwise
    '''

    if not ctl_cmd in ('check', 'stop', 'exit'):
        raise RuntimeError("unsupported control command '%s'" % ctl_cmd)

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return False

    verbose('sending control command %s to %s' % (ctl_cmd, nodename))

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    cmd_arr.extend(['-N', '-n',
                    '-O', ctl_cmd,
                    '-o', 'ControlPath=' + control_path])

    # if VERBOSE: don't care about ssh -v options here

    cmd_arr.append('--')
    cmd_arr.append(remote_addr)

    exitcode = synctool.lib.exec_command(cmd_arr, silent=True)
    return exitcode == 0


def ssh_args(ssh_cmd_arr, nodename):
    '''add multiplexing arguments to ssh_cmd_arr'''

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return

    ssh_cmd_arr.extend(['-o', 'ControlPath=' + control_path])


def setup_master(node_list, persist):
    '''setup master connections to all nodes in node_list
    node_list is a list of pairs: (addr, nodename)
    Argument 'persist' is the SSH ControlPersist parameter
    Returns True on success, False on error
    '''

    detect_ssh()
    if SSH_VERSION < 39:
        error('unsupported version of ssh')
        return False

    if persist == 'none':
        persist = None

    procs = []

    ssh_cmd_arr = shlex.split(synctool.param.SSH_CMD)
    ssh_cmd_arr.extend(['-M', '-N', '-n'])
    if SSH_VERSION >= 56 and not persist is None:
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
                warning('control path %s: not a socket file' % control_path)
                errors += 1
                continue

            if statbuf.uid != os.getuid():
                warning('control path: %s: incorrect owner uid %u' %
                        (control_path, statbuf.uid))
                errors += 1
                continue

            if statbuf.mode & 077 != 0:
                warning('control path %s: suspicious file mode %04o' %
                        (control_path, statbuf.mode & 0777))
                errors += 1
                continue

            verbose('control path %s already exists' % control_path)
            continue

        # start ssh in master mode to create a new control path
        verbose('creating master control path to %s' % nodename)

        cmd_arr = ssh_cmd_arr[:]
        cmd_arr.extend(['-o', 'ControlPath=' + control_path, '--', addr])

        # start in background
        unix_out(' '.join(cmd_arr))
        try:
            proc = subprocess.Popen(cmd_arr, shell=False)
        except OSError as err:
            error('failed to execute %s: %s' % (cmd_arr[0], err.strerror))
            errors += 1
            continue

        procs.append(proc)

    # print some info to the user about what's going on
    if len(procs) > 0:
        if SSH_VERSION < 56 or persist is None:
            print '''waiting for ssh master processes to terminate
Meanwhile, you may background this process or continue working
in another terminal
'''
        else:
            print 'ssh master processes started'

        for proc in procs:
            if errors > 0:
                proc.terminate()

            proc.wait()
    else:
        if errors == 0:
            print 'ssh master processes already running'

    return errors == 0


def detect_ssh():
    '''detect ssh version
    Set global SSH_VERSION to 2-digit int number:
    eg. version "5.6p1" -> SSH_VERSION = 56

    Returns: SSH_VERSION
    This routine only works for OpenSSH; otherwise return -1
    '''

    global SSH_VERSION

    if not SSH_VERSION is None:
        return SSH_VERSION

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    # only use first item: the path to the ssh command
    cmd_arr = cmd_arr[:1]
    cmd_arr.append('-V')

    unix_out(' '.join(cmd_arr))
    try:
        # OpenSSH may print version information on stderr
        proc = subprocess.Popen(cmd_arr, shell=False, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError as err:
        error('failed to execute %s: %s' % (cmd_arr[0], err.strerror))
        SSH_VERSION = -1
        return SSH_VERSION

    # stderr was redirected to stdout
    data, _ = proc.communicate()
    if not data:
        SSH_VERSION = -1
        return SSH_VERSION

    data = data.strip()
    verbose('ssh version string: ' + data)

    # data should be a single line matching "OpenSSH_... SSL ... date\n"
    m = MATCH_SSH_VERSION.match(data)
    if not m:
        SSH_VERSION = -1
        return SSH_VERSION

    groups = m.groups()
    SSH_VERSION = int(groups[0]) * 10 + int(groups[1])
    verbose('SSH_VERSION: %d' % SSH_VERSION)
    return SSH_VERSION



if __name__ == '__main__':
    synctool.lib.VERBOSE = True
    detect_ssh()

# EOB
