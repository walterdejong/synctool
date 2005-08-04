#! /usr/bin/env python
#
#	synctool	WJ103
#

import sys
import os
import os.path
import string
import socket
import getopt
import stat
import errno
import shutil
import pwd
import grp
import time
import md5

DEFAULT_CONF='synctool.conf'

CONF_FILE=DEFAULT_CONF
DRY_RUN=1
VERBOSE=0
QUIET=0
UNIX_CMD=0
LOGFILE=None
LOGFD=None
DIFF_FILE=None

#
#	default symlink mode
#	Linux makes them 0777 no matter what umask you have ...
#	but how do you like them on a different platform?
#
#	The symlink mode can be set in the config file with keyword symlink_mode
#
SYMLINK_MODE=0755

MONTHS = ( 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec' )


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
	global UNIX_CMD, LOGFD, DRY_RUN

	if not UNIX_CMD:
		print str

	log(str)


def stderr(str):
	print str
	log(str)


def openlog(filename):
	global LOGFD

	LOGFD = None
	if filename != None and filename != '':
		try:
			LOGFD = open(filename, 'a')
		except IOError, (err, reason):
			print 'error: failed to open logfile %s : %s' % (filename, reason)
			sys.exit(-1)

		log('start run')


def closelog():
	global LOGFD

	if LOGFD != None:
		log('end run\n')

		LOGFD.close()
		LOGFD = None


def log(str):
	global DRY_RUN, LOGFD

	if not DRY_RUN and LOGFD != None:
		t = time.localtime(time.time())
		LOGFD.write('%s %02d %02d:%02d:%02d %s\n' % (MONTHS[t[1]-1], t[2], t[3], t[4], t[5], str))


def ascii_uid(uid):
	'''get the name for this uid'''

	try:
		entry = pwd.getpwuid(uid)
		return entry[0]

	except KeyError:
		pass

	return "%d" % uid


def ascii_gid(gid):
	'''get the name for this gid'''

	try:
		entry = grp.getgrgid(gid)
		return entry[0]

	except KeyError:
		pass

	return "%d" % gid


def checksum_files(file1, file2):
	'''do a quick checksum of 2 files'''

	try:
		f1 = open(file1, 'r')
	except IOError(err, reason):
		raise IOError(err, 'failed to open %s : %s' % (file1, reason))

	try:
		f2 = open(file2, 'r')
	except IOError(err, reason):
		raise IOError(err, 'failed to open %s : %s' % (file2, reason))

	sum1 = md5.new()
	sum2 = md5.new()

	len1 = len2 = 0
	ended = 0
	while len1 == len2 and sum1.digest() == sum2.digest() and not ended:
		data1 = f1.read(4096)
		if not data1:
			ended = 1
		else:
			len1 = len1 + len(data1)
			sum1.update(data1)

		data2 = f2.read(4096)
		if not data2:
			ended = 1
		else:
			len2 = len2 + len(data2)
			sum2.update(data2)

	f1.close()
	f2.close()
	return sum1.digest(), sum2.digest()


def compare_files(src_path, dest_path):
	'''see what the differences are between src and dest, and fix it'''

	global SYMLINK_MODE

	changed = 0

	try:
		src_stat = os.lstat(src_path)
	except OSError, (err, reason):
		stderr('lstat(%s) failed: %d %s' % (src_path, err, reason))
		return changed

	try:
		dest_stat = os.lstat(dest_path)
	except OSError, (err, reason):
		if err != errno.ENOENT:
			stderr('lstat(%s) failed: %d %s' % (src_path, err, reason))
			return changed

# error is ENOENT, see if the src does exist

		if os.path.islink(src_path):			# we're trying to copy a link
			stdout('symbolic link %s does not exist' % dest_path)

			path = None
			try:
				link_path = os.readlink(src_path)
			except OSError, reason:
				stderr('failed to readlink %s : %s' % (src_path, reason))
			else:
				unix_out('# create symbolic link %s' % dest_path)
				symlink_file(link_path, dest_path)
				unix_out('')
		else:
			if os.path.isdir(src_path):
				stdout('%s/ does not exist' % dest_path)
				unix_out('# make directory %s' % dest_path)

				make_dir(dest_path)
				set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
				set_permissions(dest_path, src_stat[stat.ST_MODE])

				unix_out('')
			else:
				stdout('%s does not exist' % dest_path)
				unix_out('# copy file %s' % dest_path)

				copy_file(src_path, dest_path)
				set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
				set_permissions(dest_path, src_stat[stat.ST_MODE])

				unix_out('')

		return 1

#
#	check symbolic link destination
#
	if os.path.islink(src_path):
		src_link = os.readlink(src_path)

		if os.path.islink(dest_path):
			dest_link = os.readlink(dest_path)

			if src_link != dest_link:
				stdout('%s should point to %s, but points to %s' % (dest_path, src_link, dest_link))

				unix_out('# relink symbolic link %s' % dest_path)
				delete_file(dest_path)
				symlink_file(src_link, dest_path)

				unix_out('')
				return 1

			if (dest_stat[stat.ST_MODE] & 07777) != SYMLINK_MODE:
				stdout('%s should have mode %04o (symlink), but has %04o' % (dest_path, SYMLINK_MODE, dest_stat[stat.ST_MODE] & 07777))
				unix_out('# fix permissions of symbolic link %s' % dest_path)
				symlink_file(src_link, dest_path)

				unix_out('')
				return 1

			return 0

		else:
			stdout('%s is not a symlink' % dest_path)
			unix_out('# target should be a symbolic link %s' % dest_path)
			symlink_file(src_link, dest_path)

			unix_out('')
			return 1

	else:
		if os.path.islink(dest_path):
			stdout('%s is a symlink, but should not be' % dest_path)
			unix_out('# target should not be a symbolic link %s' % dest_path)

			delete_file(dest_path)

			if os.path.isdir(src_path):
				make_dir(dest_path)
			else:
				copy_file(src_path, dest_path)

			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])

			unix_out('')
			return 1


	if not os.path.isdir(src_path):
