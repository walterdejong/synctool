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

# map interface names back to node definition names
NAMEMAP = {}

OPT_AGGREGATE = False


def make_nodeset():
	global NAMEMAP

	nodes = []
	explicit_includes = []

	if not NODELIST and not GROUPLIST:
		nodes = synctool_config.get_all_nodes()

	if NODELIST:
		nodes = string.split(NODELIST, ',')
		explicit_includes = nodes[:]

# check if the nodes exist at all
	all_nodes = synctool_config.get_all_nodes()
	for node in nodes:
		if not node in all_nodes:
			stderr("no such node '%s'" % node)
			return None

	if GROUPLIST:
		groups = string.split(GROUPLIST, ',')

# check if the groups exist at all
		all_groups = synctool_config.make_all_groups()
		for group in groups:
			if not group in all_groups:
				stderr("no such group '%s'" % group)
				return None

		nodes_in_groups = synctool_config.get_nodes_in_groups(groups)
		nodes.extend(nodes_in_groups)

	excludes = []

	if EXCLUDELIST:
		excludes = string.split(EXCLUDELIST, ',')

	if EXCLUDEGROUPS:
		groups = string.split(EXCLUDEGROUPS, ',')
		nodes_in_groups = synctool_config.get_nodes_in_groups(groups)
		excludes.extend(nodes_in_groups)

	for node in excludes:
		if node in nodes and not node in explicit_includes:
			nodes.remove(node)

	if len(nodes) <= 0:
		return []

	nodeset = []

	for node in nodes:
		if node in synctool_config.IGNORE_GROUPS and not node in explicit_includes:
			verbose('node %s is ignored' % node)
			continue

		groups = synctool_config.get_groups(node)
		do_continue = 0
		for group in groups:
			if group in synctool_config.IGNORE_GROUPS:
				verbose('group %s is ignored' % group)
				do_continue = 1
				break

		if do_continue:
			continue

		iface = synctool_config.get_node_interface(node)
		NAMEMAP[iface] = node

		if not iface in nodeset:			# make sure we do not have duplicates
			nodeset.append(iface)

	return nodeset


def ping_nodes(nodes):
	'''ping nodes in parallel'''
	'''nodes is a list of interfaces, really'''
	
	if not synctool_config.PING_CMD:
		stderr('%s: error: ping_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_config.CONF_FILE))
		sys.exit(-1)
	
	parallel = 0
	
	for node in nodes:
		nodename = NAMEMAP[node]
		if nodename == synctool_config.NODENAME:
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
	
	nodename = NAMEMAP[node]
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
	global NODELIST, GROUPLIST, EXCLUDELIST, EXCLUDEGROUPS, REMOTE_CMD, MASTER_OPTS, OPT_AGGREGATE

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vn:g:x:X:aNq', ['help', 'conf=', 'verbose',
			'node=', 'group=', 'exclude=', 'exclude-group=', 'aggregate', 'unix', 'dry-run', 'quiet'])
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
	
	NODELIST = ''
	GROUPLIST = ''
	
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
			if not NODELIST:
				NODELIST = arg
			else:
				NODELIST = NODELIST + ',' + arg
			continue
		
		if opt in ('-g', '--group'):
			if not GROUPLIST:
				GROUPLIST = arg
			else:
				GROUPLIST = GROUPLIST + ',' + arg
			continue
		
		if opt in ('-x', '--exclude'):
			if not EXCLUDELIST:
				EXCLUDELIST = arg
			else:
				EXCLUDELIST = EXCLUDELIST + ',' + arg
			continue
		
		if opt in ('-X', '--exclude-group'):
			if not EXCLUDEGROUPS:
				EXCLUDEGROUPS = arg
			else:
				EXCLUDEGROUPS = EXCLUDEGROUPS + ',' + arg
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
	
	nodes = make_nodeset()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)
	
	ping_nodes(nodes)

# EOB
