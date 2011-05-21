#! /usr/bin/env python
#
#	synctool-ssh	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_unbuffered
import synctool_param
import synctool_config
import synctool_aggr
import synctool_lib
import synctool_nodeset

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt
import shlex

NODESET = synctool_nodeset.NodeSet()

OPT_AGGREGATE = False
OPT_NODENAME = True
MASTER_OPTS = None


def ssh_nodeset(nodeset, remote_cmd_arr):
	'''run remote command to a set of nodes using ssh (param ssh_cmd)'''
	
	nodes = NODESET.interfaces()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)
	
	if not synctool_param.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	ssh_cmd_arr = shlex.split(synctool_param.SSH_CMD)
	
	synctool_lib.run_parallel(master_ssh, worker_ssh,
		(nodes, nodeset, ssh_cmd_arr, remote_cmd_arr), len(nodes))


def master_ssh(rank, args):
	(nodes, nodeset, ssh_cmd_arr, remote_cmd_arr) = args
	
	node = nodes[rank]
	cmd_str = string.join(remote_cmd_arr)
	
	if node == synctool_param.NODENAME:
		verbose('running %s' % cmd_str)
		unix_out(cmd_str)
	else:
		verbose('running %s to %s %s' % (os.path.basename(ssh_cmd_arr[0]),
			nodeset.get_nodename_from_interface(node), cmd_str))
		
		unix_out('%s %s %s' % (string.join(ssh_cmd_arr), node, cmd_str))


def worker_ssh(rank, args):
	if synctool_lib.DRY_RUN:		# got here for nothing
		return
	
	(nodes, nodeset, ssh_cmd_arr, remote_cmd_arr) = args
	
	node = nodes[rank]
	nodename = nodeset.get_nodename_from_interface(node)
	
	if nodename == synctool_param.NODENAME:
		# is this node the local node? Then do not use ssh
		ssh_cmd_arr = []
	else:
		ssh_cmd_arr.append(node)
	
	ssh_cmd_arr.extend(cmd_args)
	
	# execute remote command and show output with the nodename
	# TODO move this block to synctool_lib.run_command()
	f = synctool_lib.popen(ssh_cmd_arr)
	
	while True:
		line = f.readline()
		if not line:
			break

		line = string.strip(line)

		# pass output on; simply use 'print' rather than 'stdout()'
		if line[:15] == '%synctool-log% ':
			if line[15:] == '--':
				pass
			else:
				synctool_lib.masterlog('%s: %s' % (nodename, line[15:]))
		else:
			if OPT_NODENAME:
				print '%s: %s' % (nodename, line)
			else:
				# do not prepend the nodename of this node to the output
				# if option --no-nodename was given
				print line

	f.close()


def run_parallel_cmds(nodes, cmds, nodeset):
# TODO run_parallel_cmds is only used by synctool_master
# TODO so move it there
	'''fork and run multiple commands in sequence
	cmds[] is an array of tuples (cmd_arr[], cmd_args[], join_char)
	cmd_arr[] is an array that can be passed to e.g. os.execv(), or synctool_lib.popen()
	cmd_args[] contains the additional arguments to the command

	The resulting command will be: cmd_arr + node + join_char + cmd_args'''

	parallel = 0

	for node in nodes:
		#
		#	run commands in parallel, as many as defined
		#
		if parallel > synctool_param.NUM_PROC:
			try:
				if os.wait() != -1:
					parallel = parallel - 1

			except OSError:
				pass

		pid = os.fork()

		if not pid:
			#
			#	run the commands one after another
			#
			for (cmd_arr, cmd_args, join_char) in cmds:
				# show what we're going to do
				the_command = os.path.basename(cmd_arr[0])
				if node == synctool_param.NODENAME:
					cmd_str = string.join(cmd_args)
					verbose('running %s %s' % (the_command, cmd_str))
					unix_out('%s %s' % (string.join(cmd_arr), cmd_str))
				else:
					if join_char:
						cmd_str = '%s%s%s' % (nodeset.get_nodename_from_interface(node), join_char, string.join(cmd_args))
					else:
						cmd_str = '%s %s' % (nodeset.get_nodename_from_interface(node), string.join(cmd_args))

					verbose('running %s %s' % (the_command, cmd_str))

					if join_char:
						cmd_str = '%s%s%s' % (node, join_char, string.join(cmd_args))
					else:
						cmd_str = '%s %s' % (node, string.join(cmd_args))

					unix_out('%s %s' % (string.join(cmd_arr), cmd_str))

# the rsync must run, even for dry runs
#				if synctool_lib.DRY_RUN:
#					continue

				_run_command(cmd_arr, node, join_char, cmd_args, nodeset)

			# all done, child exits
			sys.exit(0)

		if pid == -1:
			stderr('error: failed to fork()')
		else:
			parallel = parallel + 1

	#
	#	wait for children to terminate
	#
	while True:
		try:
			if os.wait() == -1:
				break

		except OSError:
			break


def usage():
	print 'usage: %s [options] <remote command>' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print '  -a, --aggregate                Condense output'
	print
	print '  -v, --verbose                  Be verbose'
	print '  -N, --no-nodename              Do not prepend nodename to output'
	print '      --unix                     Output actions as unix shell commands'
	print '      --dry-run                  Do not run the remote command'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-ssh by Walter de Jong <walter@heiho.net> (c) 2009-2011'


def get_options():
	global NODESET, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE, OPT_NODENAME
	
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aNq', ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'aggregate', 'no-nodename', 'unix', 'dry-run', 'quiet'])
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

	MASTER_OPTS = [ sys.argv[0] ]

	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)
		if arg:
			MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue

		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			continue

		if opt in ('-n', '--node'):
			NODESET.add_node(arg)
			continue

		if opt in ('-g', '--group'):
			NODESET.add_group(arg)
			continue

		if opt in ('-x', '--exclude'):
			NODESET.exclude_node(arg)
			continue

		if opt in ('-X', '--exclude-group'):
			NODESET.exclude_group(arg)
			continue

		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue

		if opt in ('-N', '--no-nodename'):
			OPT_NODENAME = False
			continue

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue

		if opt == '--dry-run':
			synctool_lib.DRY_RUN = True
			continue

		if opt in ('-q', '--quiet'):
			# silently ignore this option
			continue

	if args == None or len(args) <= 0:
		print '%s: missing remote command' % os.path.basename(sys.argv[0])
		sys.exit(1)

	if args != None:
		MASTER_OPTS.extend(args)

	return args


if __name__ == '__main__':
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)

	cmd_args = get_options()

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.read_config()
	synctool_config.add_myhostname()

	ssh_nodeset(NODESET, cmd_args)


# EOB