#
#	check file size
#
		if src_stat[stat.ST_SIZE] != dest_stat[stat.ST_SIZE]:
			stdout('%s updated (file size mismatch)' % dest_path)
			unix_out('# updating file %s' % dest_path)

			copy_file(src_path, dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])

			unix_out('')
			return 1

#
#	check file contents (SHA1 or MD5 checksum)
#
		try:
			src_sum, dest_sum = checksum_files(src_path, dest_path)
		except IOError, (err, reason):
			stderr('error: %s' % reason)
			return 0

		if src_sum != dest_sum:
#			stdout('%s updated (SHA1 mismatch)' % dest_path)
			stdout('%s updated (MD5 mismatch)' % dest_path)

			unix_out('# updating file %s' % dest_path)

			copy_file(src_path, dest_path)
			set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
			set_permissions(dest_path, src_stat[stat.ST_MODE])

			unix_out('')
			return 1

#	if src_stat[stat.ST_CTIME] != dest_stat[stat.ST_CTIME]:
#		stdout('%s should have ctime %d, but has %d' % (dest_path, src_stat[stat.ST_CTIME], dest_stat[stat.ST_CTIME]))

#
#	check mode and owner/group
#
	if src_stat[stat.ST_UID] != dest_stat[stat.ST_UID] or src_stat[stat.ST_GID] != dest_stat[stat.ST_GID]:
		stdout('%s should have owner %s.%s (%d.%d), but has %s.%s (%d.%d)' % (dest_path, ascii_uid(src_stat[stat.ST_UID]), ascii_gid(src_stat[stat.ST_GID]), src_stat[stat.ST_UID], src_stat[stat.ST_GID], ascii_uid(dest_stat[stat.ST_UID]), ascii_gid(dest_stat[stat.ST_GID]), dest_stat[stat.ST_UID], dest_stat[stat.ST_GID]))
		unix_out('# changing ownership on %s' % dest_path)
		set_owner(dest_path, src_stat[stat.ST_UID], src_stat[stat.ST_GID])
		unix_out('')
		changed = 1

	if (src_stat[stat.ST_MODE] & 07777) != (dest_stat[stat.ST_MODE] & 07777) :
		stdout('%s should have mode %04o, but has %04o' % (dest_path, src_stat[stat.ST_MODE] & 07777, dest_stat[stat.ST_MODE] & 07777))
		unix_out('# changing permissions on %s' % dest_path)
		set_permissions(dest_path, src_stat[stat.ST_MODE])
		unix_out('')
		changed = 1

	return changed


