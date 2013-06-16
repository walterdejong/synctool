#! /usr/bin/env python
#
#	synctool-launch	WJ113
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import sys

LAUNCH = {
	'synctool' : 'synctool_master.py',
	'synctool-ssh' : 'synctool_ssh.py',
	'synctool-scp' : 'synctool_scp.py',
	'synctool-pkg' : 'synctool_master_pkg.py',
	'synctool-ping' : 'synctool_ping.py',
	'dsh' : 'synctool_ssh.py',
	'dcp' : 'synctool_scp.py',
	'dsh-pkg' : 'synctool_master_pkg.py',
	'dsh-ping' : 'synctool_ping.py',
	'synctool-aggr' : 'synctool_aggr.py',
	'synctool-config' : 'synctool_config.py',
	'synctool-client' : 'synctool_client.py',
	'synctool-client-pkg' : 'synctool_pkg.py',
	'synctool-template' : 'synctool_template.py'
}


def stderr(msg):
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

	if not LAUNCH.has_key(prognam):
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

	os.environ['PYTHONPATH'] = '%s/lib' % prefix

	argv = sys.argv[1:]
	argv.insert(0, launch)

	os.execv(argv[0], argv)

	stderr('launch: error: failed to execute: %s' % argv[0])
	sys.exit(-1)


# EOB
