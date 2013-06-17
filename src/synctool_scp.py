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

import os
import sys
import string
import getopt
import shlex
import errno

import synctool.config
import synctool.lib
from synctool.lib import verbose,stderr,unix_out
import synctool.nodeset
import synctool.param
import synctool.unbuffered

NODESET = synctool.nodeset.NodeSet()

DESTDIR = None
OPT_AGGREGATE = False
MASTER_OPTS = None
SCP_OPTIONS = None

# ugly globals help parallelism
SCP_CMD_ARR = None
FILES_STR = None


def run_remote_copy(address_list, files):
	'''copy files[] to nodes[]'''

	global SCP_CMD_ARR, FILES_STR

	SCP_CMD_ARR = shlex.split(synctool.param.SCP_CMD)

	if SCP_OPTIONS:
		SCP_CMD_ARR.extend(shlex.split(SCP_OPTIONS))

	SCP_CMD_ARR.extend(files)

	FILES_STR = string.join(files)		# only used for printing

	synctool.lib.multiprocess(worker_scp, address_list)


def worker_scp(addr):
	'''runs scp (remote copy) to node'''

	global SCP_CMD_ARR

	if synctool.lib.DRY_RUN:	# got here for nothing
		return

	nodename = NODESET.get_nodename_from_address(addr)
	if nodename == synctool.param.NODENAME:
		return

	# note that the fileset already had been added to SCP_CMD_ARR

	# create local copy
	# or parallelism may screw things up
	scp_cmd_arr = SCP_CMD_ARR[:]

	if DESTDIR:
		verbose('copying %s to %s:%s' % (FILES_STR, nodename, DESTDIR))

		if SCP_OPTIONS:
			unix_out('%s %s %s %s:%s' % (synctool.param.SCP_CMD, SCP_OPTIONS,
										FILES_STR, addr, DESTDIR))
		else:
			unix_out('%s %s %s:%s' % (synctool.param.SCP_CMD, FILES_STR,
										addr, DESTDIR))
		scp_cmd_arr.append('%s:%s' % (addr, DESTDIR))
	else:
		verbose('copying %s to %s' % (FILES_STR, nodename))

		if SCP_OPTIONS:
			unix_out('%s %s %s %s:' % (synctool.param.SCP_CMD, SCP_OPTIONS,
										FILES_STR, addr))
		else:
			unix_out('%s %s %s:' % (synctool.param.SCP_CMD, FILES_STR, addr))

		scp_cmd_arr.append('%s:' % addr)

	synctool.lib.run_with_nodename(scp_cmd_arr, nodename)


def check_cmd_config():
	'''check whether the commands as given in synctool.conf actually exist'''

	(ok, synctool.param.SCP_CMD) = synctool.config.check_cmd_config(
									'scp_cmd', synctool.param.SCP_CMD)
	if not ok:
		sys.exit(-1)


def usage():
	print ('usage: %s [options] <filename> [..]' %
		os.path.basename(sys.argv[0]))
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print ('                                 (default: %s)' %
		synctool.param.DEFAULT_CONF)
	print '''  -n, --node=nodelist            Execute only on these nodes
  -g, --group=grouplist          Execute only on these groups of nodes
  -x, --exclude=nodelist         Exclude these nodes from the selected group
  -X, --exclude-group=grouplist  Exclude these groups from the selection
  -a, --aggregate                Condense output
  -o, --options=options          Set additional scp options
  -d, --dest=dir/file            Set destination name to copy to

  -N, --no-nodename              Do not prepend nodename to output
  -p, --numproc=NUM              Set number of concurrent procs
  -z, --zzz=NUM                  Sleep NUM seconds between each run
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
		opts, args = getopt.getopt(sys.argv[1:], 'hc:vd:o:n:g:x:X:Nqp:z:',
			['help', 'conf=', 'verbose', 'dest=', 'options=',
			'node=', 'group=', 'exclude=', 'exclude-group=',
			'no-nodename', 'numproc=', 'zzz=', 'unix', 'dry-run', 'quiet'])
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
			synctool.param.CONF_FILE = arg
			continue

		if opt == '--version':
			print synctool.param.VERSION
			sys.exit(0)

	synctool.config.read_config()
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
			synctool.lib.VERBOSE = True
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
			synctool.lib.OPT_NODENAME = False
			continue

		if opt == '--unix':
			synctool.lib.UNIX_CMD = True
			continue

		if opt == '--dry-run':
			synctool.lib.DRY_RUN = True
			continue

		if opt in ('-q', '--quiet'):
			# silently ignore this option
			continue

		if opt in ('-p', '--numproc'):
			try:
				synctool.param.NUM_PROC = int(arg)
			except ValueError:
				print ("%s: option '%s' requires a numeric value" %
					(os.path.basename(sys.argv[0]), opt))
				sys.exit(1)

			if synctool.param.NUM_PROC < 1:
				print ('%s: invalid value for numproc' %
					os.path.basename(sys.argv[0]))
				sys.exit(1)

			continue

		if opt in ('-z', '--zzz'):
			try:
				synctool.param.SLEEP_TIME = int(arg)
			except ValueError:
				print ("%s: option '%s' requires a numeric value" %
					(os.path.basename(sys.argv[0]), opt))
				sys.exit(1)

			if synctool.param.SLEEP_TIME < 0:
				print ('%s: invalid value for sleep time' %
					os.path.basename(sys.argv[0]))
				sys.exit(1)

			if not synctool.param.SLEEP_TIME:
				# (temporarily) set to -1 to indicate we want
				# to run serialized
				# synctool.lib.run_parallel() will use this
				synctool.param.SLEEP_TIME = -1

			continue

	if not args:
		print '%s: missing file to copy' % os.path.basename(sys.argv[0])
		sys.exit(1)

	MASTER_OPTS.extend(args)

	return args


def main():
	synctool.param.init()

	sys.stdout = synctool.unbuffered.Unbuffered(sys.stdout)
	sys.stderr = synctool.unbuffered.Unbuffered(sys.stderr)

	files = get_options()

	if OPT_AGGREGATE:
		if not synctool.aggr.run(MASTER_OPTS):
			sys.exit(-1)

		sys.exit(0)

	synctool.config.init_mynodename()

	address_list = NODESET.addresses()
	if not address_list:
		print 'no valid nodes specified'
		sys.exit(1)

	run_remote_copy(address_list, files)


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