def copy_file(src, dest):
	global DRY_RUN

	if os.path.isfile(dest):
		unix_out('mv %s %s.saved' % (dest, dest))

	unix_out('umask 077')
	unix_out('cp %s %s' % (src, dest))

	if not DRY_RUN:
		if os.path.isfile(dest):
			verbose('  saving %s as %s.saved' % (dest, dest))
			try:
				os.rename(dest, '%s.saved' % dest)
			except OSError, reason:
				stderr('failed to save %s as %s.saved : %s' % (dest, dest, reason))

		old_umask = os.umask(077)

		verbose('  cp %s %s' % (src, dest))
		try:
			shutil.copy2(src, dest)			# copy file and stats
		except:
			stderr('failed to copy %s to %s' % (src, dest))

		os.umask(old_umask)
	else:
		if os.path.isfile(dest):
			verbose('  saving %s as %s.saved' % (dest, dest))

		verbose('  cp %s %s             # dry run, update not performed' % (src, dest))


def symlink_file(oldpath, newpath):
	global DRY_RUN

	if os.path.exists(newpath):
		unix_out('mv %s %s.saved' % (newpath, newpath))

	unix_out('umask 022')
	unix_out('ln -s %s %s' % (oldpath, newpath))

	if not DRY_RUN:
		if os.path.exists(newpath):
			verbose('saving %s as %s.saved' % (newpath, newpath))
			try:
				os.rename(newpath, '%s.saved' % newpath)
			except OSError, reason:
				stderr('failed to save %s as %s.saved : %s' % (newpath, newpath, reason))

		old_umask = os.umask(022)		# we want symlinks to have mode 0755, but linux makes them 0777 anyway

		verbose('  os.symlink(%s, %s)' % (oldpath, newpath))
		try:
			os.symlink(oldpath, newpath)
		except OSError, reason:
			stderr('failed to create symlink %s -> %s : %s' % (newpath, oldpath, reason))

		os.umask(old_umask)

	else:
		verbose('  os.symlink(%s, %s)             # dry run, update not performed' % (oldpath, newpath))


def set_permissions(file, mode):
	global DRY_RUN

	unix_out('chmod 0%o %s' % (mode & 07777, file))

	if not DRY_RUN:
		verbose('  os.chmod(%s, %04o)' % (file, mode & 07777))
		try:
			os.chmod(file, mode & 07777)
		except OSError, reason:
			stderr('failed to chmod %04o %s : %s' % (mode & 07777, file, reason))
	else:
		verbose('  os.chmod(%s, %04o)             # dry run, update not performed' % (file, mode & 07777))


def set_owner(file, uid, gid):
	global DRY_RUN

	unix_out('chown %s.%s %s' % (ascii_uid(uid), ascii_gid(gid), file))

	if not DRY_RUN:
		verbose('  os.chown(%s, %d, %d)' % (file, uid, gid))
		try:
			os.chown(file, uid, gid)
		except OSError, reason:
			stderr('failed to chown %s.%s %s : %s' % (ascii_uid(uid), ascii_gid(gid), file, reason))
	else:
		verbose('  os.chown(%s, %d, %d)             # dry run, update not performed' % (file, uid, gid))


def delete_file(file):
	global DRY_RUN

	unix_out('mv %s %s.saved' % (file, file))

	if not DRY_RUN:
		verbose('moving %s to %s.saved' % (file, file))
		try:
			os.rename(file, '%s.saved' % file)
		except OSError, reason:
			stderr('failed to move file to %s.saved : %s' % (file, reason))

#		verbose('  os.unlink(%s)' % file)
#		try:
#			os.unlink(file)
#		except OSError, reason:
#			stderr('failed to delete %s : %s' % (file, reason))
	else:
		verbose('moving %s to %s.saved             # dry run, update not performed' % (file, file))


def hard_delete_file(file):
	global DRY_RUN

	unix_out('rm -f %s' % file)

	if not DRY_RUN:
		verbose('  os.unlink(%s)' % file)
		try:
			os.unlink(file)
		except OSError, reason:
			stderr('failed to delete %s : %s' % (file, reason))
	else:
		verbose('deleting %s             # dry run, update not performed' % file)


def make_dir(path):
	global DRY_RUN

	unix_out('umask 077')
	unix_out('mkdir %s' % path)

	if not DRY_RUN:
		old_umask = os.umask(077)

		verbose('  os.mkdir(%s)' % path)
		try:
			os.mkdir(path)
		except OSError, reason:
			stderr('failed to make directory %s : %s' % (path, reason))

		os.umask(old_umask)
	else:
		verbose('  os.mkdir(%s)             # dry run, update not performed' % path)


