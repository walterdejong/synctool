#! /usr/bin/env python
#
#	overlay	WJ106
#

'''WdJ: overlay is no longer functionally compatible with synctool.'''
'''     The main reason for this is that synctool now works with'''
'''     underscored group extensions, and supports group extensions'''
'''     on directories.'''

'''This code is still provided as proof-of-concept.'''


import sys
import os
import os.path
import string
import getopt
import pwd
import grp
import stat
import errno

DEFAULT_CONF='overlay.conf'

CONF_FILE=DEFAULT_CONF
DRY_RUN=1
VERBOSE=0
QUIET=0
UNIX_CMD=0
RSYNC_OPTS=''


def verbose(str):
	'''do conditional output based on the verbose command line parameter'''

	global VERBOSE

	if VERBOSE:
		print str


def unix_out(str):
	'''output as unix shell command'''

	global UNIX_CMD

	if UNIX_CMD:
		print str


def stdout(str):
	global UNIX_CMD

	if not UNIX_CMD:
		print str


def stderr(str):
	print str


def ascii_uid(uid):
	'''get the name for this uid'''

	try:
		entry = pwd.getpwuid(uid)
		return entry[0]

	except KeyError:
		pass

	return '%d' % uid


def ascii_gid(gid):
	'''get the name for this gid'''

	try:
		entry = grp.getgrgid(gid)
		return entry[0]

	except KeyError:
		pass

	return '%d' % gid


def stat_isdir(stat_struct):
	'''returns if a file is a directory'''
	'''this function is needed because os.path.isdir() returns True for symlinks to directories ...'''

	if not stat_struct:
		return 0

	return stat.S_ISDIR(stat_struct[stat.ST_MODE])


def stat_exists(stat_struct):
	'''returns if a path exists'''

	if not stat_struct:
		return 0

	return 1


def stat_path(path):
	'''lstat() a path'''

	try:
		stat_struct = os.lstat(path)
	except OSError, (err, reason):
		if err != errno.ENOENT:
			stderr("lstat('%s') failed: %s" % (path, reason))
			return 0

		stat_struct = None

	return stat_struct


def path_isdir(path):
	return stat_isdir(stat_path(path))


def path_exists(path):
	return stat_exists(stat_path(path))


def make_dir(path):
	unix_out('umask 077')
	unix_out('mkdir %s' % path)

	old_umask = os.umask(077)

	verbose('  os.mkdir(%s)' % path)
	try:
		os.mkdir(path)
	except OSError, reason:
		stderr('failed to make directory %s : %s' % (path, reason))

	os.umask(old_umask)


def hard_link(src, dest):
	unix_out('ln %s %s' % (src, dest))

	verbose('  os.link(%s, %s)' % (src, dest))
	try:
		os.link(src, dest)
	except OSError, reason:
		stderr('failed to hard link %s to %s : %s' % (src, dest, reason))


def replicate_path(path, base_path, dest_path):
	stats = stat_path(os.path.join(base_path, path))
	mode = stats[stat.ST_MODE] & 07777

	dest_dir = os.path.join(dest_path, path)
	make_dir(dest_dir)

	unix_out('chmod %03o %s' % (mode, dest_dir))
	unix_out('chown %s.%s %s' % (ascii_uid(stats[stat.ST_UID]), ascii_gid(stats[stat.ST_GID]), dest_dir))

	verbose('    os.chmod(%s, %03o)' % (dest_dir, mode))
	os.chmod(dest_dir, mode)

	verbose('    os.chown(%s, %d, %d)' % (dest_dir, stats[stat.ST_UID], stats[stat.ST_GID]))
	os.chown(dest_dir, stats[stat.ST_UID], stats[stat.ST_GID])


def unlink_dir(path):
	os.path.walk(path, treewalk_unlink, None)


def treewalk_unlink(args, dir, files):
	for file in files:
		if path_isdir('%s/%s' % (dir, file)):
			os.path.walk(os.path.join(dir, file), treewalk_unlink, None)
			continue

		try:
			os.unlink(os.path.join(dir, file))
		except OSError, reason:
			stderr('failed to delete tmp link %s : %s' % (os.path.join(dir, file), reason))

	try:
		os.rmdir('%s' % dir)
	except OSError, reason:
		stderr('failed to delete tmp dir %s : %s' % (dir, reason))


