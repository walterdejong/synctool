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


def run_remote_copy(nodes, args):
	if not synctool_config.SCP_CMD:
		stderr('%s: error: scp_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)

	run_parallel(nodes, synctool_config.SCP_CMD, args)


def run_parallel(nodes, cmd, cmd_args, join_char=None):
	parallel = 0

	for node in nodes:
		if node == synctool_config.NODENAME:
			verbose('running %s' % cmd_args)
			unix_out(cmd_args)
		else:
			the_command = string.split(cmd)
			the_command = the_command[0]
			the_command = os.path.basename(the_command)

			verbose('copying %s' % cmd_args)
			unix_out('%s %s %s:' % (cmd, cmd_args, node)

		if synctool_lib.DRY_RUN:
			continue
#
#	run commands in parallel, as many as defined
#
		if parallel > synctool_config.NUM_PROC:
			try:
				if os.wait() != -1:
					parallel = parallel - 1

			except OSError:
				pass

		pid = os.fork()

		if not pid:
#
#	is this node the localhost? then run locally
#
			if node == synctool_config.NODENAME:
###				run_local_cmd(cmd_args)
				sys.exit(0)

#
#	execute remote command and show output with the nodename
#
			f = os.popen('%s %s %s: 2>&1' % (cmd, cmd_args, node), 'r')

			while 1:
				line = f.readline()
				if not line:
					break

				line = string.strip(line)

				stdout('%s: %s' % (NAMEMAP[node], line))

			f.close()
			sys.exit(0)

		if pid == -1:
			stderr('error: failed to fork()')
		else:
			parallel = parallel + 1

#
#	wait for children to terminate
#
	while 1:
		try:
			if os.wait() == -1:
				break

		except OSError:
			break


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
