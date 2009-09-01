#! /usr/bin/env python
#
#	synctool-scp	WJ109
#
#	- simply use synctool-ssh because lots of code would be the same
#

import synctool_config
import synctool_lib
import synctool_ssh

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt


# these are set by command-line options
NODELIST = None
GROUPLIST = None
EXCLUDELIST = None
EXCLUDEGROUPS = None


def run_remote_copy(nodes, remote_cmd):
	if not synctool_config.SCP_CMD:
		stderr('%s: error: scp_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	synctool_ssh.run_parallel(nodes, synctool_config.SCP_CMD, remote_cmd)


def usage():
	print 'usage: %s [options] <filename> [..] [<destination directory>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -v, --verbose                  Be verbose'
	print
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print
	print '      --unix                     Output actions as unix shell commands'
	print '      --dry-run                  Do not run the remote copy command'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-scp by Walter de Jong <walter@sara.nl> (c) 2009'


def get_options():
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], "hc:vn:g:x:X:", ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'unix', 'dry-run'])
	except getopt.error, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)

	except getopt.GetoptError, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)

	except:
		usage()
		sys.exit(1)

	synctool_ssh.NODELIST = ''
	synctool_ssh.GROUPLIST = ''

	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_config.CONF_FILE = arg
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = 1
			continue

		if opt in ('-n', '--node'):
			if not synctool_ssh.NODELIST:
				synctool_ssh.NODELIST = arg
			else:
				synctool_ssh.NODELIST = NODELIST + ',' + arg
			continue

		if opt in ('-g', '--group'):
			if not synctool_ssh.GROUPLIST:
				synctool_ssh.GROUPLIST = arg
			else:
				synctool_ssh.GROUPLIST = synctool_ssh.GROUPLIST + ',' + arg
			continue

		if opt in ('-x', '--exclude'):
			if not synctool_ssh.EXCLUDELIST:
				synctool_ssh.EXCLUDELIST = arg
			else:
				synctool_ssh.EXCLUDELIST = synctool_ssh.EXCLUDELIST + ',' + arg
			continue

		if opt in ('-X', '--exclude-group'):
			if not synctool_ssh.EXCLUDEGROUPS:
				synctool_ssh.EXCLUDEGROUPS = arg
			else:
				synctool_ssh.EXCLUDEGROUPS = synctool_ssh.EXCLUDEGROUPS + ',' + arg
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = 1
			continue

		if opt == '--dry-run':
			synctool_lib.DRY_RUN = 1
			continue

	if args == None or len(args) <= 0:
		print '%s: missing file to copy' % os.path.basename(sys.argv[0])
		sys.exit(1)

	return string.join(args)


if __name__ == '__main__':
	cmd = get_options()
	synctool_config.read_config()
	synctool_config.add_myhostname()

	nodes = synctool_ssh.make_nodeset()
	if nodes == None:
		sys.exit(1)

	run_remote_copy(nodes, cmd)


# EOB
