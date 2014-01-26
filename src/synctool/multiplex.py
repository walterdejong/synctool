#
#   synctool.multiplex.py   WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''multiplexing ssh connections'''

import os
import shlex

import synctool.lib
from synctool.lib import verbose, stderr, unix_out
import synctool.param
import synctool.syncstat


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


def setup(nodename, remote_addr):
    '''setup a master connection to node
    Returns True on success, False otherwise -> don't use multiplexing
    '''

    if not synctool.param.MULTIPLEX:
        return False

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return False

    # see if the control path already exists
    statbuf = synctool.syncstat.SyncStat(control_path)
    if statbuf.exists():
        if not statbuf.is_sock():
            stderr('warning: control path exists, but is not a socket file')
            return False

        verbose('control path %s already exists' % control_path)
        return True

    # start ssh in master mode to create a new control path
    verbose('creating master control path to %s' % nodename)

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    cmd_arr.extend(['-M', '-N', '-n',
                    '-o', 'ControlPath=' + control_path,
                    '-o', 'ControlPersist=yes' ])

    # make sure ssh is quiet; otherwise the ssh mux process will
    # keep printing debug info
    if '-v' in cmd_arr or '--verbose' in cmd_arr:
        cmd_arr.remove('-v')

    if not '-q' in cmd_arr and not '--quiet' in cmd_arr:
        cmd_arr.append('-q')

    cmd_arr.append('--')
    cmd_arr.append(remote_addr)

    exitcode = synctool.lib.exec_command(cmd_arr)
    if exitcode != 0:
        stderr('error: got exitcode %d from ssh -M %s' % (exitcode, nodename))
        return False

    return True


def stop(nodename, remote_addr):
    '''stop multiplexing to node
    Tell the ssh mux process to exit
    Returns True on success, False otherwise
    '''

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return False

    verbose('stopping control path to %s' % nodename)

    cmd_arr = shlex.split(synctool.param.SSH_CMD)
    cmd_arr.extend(['-N', '-n',
                    '-O', 'exit',
                    '-o', 'ControlPath=' + control_path,
                    '-o', 'ControlPersist=yes' ])

    if synctool.lib.VERBOSE:
        if not '-v' in cmd_arr and not '--verbose' in cmd_arr:
            cmd_arr.append('-v')
    else:
        if not '-q' in cmd_arr and not '--quiet' in cmd_arr:
            cmd_arr.append('-q')

    cmd_arr.append('--')
    cmd_arr.append(remote_addr)

    unix_out(' '.join(cmd_arr))

    exitcode = synctool.lib.exec_command(cmd_arr)
    if exitcode != 0:
        stderr('got exitcode %d from ssh -O exit %s' % (exitcode, nodename))
        return False

    return True


def ssh_args(ssh_cmd_arr, nodename):
    '''add multiplexing arguments to ssh_cmd_arr'''

    if not synctool.param.MULTIPLEX:
        return

    control_path = _make_control_path(nodename)
    if not control_path:
        # error message already printed
        return

    ssh_cmd_arr.extend(['-o', 'ControlPath=' + control_path])

# EOB
