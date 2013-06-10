#! /usr/bin/env python
#
#	synctool-scp	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_config
import synctool_param
import synctool_ssh
import synctool_lib

from synctool_lib import verbose,stderr,unix_out

import os
import sys
import string
import getopt
import shlex
import errno

import synctool.nodeset
import synctool.unbuffered

NODESET = synctool.nodeset.NodeSet()

DESTDIR = None
OPT_AGGREGATE = False
MASTER_OPTS = None
SCP_OPTIONS = None


def run_remote_copy(nodes, files):
	'''copy files[] to nodes[]'''

	scp_cmd_arr = shlex.split(synctool_param.SCP_CMD)

	if SCP_OPTIONS:
		scp_cmd_arr.extend(shlex.split(SCP_OPTIONS))

	for node in nodes:
		if node == synctool_param.NODENAME:
			verbose('skipping node %s' % node)
			nodes.remove(node)
			break

	scp_cmd_arr.extend(files)

	files_str = string.join(files)		# this is used only for printing

	synctool_lib.run_parallel(master_scp, worker_scp,
		(nodes, scp_cmd_arr, files_str), len(nodes))


def master_scp(rank, args):
	(nodes, scp_cmd_arr, files_str) = args

	node = nodes[rank]
	nodename = NODESET.get_nodename_from_address(node)

	# master thread only displays what we're running

	if DESTDIR:
		verbose('copying %s to %s:%s' % (files_str, nodename, DESTDIR))

		if SCP_OPTIONS:
			unix_out('%s %s %s %s:%s' % (synctool_param.SCP_CMD, SCP_OPTIONS,
										files_str, node, DESTDIR))
		else:
			unix_out('%s %s %s:%s' % (synctool_param.SCP_CMD, files_str,
										node, DESTDIR))

	else:
		verbose('copying %s to %s' % (files_str, nodename))

		if SCP_OPTIONS:
			unix_out('%s %s %s %s:' % (synctool_param.SCP_CMD, SCP_OPTIONS,
										files_str, node))
		else:
			unix_out('%s %s %s:' % (synctool_param.SCP_CMD, files_str, node))


def worker_scp(rank, args):
	'''runs scp (remote copy) to node'''

	if synctool_lib.DRY_RUN:	# got here for nothing
		return

	(nodes, scp_cmd_arr, files_str) = args

	node = nodes[rank]
	nodename = NODESET.get_nodename_from_address(node)

	# note that the fileset already had been added to scp_cmd_arr

	if DESTDIR:
		scp_cmd_arr.append('%s:%s' % (node, DESTDIR))
	else:
		scp_cmd_arr.append('%s:' % node)

	synctool_lib.run_with_nodename(scp_cmd_arr, nodename)


def check_cmd_config():
	'''check whether the commands as given in synctool.conf actually exist'''

	(ok, synctool_param.SCP_CMD) = synctool_config.check_cmd_config(
									'scp_cmd', synctool_param.SCP_CMD)
	if not ok:
		sys.exit(-1)


def usage():
	print ('usage: %s [options] <filename> [..]' %
		os.path.basename(sys.argv[0]))
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
  -o, --options=options          Set additional scp options
  -d, --dest=dir/file            Set destination name to copy to

  -N, --no-nodename              Do not prepend nodename to output
  -v, --verbose                  Be verbose
      --unix                     Output actions as unix shell commands
      --dry-run                  Do not run the remote copy command
      --version                  Print current version number

A nodelist or grouplist is a comma-separated list

synctool-scp by Walter de Jong <walter@heiho.net> (c) 2009-2013'''


def get_options():
	global NODESET, DESTDIR, MASTER_OPTS, OPT_AGGREGATE, SCP_OPTIONS

	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	DESTDIR = None
	SCP_OPTIONS = None

	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vd:o:n:g:x:X:Nq',
			['help', 'conf=', 'verbose', 'dest=', 'options=',
			'node=', 'group=', 'exclude=', 'exclude-group=',
			'no-nodename', 'unix', 'dry-run', 'quiet'])
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

		if opt in ('-o', '--options'):
			SCP_OPTIONS = arg
			continue

		if opt in ('-d', '--dest'):
			DESTDIR = arg
			continue

		if opt in ('-N', '--no-nodename'):
			synctool_lib.OPT_NODENAME = False
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

	if not args:
		print '%s: missing file to copy' % os.path.basename(sys.argv[0])
		sys.exit(1)

	MASTER_OPTS.extend(args)

	return args


def main():
	sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

	files = get_options()

	if OPT_AGGREGATE:
		synctool.aggr.run(MASTER_OPTS)
		sys.exit(0)

	synctool_config.init_mynodename()

	nodes = NODESET.addresses()
	if not nodes:
		print 'no valid nodes specified'
		sys.exit(1)

	run_remote_copy(nodes, files)


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
