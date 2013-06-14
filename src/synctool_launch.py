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
	'synctool-client' : 'synctool_client.py'
}


def stderr(msg):
	sys.stderr.write(msg + '\n')
	sys.stderr.flush()


if __name__ == '__main__':
	base = os.path.abspath(os.path.dirname(sys.argv[0]))
	if not base:
		stderr('launch: fatal: unable to determine my base dir')
		sys.exit(-1)

	# Note that the prefix is in the config file,
	# but the launcher does not use it
	# It requires the other programs to be in the same dir
	# as the launcher itself

	(prefix, bindir) = os.path.split(base)
	os.environ['PYTHONPATH'] = '%s/lib' % prefix

	prognam = os.path.basename(sys.argv[0])

	if prognam == 'synctool_launch.py':
		print 'This program is used as a launcher for synctool'
		sys.exit(0)

	if not LAUNCH.has_key(prognam):
		stderr("launch: error: unknown program '%s'" % prognam)
		sys.exit(1)

	launch = os.path.join(base, LAUNCH[prognam])

	if not os.path.isfile(launch):
		stderr('launch: error: missing program %s' % launch)
		sys.exit(-1)

	argv = sys.argv[1:]
	argv.insert(0, launch)

	os.execv(argv[0], argv)

	stderr('launch: error: failed to execute: %s' % argv[0])
	sys.exit(-1)


# EOB