def treewalk_overlay(args, dir, files):
	'''scan the overlay directory and check against the live system'''

	(cfg, base_path, groups, all_groups) = args
	base_len = len(base_path)

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	dest_dir = dir[base_len:]
	if not dest_dir:
		dest_dir = '/'

	for file in files:
		full_path = os.path.join(dir, file)
#		if os.path.isdir(full_path):
#			continue

		verbose('checking $masterdir%s' % full_path[master_len:])

		dest = os.path.join(dest_dir, file)

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
			override = os.path.join(masterdir, 'overlay', "%s.%s" % (dest[1:], group))

			if os.path.exists(override):
				if full_path != override:
					verbose('override by $masterdir%s' % override[master_len:])
					full_path = override
				break

#
#	if files is updated, run the appropriate on_update command
#
		if compare_files(full_path, dest):
			on_update(cfg, dest)


def on_update(cfg, dest):
	'''run on_update command for the dest file'''

	if cfg.has_key('on_update'):

# if the dest file is not in the on_update map, maybe it's directory is ...
# note that if there are multiple files in the directory that are updated,
# the action may is triggered multiple times as well

		update = cfg['on_update']
		if not update.has_key(dest):
			dest = os.path.dirname(dest)
			if not update.has_key(dest):
				dest = dest + '/'

		if update.has_key(dest):
			cmd = update[dest]
			if cmd[0] == '/':
				stdout('running command %s' % cmd)
			else:
				stdout('running command $masterdir/scripts/%s' % cmd)

			run_command(cfg, cmd)


def run_command(cfg, cmd):
	'''run a shell command'''

	global DRY_RUN

	masterdir = cfg['masterdir']
	master_len = len(masterdir)

	cmd1 = cmd
	arr = string.split(cmd)
	if not arr:
		cmdfile = cmd
	else:
		cmdfile = arr[0]

#
#	if relative path, use script_path
#
	if cmdfile[0] != '/':
		script_path = os.path.join(masterdir, 'scripts')
		if not os.path.isdir(script_path):
			stderr('error: no such directory $masterdir/scripts')
			return

		cmdfile = os.path.join(script_path, cmdfile)

		if not os.path.isfile(cmdfile):
			stderr("error: command $masterdir%s not found" % cmdfile[master_len:])
			return

		arr[0] = cmdfile
		cmd = string.join(arr)

	unix_out('# run command %s' % cmd1)
	unix_out(cmd)
	unix_out('')

	if not DRY_RUN:
		verbose('  os.system("%s")' % cmd1)
		try:
			os.system(cmd)
		except OSError, reason:
			stderr("failed to run shell command '%s' : %s" % (cmd1, reason))
	else:
		verbose('  os.system("%s")             # dry run, action not performed' % cmd)


def make_all_groups(cfg):
	'''make a list of all possible groups'''

	all_groups = []
	host_dict = cfg['host']
	for host in host_dict.keys():
		for group in host_dict[host]:
			if not group in all_groups:
				all_groups.append(group)

	return all_groups


def overlay_files(cfg):
	'''run the overlay function'''

	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	base_path = os.path.join(masterdir, 'overlay')
	if not os.path.isdir(base_path):
		verbose('skipping %s, no such directory' % base_path)
		base_path = None

	if base_path:
		os.path.walk(base_path, treewalk_overlay, (cfg, base_path, groups, all_groups))


def treewalk_delete(args, dir, files):
	(cfg, delete_path, groups, all_groups) = args

	delete_len = len(delete_path)
	master_len = len(cfg['masterdir'])

	for f in files:
		full_path = os.path.join(dir, f)
		if os.path.isdir(full_path):
			continue

		arr = string.split(full_path, '.')
		if len(arr) > 1 and arr[-1] in all_groups:
			if not arr[-1] in groups:
				verbose('skipping $masterdir%s, it is not one of my groups' % full_path[master_len:])
				continue

			full_path = string.join(arr[:-1], '.')		# strip the 'group' or 'host' extension

		dest = full_path[delete_len:]
		if os.path.exists(dest):
			stdout('deleting $masterdir%s : %s' % (full_path[master_len:], dest))
			hard_delete_file(dest)


def delete_files(cfg):
	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	delete_path = os.path.join(masterdir, 'delete')
	if not os.path.isdir(delete_path):
		verbose('skipping $masterdir/delete, no such directory')
		return

	os.path.walk(delete_path, treewalk_delete, (cfg, delete_path, groups, all_groups))