def run_command(cmd):
	'''run a shell command'''

	global QUIET

	arr = string.split(cmd)
	(path, cmd1) = os.path.split(arr[0])

	unix_out('# run command %s' % cmd1)
	unix_out(cmd)
	unix_out('')

	verbose('  os.system("%s")' % cmd)
	try:
		os.system(cmd)
	except OSError, reason:
		stderr("failed to run shell command '%s' : %s" % (cmd1, reason))


def treewalk_overlay(args, dir, files):
	'''scan the overlay directory and check against the live system'''

	(cfg, base_path, dest_path, groups, all_groups) = args
	base_len = len(base_path)

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	dest_dir = dir[base_len:]
	if not dest_dir:
		dest_dir = ''
	elif dest_dir[0] == '/':
		dest_dir = dest_dir[1:]

	for file in files:
		full_path = os.path.join(dir, file)
		if path_isdir(full_path):
			replicate_path(full_path[base_len+1:], base_path, dest_path)
			continue

		verbose('checking $masterdir%s' % full_path[master_len:])

		dest = file

		arr = string.split(dest, '.')
		if len(arr) > 1 and arr[-1] in all_groups:
			if not arr[-1] in groups:
				verbose('skipping $masterdir%s, it is not one of my groups' % full_path[master_len:])
				continue

			dest = string.join(arr[:-1], '.')		# strip the 'group' or 'host' extension

#
#	is this file overridden by another group for this host?
#
		override = None

		for group in groups:
			possible_override = os.path.join(masterdir, 'overlay', dir, "%s.%s" % (dest, group))

			if path_exists(possible_override):
				override = possible_override
				break

		if override and full_path != override:
			verbose('overridden by $masterdir%s' % override[master_len:])
			continue

		hard_link(full_path, os.path.join(dest_path, dest_dir, dest))


def make_all_groups(cfg):
	'''make a list of all possible groups'''

	all_groups = []
	host_dict = cfg['host']
	for host in host_dict.keys():
		for group in host_dict[host]:
			if not group in all_groups:
				all_groups.append(group)

	return all_groups


def overlay_files(cfg, hostname, dest_path):
	'''run the overlay function'''

	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	base_path = os.path.join(masterdir, 'overlay')
	if not os.path.isdir(base_path):
		verbose('skipping %s, no such directory' % base_path)
		base_path = None
		return

	make_dir(dest_path)

	os.path.walk(base_path, treewalk_overlay, (cfg, base_path, dest_path, groups, all_groups))


def read_config(filename):
	'''read the config file and return cfg structure'''

	global DEFAULT_CONF

	if not filename:
		filename = os.path.join('.', DEFAULT_CONF)

	cfg = {}

	if os.path.isdir(filename):
		filename = os.path.join(filename, DEFAULT_CONF)

# funky ... it is possible to open() directories without problems ...
	if not os.path.isfile(filename):
		stderr("no such config file '%s'" % filename)
		sys.exit(-1)

	try:
		cwd = os.getcwd()
	except OSError, reason:
		cwd = '.'

	filename = os.path.join(cwd, filename)
	if not QUIET:
		stdout('using config file: %s' % filename)

	try:
		f = open(filename, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (filename, reason))
		sys.exit(-1)

	lineno = 0
	errors = 0

	while 1:
		line = f.readline()
		if not line:
			break

		lineno = lineno + 1

		line = string.strip(line)
		if not line:
			continue

		if line[0] == '#':
			continue

		arr = string.split(line)
		if len(arr) <= 1:
			stderr('%s:%d: syntax error ; expected key/value pair' % (filename, lineno))
			errors = errors + 1
			continue

		keyword = string.lower(arr[0])

