#! /usr/bin/env python -tt
#
#	synctool-ping	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_unbuffered
import synctool_nodeset
import synctool_config
import synctool_param
import synctool_aggr
import synctool_lib

from synctool_lib import verbose,stderr,unix_out

import os
import sys
import string
import getopt
import shlex
import errno

NODESET = synctool_nodeset.NodeSet()

OPT_AGGREGATE = False


def ping_nodes(nodes):
	'''ping nodes in parallel'''
	'''nodes is a list of interfaces, really'''

	synctool_lib.run_parallel(master_ping, worker_ping, nodes, len(nodes))


def master_ping(rank, nodes):
	nodename = NODESET.get_nodename_from_interface(nodes[rank])
	if nodename == synctool_param.NODENAME:
		print '%s: up' % nodename
		return

	verbose('pinging %s' % nodename)
	unix_out('%s %s' % (synctool_param.PING_CMD, nodes[rank]))


def worker_ping(rank, nodes):
	'''ping a single node'''

	node = nodes[rank]
	nodename = NODESET.get_nodename_from_interface(node)

	packets_received = 0

	# execute ping command and show output with the nodename
	cmd = '%s %s' % (synctool_param.PING_CMD, node)
	cmd_arr = shlex.split(cmd)
	f = synctool_lib.popen(cmd_arr)
	if not f:
		stderr('failed to run command %s' % cmd_arr[0])
		return

	while True:
		line = f.readline()
		if not line:
			break

		line = string.strip(line)

		# argh, we have to parse output here
		#
		# on BSD, ping says something like:
		# "2 packets transmitted, 0 packets received, 100.0% packet loss"
		#
		# on Linux, ping says something like:
		# "2 packets transmitted, 0 received, 100.0% packet loss, time 1001ms"

		arr = string.split(line)
		if len(arr) > 3 and arr[1] == 'packets' and arr[2] == 'transmitted,':
			try:
				packets_received = int(arr[3])
			except ValueError:
				pass

			break

		# some ping implementations say "hostname is alive"
		# or "hostname is unreachable"
		elif len(arr) == 3 and arr[1] == 'is':
			if arr[2] == 'alive':
				packets_received = 100

			elif arr[2] == 'unreachable':
				packets_received = -1

	f.close()

	if packets_received > 0:
		print '%s: up' % nodename
	else:
		print '%s: not responding' % nodename


def check_cmd_config():
	'''check whether the commands as given in synctool.conf actually exist'''

	(ok, synctool_param.PING_CMD) = synctool_config.check_cmd_config(
									'ping_cmd', synctool_param.PING_CMD)
	if not ok:
		sys.exit(-1)


def usage():
	print 'usage: %s [options]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print ('                                 (default: %s)' %
		synctool_param.DEFAULT_CONF)

	print '''  -n, --node=nodelist            Execute only on these nodes
  -g, --group=grouplist          Execute only on these groups of nodes
  -x, --exclude=nodelist         Exclude these nodes from the selected group
  -X, --exclude-group=grouplist  Exclude these groups from the selection
  -a, --aggregate                Condense output

  -v, --verbose                  Be verbose
      --unix                     Output actions as unix shell commands
      --version                  Print current version number

A nodelist or grouplist is a comma-separated list

synctool-ping by Walter de Jong <walter@heiho.net> (c) 2013'''


def get_options():
	global NODESET, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aNq',
			['help', 'conf=', 'verbose', 'node=', 'group=',
			'exclude=', 'exclude-group=', 'aggregate', 'unix', 'quiet'])
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

	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)

		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue

		if opt == '--version':
			print synctool_param.VERSION
			sys.exit(0)

	synctool_config.read_config()
	check_cmd_config()

	# then process the other options
	MASTER_OPTS = [ sys.argv[0] ]

	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)
		if arg:
			MASTER_OPTS.append(arg)

		if opt in ('-h', '--help', '-?', '-c', '--conf', '--version'):
			# already done
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

		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue

		if opt in ('-q', '--quiet'):
			# silently ignore this option
			continue

	if args != None:
		MASTER_OPTS.extend(args)

	return args


def main():
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)

	cmd_args = get_options()

	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.init_mynodename()

	nodes = NODESET.interfaces()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)

	ping_nodes(nodes)


if __name__ == '__main__':
	try:
		main()
	except IOError, ioerr:
		if ioerr.errno == errno.EPIPE:		# Broken pipe
			pass
		else:
			print ioerr

	except KeyboardInterrupt:		# user pressed Ctrl-C
		pass

# EOB