def always_run(cfg):
	'''always run these commands'''

	if not cfg.has_key('always_run'):
		return

	for cmd in cfg['always_run']:
		if cmd[0] == '/':
			stdout('running command %s' % cmd)
		else:
			stdout('running command $masterdir/scripts/%s' % cmd)

		run_command(cfg, cmd)


def diff_files(cfg):
	'''do a diff of a file'''

	global DIFF_FILE

	if not cfg.has_key('diff_cmd'):
		stderr('error: diff_cmd is undefined in %s' % CONF_FILE)
		return

	hostname = cfg['hostname']
	masterdir = cfg['masterdir']
	groups = cfg['host'][hostname]
	all_groups = make_all_groups(cfg)

	master_len = len(masterdir)

	base_path = os.path.join(masterdir, 'overlay')
	if not os.path.isdir(base_path):
		stderr('error: overlay directory %s does not exist' % base_path)
		return

	dest = DIFF_FILE

	if dest[0] == '/':
		src = os.path.join(base_path, dest[1:])
	else:
		src = os.path.join(base_path, dest)
#
#	see if there are any overrides for this file
#
	full_path = None
	for group in groups:
		override = '%s.%s' % (src, group)

		if os.path.exists(override):
			if full_path != override:
				verbose('override by $masterdir%s' % override[master_len:])
				full_path = override
			break

	if not full_path:
		if not os.path.isfile(src):
			stderr('%s is not in the synctool tree' % dest)
			return

		full_path = src

	if not compare_files(full_path, dest):
		stdout('files are identical')

	if UNIX_CMD:
		unix_out('%s %s %s' % (cfg['diff_cmd'], dest, full_path))
	else:
		verbose('%s %s %s' % (cfg['diff_cmd'], dest, full_path))
		os.system('%s %s %s' % (cfg['diff_cmd'], dest, full_path))


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
#	keyword: symlink_mode
#
		if keyword == 'symlink_mode':
			if cfg.has_key('symlink_mode'):
				stderr("%s:%d: redefinition of symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			try:
				mode = int(arr[1], 8)
			except ValueError:
				stderr("%s:%d: invalid argument for symlink_mode" % (filename, lineno))
				errors = errors + 1
				continue

			cfg['symlink_mode'] = mode
			continue

#
#	keyword: host
#
		if keyword == 'host':
			if len(arr) < 3:
				stderr("%s:%d: 'host' requires at least 2 arguments: hostname and logical group name" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('host'):
				cfg['host'] = {}

			host = arr[1]
			groups = arr[2:]

			if cfg['host'].has_key(host):
				stderr("%s:%d: redefinition of host %s" % (filename, lineno, host))
				errors = errors + 1
				continue

			cfg['host'][host] = groups
			continue

#
#	keyword: on_update
#
		if keyword == 'on_update':
			if len(arr) < 3:
				stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('on_update'):
				cfg['on_update'] = {}

			file = arr[1]
			cmd = string.join(arr[2:])

			if cfg['on_update'].has_key(file):
				stderr("%s:%d: redefinition of on_update %s" % (filename, lineno, file))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[2][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[2])
			else:
				full_cmd = arr[2]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['on_update'][file] = cmd
			continue

#
#	keyword: always_run
#
		if keyword == 'always_run':
			if len(arr) < 2:
				stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (filename, lineno))
				errors = errors + 1
				continue

			if not cfg.has_key('always_run'):
				cfg['always_run'] = []

			cmd = string.join(arr[1:])

			if cmd in cfg['always_run']:
				stderr("%s:%d: same command defined again: %s" % (filename, lineno, cmd))
				errors = errors + 1
				continue

#
#	check if the script exists
#
			if arr[1][0] != '/':
				master = '.'
				if cfg.has_key('masterdir'):
					master = cfg['masterdir']
				else:
					stderr("%s:%d: note: masterdir not defined, using current working directory" % (filename, lineno))

				scripts = os.path.join(master, 'scripts')
				full_cmd = os.path.join(scripts, arr[1])
			else:
				full_cmd = arr[1]

			if not os.path.isfile(full_cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, full_cmd))
				errors = errors + 1
				continue

			cfg['always_run'].append(cmd)
			continue

#
#	keyword: diff_cmd
#
		if keyword == 'diff_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'diff_cmd' requires an argument: the full path to the 'diff' command" % (filename, lineno))
				errors = errors + 1
				continue

			if cfg.has_key('diff_cmd'):
				stderr("%s:%d: redefinition of diff_cmd" % (filename, lineno))
				errors = errors + 1
				continue

			cmd = arr[1]
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (filename, lineno, cmd))
				errors = errors + 1
				continue

			cfg['diff_cmd'] = string.join(arr[1:])
			continue

		stderr("%s:%d: unknown keyword '%s'" % (filename, lineno, keyword))
		errors = errors + 1

	f.close()

	if not cfg.has_key('masterdir'):
		cfg['masterdir'] = '.'