#
#	keyword: masterdir
#
		if keyword == 'masterdir':
			if cfg.has_key('masterdir'):
				stderr("%s:%d: redefinition of masterdir" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['masterdir'] = arr[1]
			continue

#
#	keyword: rsync_cmd
#
		if keyword == 'rsync_cmd':
			if cfg.has_key('rsync_cmd'):
				stderr("%s:%d: redefinition of rsync_cmd" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['rsync_cmd'] = string.join(arr[1:])
			continue

#
#	keyword: host
#
		if keyword == 'host':
			if len(arr) < 2:
				stderr("%s:%d: 'host' requires at least 1 argument: the hostname" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('host'):
				cfg['host'] = {}

			host = arr[1]
			groups = arr[2:]
# implicitly add hostname as first group
			groups.insert(0, host)

			if cfg['host'].has_key(host):
				stderr("%s:%d: redefinition of host %s" % (filename, lineno, host))
				errors = errors + 1
				continue

			cfg['host'][host] = groups
			continue

		stderr("%s:%d: unknown keyword '%s'" % (filename, lineno, keyword))
		errors = errors + 1

	f.close()

	if not cfg.has_key('masterdir'):
		cfg['masterdir'] = '.'

	if errors > 0:
		sys.exit(-1)

	return cfg


def usage():
	global DEFAULT_CONF

	print 'usage: %s [options] [<arguments>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help            Display this information'
	print '  -c, --conf=dir/file   Use this config file (default: %s)' % DEFAULT_CONF
#	print '  -n, --dry-run         Show what would have been updated'
	print '  -f, --fix             Perform updates (otherwise, do dry-run)'
	print '  -v, --verbose         Be verbose'
	print '  -q, --quiet           Suppress informational startup messages'
	print '  -x, --unix            Output actions as unix shell commands'
	print '  -o, --rsync-opts      Pass extra options to rsync'
	print
	print 'overlay can help you administer your cluster of machines'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@sara.nl> (c) 2006'


def main():
	global CONF_FILE, DRY_RUN, VERBOSE, QUIET, UNIX_CMD, RSYNC_OPTS

	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:fvqxo:", ['help', 'conf=', 'fix', 'verbose', 'quiet', 'unix', 'rsync-opts='])
		except getopt.error, (reason):
			print '%s: %s' % (progname, reason)
			usage()
			sys.exit(1)

		except getopt.GetoptError, (reason):
			print '%s: %s' % (progname, reason)
			usage()
			sys.exit(1)

		except:
			usage()
			sys.exit(1)

		errors = 0

		for opt, arg in opts:
			if opt in ('-h', '--help', '-?'):
				usage()
				sys.exit(1)

			if opt in ('-c', '--conf'):
				CONF_FILE=arg
				continue

# dry run already is default
#
#			if opt in ('-n', '--dry-run'):
#				DRY_RUN=1
#				continue

			if opt in ('-f', '--fix'):
				DRY_RUN=0
				continue

			if opt in ('-v', '--verbose'):
				VERBOSE=1
				continue

			if opt in ('-q', '--quiet'):
				QUIET=1
				continue

			if opt in ('-x', '--unix'):
				UNIX_CMD=1
				continue


			if opt in ('-o', '--rsync-opts'):
				RSYNC_OPTS=arg
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

	cfg = read_config(CONF_FILE)

	if UNIX_CMD:
		import time

		t = time.localtime(time.time())

		unix_out('#')
		unix_out('# overlay by Walter de Jong <walter@sara.nl> (c) 2006')
		unix_out('#')
		unix_out('# script generated on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# MASTERDIR=%s' % cfg['masterdir'])
		unix_out('#')

		if DRY_RUN:
			unix_out('# NOTE: dry run, not doing any updates')
		else:
			unix_out('# NOTE: --fix specified, applying updates')

		unix_out('#')
		unix_out('')
	else:
		if not QUIET:
			stdout('masterdir: %s' % cfg['masterdir'])
			stdout('')

			if DRY_RUN:
				stdout(' DRY RUN, not doing any updates')
			else:
				stdout(' --fix specified, applying changes')
			stdout('')

	if DRY_RUN:
		RSYNC_OPTS = '%s -n' % RSYNC_OPTS

	if VERBOSE:
		RSYNC_OPTS = '%s -v' % RSYNC_OPTS

	if QUIET:
		RSYNC_OPTS = '%s -q' % RSYNC_OPTS

	masterdir = cfg['masterdir']
	dest_path = os.path.join(masterdir, '.overlay.%d' % os.getpid())

	hosts = cfg['host'].keys()
	hosts.sort()

	try:
		for host in hosts:
			unix_out('#')
			unix_out('#   host %s' % host)
			unix_out('#')

			verbose('')
			verbose('overlaying host %s' % host)
			verbose('')

			overlay_files(cfg, host, dest_path)

			if not QUIET:
				stdout('rsyncing to %s' % host)

			run_command('%s %s %s/ %s:/' % (cfg['rsync_cmd'], RSYNC_OPTS, dest_path, host))
			unlink_dir(dest_path)
	except:								# on error, cleanup temp dir
		if path_isdir(dest_path):
			unlink_dir(dest_path)

	unix_out('# EOB')


if __name__ == '__main__':
	print 'WdJ: overlay is no longer functionally compatible with synctool.'
	print '     The main reason for this is that synctool now works with'
	print '     underscored group extensions, and supports group extensions'
	print '     on directories.'
	print
	print "(maybe I'll fix this later, but I don't think so ... use synctool instead)"

	sys.exit(1)

	main()

# EOB
