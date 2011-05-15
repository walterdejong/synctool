#! /usr/bin/env python
#
#	synctool-ping	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_unbuffered
import synctool_config
import synctool_aggr
import synctool_lib
import synctool_nodeset

from synctool_lib import verbose,stdout,stderr,unix_out

import os
import sys
import string
import getopt

NODESET = synctool_nodeset.NodeSet()

OPT_AGGREGATE = False


def ping_nodes(nodes):
	'''ping nodes in parallel'''
	'''nodes is a list of interfaces, really'''
	
	if not synctool_config.PING_CMD:
		stderr('%s: error: ping_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)
	
	parallel = 0
	
	for node in nodes:
		nodename = NODESET.get_nodename_from_interface(node)
		if nodename == synctool_param.NODENAME:
			print '%s: up' % nodename
			continue
		
		verbose('pinging %s' % nodename)
		unix_out('%s %s' % (synctool_config.PING_CMD, node))
		
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
			ping_node(node)
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


def ping_node(node):
	'''ping a single node'''
	
	nodename = NODESET.get_nodename_from_interface(node)
	packets_received = 0
	
	# execute ping command and show output with the nodename
	cmd = '%s %s' % (synctool_config.PING_CMD, node)
	cmd_arr = string.split(cmd)
	f = synctool_lib.popen(cmd_arr)
	
	while True:
		line = f.readline()
		if not line:
			break
		
		line = string.strip(line)
		
		#
		#	argh, we have to parse output here
		#	ping says something like:
		#	"2 packets transmitted, 0 packets received, 100.0% packet loss" on BSD
		#	"2 packets transmitted, 0 received, 100.0% packet loss, time 1001ms" on Linux
		#
		arr = string.split(line)
		if len(arr) > 3 and arr[1] == 'packets' and arr[2] == 'transmitted,':
			try:
				packets_received = int(arr[3])
			except ValueError:
				pass
		
			break
	
	f.close()
	
	if packets_received > 0:
		print '%s: up' % nodename
	else:
		print '%s: not responding' % nodename


def usage():
	print 'usage: %s [options]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_config.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print '  -a, --aggregate                Condense output'
	print
	print '  -v, --verbose                  Be verbose'
	print '      --unix                     Output actions as unix shell commands'
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print
	print 'synctool-ping by Walter de Jong <walter@heiho.net> (c) 2011'


def get_options():
	global NODESET, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aNq', ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'aggregate', 'unix', 'quiet'])
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
			synctool_config.CONF_FILE = arg
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


if __name__ == '__main__':
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)
	
	cmd_args = get_options()
	
	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)
	
	synctool_config.read_config()
	synctool_config.add_myhostname()
	
	nodes = NODESET.interfaces()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)
	
	ping_nodes(nodes)

# EOB