#
#	get my hostname
#
	hostname = socket.gethostname()
	arr = string.split(hostname, '.')

	if cfg['host'].has_key(hostname):
		cfg['hostname'] = hostname

		if len(arr) > 0 and arr[0] != hostname and cfg['host'].has_key(arr[0]):
			stderr("%s: conflict; host %s and %s are both defined" % (filename, hostname, arr[0]))
			errors = errors + 1
	else:
		if len(arr) > 0 and cfg['host'].has_key(arr[0]):
			cfg['hostname'] = arr[0]
			hostname = arr[0]
		else:
			stderr('%s: no entry for host %s defined' % (filename, hostname))
			errors = errors + 1

	if errors > 0:
		sys.exit(-1)

# implicitly add 'hostname' as final group
	if not hostname in cfg['host'][hostname]:
		cfg['host'][hostname].append(hostname)

	for host in cfg['host'].keys():
		if not host in cfg['host'][host]:
			cfg['host'][host].append(host)

# reverse the group list (for overlays)
		cfg['host'][host].reverse()

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
	print '  -l, --log=logfile     Log taken actions to logfile'
	print
	print 'synctool can help you administer your cluster of machines'
	print 'Note that by default, it does a dry-run, unless you specify --fix'
	print
	print 'Written by Walter de Jong <walter@sara.nl> (c) 2003'


def main():
	global CONF_FILE, DRY_RUN, VERBOSE, QUIET, UNIX_CMD, LOGFILE, SYMLINK_MODE, DIFF_FILE

	progname = os.path.basename(sys.argv[0])

	if len(sys.argv) > 1:
		try:
			opts, args = getopt.getopt(sys.argv[1:], "hc:l:d:fvqx", ['help', 'conf=', 'log=', 'diff=', 'fix', 'verbose', 'quiet', 'unix'])
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

			if opt in ('-l', '--log'):
				LOGFILE=arg
				continue

			if opt in ('-d', '--diff'):
				DIFF_FILE=arg
				continue

			stderr("unknown command line option '%s'" % opt)
			errors = errors + 1

		if errors:
			usage()
			sys.exit(1)

	cfg = read_config(CONF_FILE)

	if cfg.has_key('symlink_mode'):
		SYMLINK_MODE = cfg['symlink_mode']

	if UNIX_CMD:
		import time

		t = time.localtime(time.time())

		unix_out('#')
		unix_out('# synctool by Walter de Jong <walter@sara.nl> (c) 2003')
		unix_out('#')
		unix_out('# script generated on %04d/%02d/%02d %02d:%02d:%02d' % (t[0], t[1], t[2], t[3], t[4], t[5]))
		unix_out('#')
		unix_out('# HOSTNAME=%s' % cfg['hostname'])
		unix_out('# MASTERDIR=%s' % cfg['masterdir'])
		unix_out('# SYMLINK_MODE=0%o' % SYMLINK_MODE)
		unix_out('#')

		if DRY_RUN:
			unix_out('# NOTE: dry run, not doing any updates')
		else:
			unix_out('# NOTE: --fix specified, applying updates')
			if LOGFILE != None:
				unix_out('#')
				unix_out('# logging to: %s' % LOGFILE)

		unix_out('#')
		unix_out('')
	else:
		if not QUIET:
			stdout('my hostname: %s' % cfg['hostname'])
			stdout('masterdir: %s' % cfg['masterdir'])
			verbose('symlink_mode: 0%o' % SYMLINK_MODE)

			if LOGFILE != None and not DRY_RUN:
				stdout('logfile: %s' % LOGFILE)

			stdout('')

			if DRY_RUN:
				stdout(' DRY RUN, not doing any updates')
			else:
				stdout(' --fix specified, applying changes')
			stdout('')

	openlog(LOGFILE)

	os.putenv('MASTERDIR', cfg['masterdir'])

	if not DIFF_FILE:
		overlay_files(cfg)
		delete_files(cfg)
		always_run(cfg)
	else:
		diff_files(cfg)

	unix_out('# EOB')

	closelog()


if __name__ == '__main__':
	main()

# EOB

