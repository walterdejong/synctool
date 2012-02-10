#! /usr/bin/env python
#
#	synctool_master_pkg.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#	- call synctool_pkg on specified nodes
#

import synctool_unbuffered
import synctool_nodeset
import synctool_config
import synctool_param
import synctool_aggr
import synctool_ssh
import synctool_lib
import synctool

from synctool_lib import verbose,stderr,unix_out

import os
import sys
import string
import getopt
import shlex
import errno

NODESET = synctool_nodeset.NodeSet()

OPT_AGGREGATE = False

PASS_ARGS = None
MASTER_OPTS = None


def run_remote_pkg(nodes):
	if not nodes:
		return
	
	if not synctool_param.SSH_CMD:
		stderr('%s: error: ssh_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	if not synctool_param.PKG_CMD:
		stderr('%s: error: pkg_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]), synctool_param.CONF_FILE))
		sys.exit(-1)

	# prepare remote synctool_pkg command
	ssh_cmd_arr = shlex.split(synctool_param.SSH_CMD)
	pkg_cmd_arr = shlex.split(synctool_param.PKG_CMD)
	pkg_cmd_arr.extend(PASS_ARGS)
	
	# run in parallel
	synctool_lib.run_parallel(master_pkg, worker_pkg,
		(nodes, ssh_cmd_arr, pkg_cmd_arr), len(nodes))


def master_pkg(rank, args):
	# the master node only displays what we're running
	(nodes, ssh_cmd_arr, pkg_cmd_arr) = args
	
	node = nodes[rank]
	nodename = NODESET.get_nodename_from_interface(node)
	
	verbose('running synctool-pkg on node %s' % nodename)
	unix_out('%s %s %s' % (string.join(ssh_cmd_arr), node, string.join(pkg_cmd_arr)))


def worker_pkg(rank, args):
	'''runs ssh + synctool-pkg to the nodes in parallel'''
	
	(nodes, ssh_cmd_arr, pkg_cmd_arr) = args
	
	node = nodes[rank]
	nodename = NODESET.get_nodename_from_interface(node)
	
	# run 'ssh node pkg_cmd'
	ssh_cmd_arr.append(node)
	ssh_cmd_arr.extend(pkg_cmd_arr)
	
	synctool_lib.run_with_nodename(ssh_cmd_arr, nodename)


def run_local_pkg():
	if not synctool_param.PKG_CMD:
		stderr('%s: error: pkg_cmd has not been defined in %s' % (os.path.basename(sys.argv[0]),
			synctool_param.CONF_FILE))
		sys.exit(-1)

	cmd_arr = shlex.split(synctool_param.PKG_CMD) + PASS_ARGS
	
	synctool_lib.run_with_nodename(cmd_arr, synctool_param.NODENAME)


def rearrange_options():
	'''rearrange command-line options so that getopt() behaves more logical for us'''
	
	# what this function does is move any arguments given after --list,
	# --install, or --remove to the back so that getopt() will treat them
	# as (loose) arguments
	# This way, you/the user can pass a package list and still append
	# a new option (like -f) at the end
	
	arglist = sys.argv[1:]
	
	new_argv = []
	pkg_list = []
	
	while len(arglist) > 0:
		arg = arglist.pop(0)
		
		new_argv.append(arg)
		
		if arg[0] == '-':
			opt = arg[1:]
			
			if opt in ('l', '-list', 'i', '-install', 'R', '-remove'):
				if len(arglist) <= 0:
					break
				
				optional_arg = arglist[0]
				while optional_arg[0] != '-':		# package names may not start with '-'
					pkg_list.append(optional_arg)
					
					arglist.pop(0)
					
					if not len(arglist):
						break
					
					optional_arg = arglist[0]
	
	new_argv.extend(pkg_list)
	return new_argv


def there_can_be_only_one():
	print 'Specify only one of these options:'
	print '  -l, --list   [PACKAGE ...]     List installed packages'
	print '  -i, --install PACKAGE [..]     Install package'
	print '  -R, --remove  PACKAGE [..]     Uninstall package'
	print '  -u, --update                   Update the database of available packages'
	print '  -U, --upgrade                  Upgrade all outdated packages'
	print '  -C, --clean                    Cleanup caches of downloaded packages'
	print
	sys.exit(1)


def usage():
	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -n, --node=nodelist            Execute only on these nodes'
	print '  -g, --group=grouplist          Execute only on these groups of nodes'
	print '  -x, --exclude=nodelist         Exclude these nodes from the selected group'
	print '  -X, --exclude-group=grouplist  Exclude these groups from the selection'
	print
	print '  -l, --list   [PACKAGE ...]     List installed packages'
	print '  -i, --install PACKAGE [..]     Install package'
	print '  -R, --remove  PACKAGE [..]     Uninstall package'
	print '  -u, --update                   Update the database of available packages'
	print '  -U, --upgrade                  Upgrade all outdated packages'
	print '  -C, --clean                    Cleanup caches of downloaded packages'
	print
	print '  -f, --fix                      Perform upgrade (otherwise, do dry-run)'
	print '  -v, --verbose                  Be verbose'
	print '      --unix                     Output actions as unix shell commands'
	print '  -a, --aggregate                Condense output'
	print '  -m, --manager PACKAGE_MANAGER  (Force) select this package manager'
	print
	print 'Supported package managers are:'
	
	# print list of supported package managers
	# format it at 78 characters wide
	print ' ',
	n = 2
	for pkg in synctool_param.KNOWN_PACKAGE_MANAGERS:
		if n + len(pkg) + 1 <= 78:
			n = n + len(pkg) + 1
			print pkg,
		else:
			n = 2 + len(pkg) + 1
			print
			print ' ', pkg,
	
	print
	print
	print 'A nodelist or grouplist is a comma-separated list'
	print 'Note that --upgrade does a dry run unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@heiho.net> (c) 2011'


def get_options():
	global NODESET, MASTER_OPTS, PASS_ARGS, OPT_AGGREGATE
	
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)
	
	synctool_lib.DRY_RUN = True				# set default dry-run
	
	# getopt() assumes that all options given after the first non-option
	# argument are all arguments (this is standard UNIX behavior, not GNU)
	# but in this case, I like the GNU way better, so re-arrange the options
	# This has odd consequences when someone gives a 'stale' --install or
	# --remove option without any argument, but hey ...
	
	arglist = rearrange_options()
	
	try:
		opts, args = getopt.getopt(arglist, 'hc:n:g:x:X:iRluUCm:fvqa',
			['help', 'conf=', 'node=', 'group=', 'exclude=', 'exclude-group=',
			'list', 'install', 'remove', 'update', 'upgrade', 'clean',
			'cleanup', 'manager=',
			'fix', 'verbose', 'quiet', 'unix', 'aggregate',
			])
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
	
	PASS_ARGS = []
	MASTER_OPTS = [ sys.argv[0] ]
	
	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			PASS_ARGS.append(opt)
			PASS_ARGS.append(arg)
			continue
	
	synctool_config.read_config()
	
	# then process all the other options
	#
	# Note: some options are passed on to synctool-pkg on the node, while
	#       others are not. Therefore some 'continue', while others don't
	#
	
	action = 0
	needs_package_list = False
	
	for opt, arg in opts:
		if opt:
			MASTER_OPTS.append(opt)
		
		if arg:
			MASTER_OPTS.append(arg)
		
		if opt in ('-h', '--help', '-?', '-c', '--conf'):
			# already done
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
		
		if opt in ('-i', '--install'):
			action = action + 1
			needs_package_list = True
		
		if opt in ('-R', '--remove'):
			action = action + 1
			needs_package_list = True
		
		if opt in ('-l', '--list'):
			action = action + 1
		
		if opt in ('-u', '--update'):
			action = action + 1
		
		if opt in ('-U', '--upgrade'):
			action = action + 1
		
		if opt in ('-C', '--clean', '--cleanup'):
			action = action + 1
		
		if opt in ('-m', '--manager'):
			if not arg in synctool_param.KNOWN_PACKAGE_MANAGERS:
				stderr("error: unknown or unsupported package manager '%s'" % arg)
				sys.exit(1)
			
			synctool_param.PACKAGE_MANAGER = arg
		
		if opt in ('-f', '--fix'):
			synctool_lib.DRY_RUN = False
		
		if opt in ('-q', '--quiet'):
			synctool_lib.QUIET = True
		
		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
		
		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
		
		if opt in ('-a', '--aggregate'):
			OPT_AGGREGATE = True
			continue
		
		if opt:
			PASS_ARGS.append(opt)
		
		if arg:
			PASS_ARGS.append(arg)

	# enable logging at the master node
# TODO it should have logging
#	PASS_ARGS.append('--masterlog')

	if args != None:
		MASTER_OPTS.extend(args)
		PASS_ARGS.extend(args)
	else:
		if needs_package_list:
			stderr('error: options --install and --remove require a package name')
			sys.exit(1)
	
	if not action:
		usage()
		sys.exit(1)
	
	if action > 1:
		there_can_be_only_one()


def main():
	sys.stdout = synctool_unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool_unbuffered.Unbuffered(sys.stderr)
	
	get_options()
	
	if OPT_AGGREGATE:
		synctool_aggr.run(MASTER_OPTS)
		sys.exit(0)
	
	synctool_config.add_myhostname()
	
	# ooh ... testing for DRY_RUN doesn't work here
#	if '-f' in PASS_ARGS or '--fix' in PASS_ARGS:
#		synctool_lib.openlog()
	
	nodes = NODESET.interfaces()
	if nodes == None or len(nodes) <= 0:
		print 'no valid nodes specified'
		sys.exit(1)
	
	local_interface = synctool_config.get_node_interface(synctool_param.NODENAME)
	
	for node in nodes:
		#
		#	is this node the localhost? then run locally
		#
		if node == local_interface:
			run_local_pkg()
			nodes.remove(node)
			break
	
	run_remote_pkg(nodes)
	
#	synctool_lib.closelog()


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
