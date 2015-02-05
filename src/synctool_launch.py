#! /usr/bin/env python
#
#   synctool-launch    WJ113
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''launch sets the correct PYTHONPATH and launches synctool commands'''

import os
import sys

LAUNCH = {
    'synctool' : 'synctool_master.py',
    'dsh' : 'dsh.py',
    'dsh-cp' : 'dsh_cp.py',
    'dsh-pkg' : 'dsh_pkg.py',
    'dsh-ping' : 'dsh_ping.py',
    'synctool-config' : 'synctool_config.py',
    'synctool-client' : 'synctool_client.py',
    'synctool-client-pkg' : 'synctool_client_pkg.py',
    'synctool-template' : 'synctool_template.py'
}


def stderr(msg):
    '''print error message to stderr'''

    sys.stdout.flush()
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()


if __name__ == '__main__':
    base = os.path.abspath(os.path.dirname(sys.argv[0]))
    if not base:
        stderr('launch: fatal: unable to determine my base dir')
        sys.exit(-1)

    prognam = os.path.basename(sys.argv[0])

    if prognam == 'synctool_launch.py':
        print 'This program is used as a launcher for synctool'
        sys.exit(0)

    if not prognam in LAUNCH:
        stderr("launch: error: unknown program '%s'" % prognam)
        sys.exit(1)

    (prefix, bindir) = os.path.split(base)
    launch = os.path.join(prefix, 'sbin', LAUNCH[prognam])
    if not os.path.isfile(launch):
        stderr('launch: error: missing program %s' % launch)
        sys.exit(-1)

    libdir = os.path.join(prefix, 'lib')
    if not os.path.isdir(libdir):
        stderr('launch: error: no such directory: %s' % libdir)
        sys.exit(-1)

    os.environ['PYTHONPATH'] = os.path.join(prefix, 'lib')

    argv = sys.argv[1:]
    argv.insert(0, launch)

    os.execv(argv[0], argv)

    stderr('launch: error: failed to execute: %s' % argv[0])
    sys.exit(-1)

# EOB
