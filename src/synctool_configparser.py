#! /usr/bin/env python
#
#	synctool_configparser.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

#
#	To make a new keyword for the config file, simply define a
#	function here like: def config_xxx(arr, configfile, lineno):
#	and it will just work (magic trick with getattr(module, functionname))
#

import synctool_param
import synctool_lib

import os
import sys
import string


def stderr(str):
	sys.stderr.write(str + '\n')


def read_config_file(configfile):
	'''read a (included) config file
	Returns 0 on success, or error count on errors'''
	
	try:
		f = open(configfile, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (configfile, reason))
		return 1
	
	this_module = sys.modules['synctool_configparser']
	
	lineno = 0
	errors = 0
	
	#
	#	read lines from the config file
	#	variable tmp_line is used to be able to do multi-line reads (backslash terminated)
	#
	line = ''
	while True:
		tmp_line = f.readline()
		if not tmp_line:
			break
		
		lineno = lineno + 1
		
		n = string.find(tmp_line, '#')
		if n >= 0:
			tmp_line = tmp_line[:n]		# strip comment
		
		tmp_line = string.strip(tmp_line)
		if not tmp_line:
			continue
		
		if tmp_line[-1] == '\\':
			tmp_line = string.strip(tmp_line[:-1])
			line = line + ' ' + tmp_line
			continue
		
		line = line + ' ' + tmp_line
		tmp_line = ''
		
		arr = string.split(line)
		
		line = ''	# <-- line is being reset here; use arr[] from here on
		
		if len(arr) <= 1:
			stderr('%s:%d: syntax error ; expected key/value pair' % (configfile, lineno))
			errors = errors + 1
			continue
		
		keyword = string.lower(arr[0])
		
		# get the parser function
		try:
			func = getattr(this_module, 'config_%s' % keyword)
		except AttributeError:
			stderr("%s:%d: unknown keyword '%s'" % (configfile, lineno, keyword))
			errors = errors + 1
			continue
		
		errors = errors + func(arr, configfile, lineno)
	
	f.close()
	return errors


#
# config functions return the number of errors in the line
# This enables the 'include' keyword to return more than 1 error
#

def _config_boolean(param, value, configfile, lineno):
	value = string.lower(value)
	if value in synctool_param.BOOLEAN_VALUE_TRUE:
		return (0, True)
	
	elif value in synctool_param.BOOLEAN_VALUE_FALSE:
		return (0, False)
	
	stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
	return (1, False)


def _config_integer(param, value, configfile, lineno, radix = 10):
	try:
		n = int(value, radix)
	except ValueError:
		stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
		return (1, 0)
	
	return (0, n)


def _config_dir(param, value, current, configfile, lineno):
	if current != None:
		stderr('%s:%d: redefinition of %s' % (configfile, lineno, param))
		return (1, current)
	
	the_dir = synctool_lib.prepare_path(value)
	
	if not os.path.isdir(the_dir):
		stderr('%s:%d: no such directory for %s' % (configfile, lineno, param))
		return (1, the_dir)
	
	return (0, the_dir)


def _config_multipath(param, value, multipaths, configfile, lineno):
	if value in multipaths:
		stderr('%s:%d: already in %s' % (configfile, lineno, param))
		return 1
	
	the_dir = synctool_lib.prepare_path(value)
	
	if not os.path.isdir(the_dir):
		stderr('%s:%d: no such directory for %s' % (configfile, lineno, param))
		return 1
	
	multipaths.append(the_dir)
	return 0


def _config_ignore_variant(param, arr, target_arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires at least 1 argument: the file or directory to ignore" % (configfile, lineno, param))
		return 1

	target_arr.extend(arr[1:])
	return 0


def _config_color_variant(param, value, configfile, lineno):
	'''set a color by name'''
	
	value = string.lower(value)
	if value in synctool_lib.COLORMAP.keys():
		synctool_param.TERSE_COLORS[param[6:]] = value
		return 0
	
	stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
	return 1


def _config_command(param, arr, short_cmd, configfile, lineno):
	'''helper for configuring rsync_cmd, ssh_cmd, synctool_cmd, etc.'''
	
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires an argument: the full path to the '%s' command" % (configfile, lineno, param, short_cmd))
		return (1, None)
	
	cmd = synctool_lib.prepare_path(arr[1])
	
	if not os.path.isfile(cmd):
		if cmd[0] != '/':
			stderr("%s:%d: '%s' requires the full path to the '%s' command" % (configfile, lineno, param, short_cmd))
		else:
			stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
		
		return (1, None)
	
	return (0, synctool_lib.prepare_path(string.join(arr[1:])))


# keyword: include
def config_include(arr, configfile, lineno):
	# recursively read the given config file
	return read_config_file(synctool_lib.prepare_path(arr[1]))


# keyword: masterdir
def config_masterdir(arr, configfile, lineno):
	if synctool_param.MASTERDIR != None:
		stderr("%s:%d: redefinition of masterdir" % (configfile, lineno))
		return 1
	
	if not os.path.isdir(arr[1]):
		stderr('%s:%d: no such directory for masterdir' % (configfile, lineno))
		return 1
	
	synctool_param.MASTERDIR = synctool_lib.strip_multiple_slashes(arr[1])
	synctool_param.MASTERDIR = synctool_lib.strip_trailing_slash(synctool_param.MASTERDIR)
	synctool_param.MASTER_LEN = len(synctool_param.MASTERDIR) + 1
	
	if synctool_param.MASTERDIR == '$masterdir':
		stderr("%s:%d: masterdir can not be set to '$masterdir', sorry" % (configfile, lineno))
		sys.exit(1)
	
	return 0


# keyword: overlaydir
def config_overlaydir(arr, configfile, lineno):
	return _config_multipath('overlaydir', arr[1], synctool_param.OVERLAY_DIRS,
		configfile, lineno)

	
# keyword: deletedir
def config_deletedir(arr, configfile, lineno):
	return _config_multipath('deletedir', arr[1], synctool_param.DELETE_DIRS,
		configfile, lineno)


# keyword: tasksdir
def config_tasksdir(arr, configfile, lineno):
	return _config_multipath('tasksdir', arr[1], synctool_param.TASKS_DIRS,
		configfile, lineno)


# keyword: scriptdir
def config_scriptdir(arr, configfile, lineno):
	(err, synctool_param.SCRIPT_DIR) = _config_dir('scriptdir',
		arr[1], synctool_param.SCRIPT_DIR, configfile, lineno)
	return err


# keyword: symlink_mode
def config_symlink_mode(arr, configfile, lineno):
	(err, synctool_param.SYMLINK_MODE) = _config_integer('symlink_mode',
		arr[1], configfile, lineno, 8)
	return err


# keyword: require_extension
def config_require_extension(arr, configfile, lineno):
	(err, synctool_param.REQUIRE_EXTENSION) = _config_boolean('require_extension',
		arr[1], configfile, lineno)
	return err

		
# keyword: full_path
def config_full_path(arr, configfile, lineno):
	(err, synctool_param.FULL_PATH) = _config_boolean('full_path',
		arr[1], configfile, lineno)
	return err


# keyword: backup_copies
def config_backup_copies(arr, configfile, lineno):
	(err, synctool_param.BACKUP_COPIES) = _config_boolean('backup_copies',
		arr[1], configfile, lineno)
	return err

		
# keyword: ignore_dotfiles
def config_ignore_dotfiles(arr, configfile, lineno):
	(err, synctool_param.IGNORE_DOTFILES) = _config_boolean('ignore_dotfiles',
		arr[1], configfile, lineno)
	return err

		
# keyword: ignore_dotdirs
def config_ignore_dotdirs(arr, configfile, lineno):
	(err, synctool_param.IGNORE_DOTDIRS) = _config_boolean('ignore_dotdirs',
		arr[1], configfile, lineno)
	return err

		
# keyword: ignore
def config_ignore(arr, configfile, lineno):
	return _config_ignore_variant('ignore', arr, synctool_param.IGNORE_FILES,
		configfile, lineno)


# keyword: ignore_file
def config_ignore_file(arr, configfile, lineno):
	return _config_ignore_variant('ignore_file', arr, synctool_param.IGNORE_FILES,
		configfile, lineno)


# keyword: ignore_files
def config_ignore_files(arr, configfile, lineno):
	return _config_ignore_variant('ignore_files', arr, synctool_param.IGNORE_FILES,
		configfile, lineno)


# keyword: ignore_dir
def config_ignore_dir(arr, configfile, lineno):
	return _config_ignore_variant('ignore_dir', arr, synctool_param.IGNORE_FILES,
		configfile, lineno)


# keyword: ignore_dirs
def config_ignore_dirs(arr, configfile, lineno):
	return _config_ignore_variant('ignore_dirs', arr, synctool_param.IGNORE_FILES,
		configfile, lineno)


# keyword: terse
def config_terse(arr, configfile, lineno):
	(err, synctool_param.TERSE) = _config_boolean('terse', arr[1], configfile, lineno)
	return err


# keyword: colorize
def config_colorize(arr, configfile, lineno):
	(err, synctool_param.COLORIZE) = _config_boolean('colorize', arr[1], configfile, lineno)
	return err

	
# keyword: colorize_full_line
def config_colorize_full_line(arr, configfile, lineno):
	(err, synctool_param.COLORIZE_FULL_LINE) = _config_boolean('colorize_full_line',
		arr[1], configfile, lineno)
	return err

		
# keyword: colorize_full_lines
# nice for typo's
def config_colorize_full_lines(arr, configfile, lineno):
	(err, synctool_param.COLORIZE_FULL_LINE) = _config_boolean('colorize_full_line',
		arr[1], configfile, lineno)
	return err

		
# keyword: colorize_bright
def config_colorize_bright(arr, configfile, lineno):
	(err, synctool_param.COLORIZE_BRIGHT) = _config_boolean('colorize_bright',
		arr[1], configfile, lineno)
	return err


# keyword: colorize_bold
def config_colorize_bold(arr, configfile, lineno):
	(err, synctool_param.COLORIZE_BRIGHT) = _config_boolean('colorize_bold',
		arr[1], configfile, lineno)
	return err


# keyword: config_color_info
def config_color_info(arr, configfile, lineno):
	return _config_color_variant('color_info', arr[1], configfile, lineno)


# keyword: config_color_warn
def config_color_warn(arr, configfile, lineno):
	return _config_color_variant('color_warn', arr[1], configfile, lineno)


# keyword: config_color_error
def config_color_error(arr, configfile, lineno):
	return _config_color_variant('color_error', arr[1], configfile, lineno)


# keyword: config_color_fail
def config_color_fail(arr, configfile, lineno):
	return _config_color_variant('color_fail', arr[1], configfile, lineno)


# keyword: config_color_sync
def config_color_sync(arr, configfile, lineno):
	return _config_color_variant('color_sync', arr[1], configfile, lineno)


# keyword: config_color_link
def config_color_link(arr, configfile, lineno):
	return _config_color_variant('color_link', arr[1], configfile, lineno)


# keyword: config_color_mkdir
def config_color_mkdir(arr, configfile, lineno):
	return _config_color_variant('color_mkdir', arr[1], configfile, lineno)


# keyword: config_color_rm
def config_color_rm(arr, configfile, lineno):
	return _config_color_variant('color_rm', arr[1], configfile, lineno)


# keyword: config_color_chown
def config_color_chown(arr, configfile, lineno):
	return _config_color_variant('color_chown', arr[1], configfile, lineno)


# keyword: config_color_chmod
def config_color_chmod(arr, configfile, lineno):
	return _config_color_variant('color_chmod', arr[1], configfile, lineno)


# keyword: config_color_exec
def config_color_exec(arr, configfile, lineno):
	return _config_color_variant('color_exec', arr[1], configfile, lineno)


# keyword: config_color_upload
def config_color_upload(arr, configfile, lineno):
	return _config_color_variant('color_upload', arr[1], configfile, lineno)


# keyword: config_color_new
def config_color_new(arr, configfile, lineno):
	return _config_color_variant('color_new', arr[1], configfile, lineno)


# keyword: config_color_type
def config_color_type(arr, configfile, lineno):
	return _config_color_variant('color_type', arr[1], configfile, lineno)


# keyword: config_color_dryrun
def config_color_dryrun(arr, configfile, lineno):
	return _config_color_variant('color_dryrun', arr[1], configfile, lineno)


# keyword: config_color_fixing
def config_color_fixing(arr, configfile, lineno):
	return _config_color_variant('color_fixing', arr[1], configfile, lineno)


# keyword: config_color_ok
def config_color_ok(arr, configfile, lineno):
	return _config_color_variant('color_ok', arr[1], configfile, lineno)


# keyword: group
def config_group(arr, configfile, lineno):
	if len(arr) < 3:
		stderr("%s:%d: 'group' requires at least 2 arguments: the compound group name and at least 1 member group" % (configfile, lineno))
		return 1
	
	group = arr[1]
	
	if synctool_param.GROUP_DEFS.has_key(group):
		stderr('%s:%d: redefiniton of group %s' % (configfile, lineno, group))
		return 1
	
	if synctool_param.NODES.has_key(group):
		stderr('%s:%d: %s was previously defined as a node' % (configfile, lineno, group))
		return 1
	
	try:
		synctool_param.GROUP_DEFS[group] = expand_grouplist(arr[2:])
	except RuntimeError, e:
		stderr('%s:%d: compound groups can not contain node names' % (configfile, lineno))
		return 1
	
	return 0


# keyword: host
def config_host(arr, configfile, lineno):
	return config_node(arr, configfile, lineno)


# keyword: node
def config_node(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires at least 1 argument: the nodename" % (configfile, lineno, arr[0]))
		return 1
	
	node = arr[1]
	groups = arr[2:]
	
	if synctool_param.NODES.has_key(node):
		stderr('%s:%d: redefinition of node %s' % (configfile, lineno, node))
		return 1
	
	if synctool_param.GROUP_DEFS.has_key(node):
		stderr('%s:%d: %s was previously defined as a group' % (configfile, lineno, node))
		return 1
	
	#
	# node lines may end with special optional qualifiers like
	# 'interface:', 'ipaddress:', 'hostname:'
	#
	# as a consequence, group names can no longer have a colon ':' in them
	#
	while len(groups) >= 1:
		n = string.find(groups[-1], ':')
		if n < 0:
			break
		
		if n == 0:
			stderr("%s:%d: syntax error in node qualifier '%s'" % (configfile, lineno, groups[-1]))
			return 1
		
		if n > 0:
			option = groups.pop()
			qualifier = option[:n]
			arg = option[n+1:]
			
			if qualifier == 'interface' or qualifier == 'ipaddress':
				if synctool_param.INTERFACES.has_key(node):
					stderr('%s:%d: redefinition of IP address for node %s' % (configfile, lineno, node))
					return 1
				
				if not arg:
					stderr("%s:%d: missing argument to node qualifier '%s'" % (configfile, lineno, qualifier))
					return 1
				
				synctool_param.INTERFACES[node] = arg
			
			elif qualifier == 'hostname':
				if synctool_param.HOSTNAMES.has_key(arg):
					stderr('%s:%d: hostname %s already in use for node %s' % (configfile, lineno, arg, synctool_param.HOSTNAMES[arg]))
					return 1
				
				if not arg:
					stderr("%s:%d: missing argument to node qualifier 'hostname'" % (configfile, lineno))
					return 1
				
				synctool_param.HOSTNAMES[arg] = node
			
			else:
				stderr('%s:%d: unknown node qualifier %s' % (configfile, lineno, qualifier))
				return 1
	
	try:
		synctool_param.NODES[node] = expand_grouplist(groups)
	except RuntimeError, e:
		stderr('%s:%d: a group list can not contain node names' % (configfile, lineno))
		return 1
	
	return 0


# keyword: ignore_host
def config_ignore_host(arr, configfile, lineno):
	return config_ignore_node(arr, configfile, lineno)


# keyword: ignore_node
def config_ignore_node(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires 1 argument: the nodename to ignore" % (configfile, lineno, arr[0]))
		return 1
	
	for node in arr[1:]:
		if not node in synctool_param.IGNORE_GROUPS:
			synctool_param.IGNORE_GROUPS.append(node)
	return 0


# keyword: ignore_group
def config_ignore_group(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires 1 argument: the groupname to ignore" % (configfile, lineno, arr[0]))
		return 1
	
	for group in arr[1:]:
		if not group in synctool_param.IGNORE_GROUPS:
			synctool_param.IGNORE_GROUPS.append(group)
	
		# add any (yet) unknown group names to the group_defs dict
		if not synctool_param.GROUP_DEFS.has_key(group):
			synctool_param.GROUP_DEFS[group] = None
	
	return 0


# keyword: on_update
def config_on_update(arr, configfile, lineno):
	if len(arr) < 3:
		stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (configfile, lineno))
		return 1
	
	file = synctool_lib.prepare_path(arr[1])
	cmd = string.join(arr[2:])
	cmd = synctool_lib.prepare_path(cmd)
	
	#
	#	check if the script exists
	#
	if cmd[0] != '/':
		# if relative path, use scriptdir
		# but what to do if scriptdir hasn't been set yet? Use default ...
		if not synctool_param.SCRIPT_DIR:
			synctool_param.SCRIPT_DIR = os.path.join(synctool_param.MASTERDIR, 'scripts')
		
		# do not use os.path.join() on dir+cmd+arguments
		cmd = synctool_param.SCRIPT_DIR + '/' + cmd
	
	# get the command file
	arr = string.split(cmd)
	cmdfile = arr[0]
	
	if not os.path.isfile(cmdfile):
		stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmdfile))
		return 1
	
	synctool_param.ON_UPDATE[file] = cmd
	return 0


# keyword: always_run
def config_always_run(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (configfile, lineno))
		return 1
	
	cmd = string.join(arr[1:])
	cmd = synctool_lib.prepare_path(cmd)
	
	if cmd in synctool_param.ALWAYS_RUN:
		stderr("%s:%d: same command defined again: %s" % (configfile, lineno, cmd))
		return 1
	
	#
	#	check if the script exists
	#
	if cmd[0] != '/':
		# if relative path, use scriptdir
		# but what to do if scriptdir hasn't been set yet? Use default ...
		if not synctool_param.SCRIPT_DIR:
			synctool_param.SCRIPT_DIR = os.path.join(synctool_param.MASTERDIR, 'scripts')
		
		# do not use os.path.join() on dir+cmd+arguments
		cmd = synctool_param.SCRIPT_DIR + '/' + cmd
	
	# get the command file
	arr = string.split(cmd)
	cmdfile = arr[1]
	
	if not os.path.isfile(cmdfile):
		stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmdfile))
		return 1
	
	synctool_param.ALWAYS_RUN.append(cmd)
	return 0


# keyword: diff_cmd
def config_diff_cmd(arr, configfile, lineno):
	(err, synctool_param.DIFF_CMD) = _config_command('diff_cmd', arr, 'diff', configfile, lineno)
	return err


# keyword: ping_cmd
def config_ping_cmd(arr, configfile, lineno):
	(err, synctool_param.PING_CMD) = _config_command('ping_cmd', arr, 'ping', configfile, lineno)
	return err


# keyword: ssh_cmd
def config_ssh_cmd(arr, configfile, lineno):
	(err, synctool_param.SSH_CMD) = _config_command('ssh_cmd', arr, 'ssh', configfile, lineno)
	return err


# keyword: scp_cmd
def config_scp_cmd(arr, configfile, lineno):
	(err, synctool_param.SCP_CMD) = _config_command('scp_cmd', arr, 'scp', configfile, lineno)
	return err


# keyword: rsync_cmd
def config_rsync_cmd(arr, configfile, lineno):
	
	# Note! strip_multiple_slashes() will break "rsync://" paths
	# and strip_trailing_slashes() may break rsync paths
	# but these are usually not used in rsync_cmd
	
	(err, synctool_param.RSYNC_CMD) = _config_command('rsync_cmd', arr, 'rsync', configfile, lineno)
	return err


# keyword: synctool_cmd
def config_synctool_cmd(arr, configfile, lineno):
	(err, synctool_param.SYNCTOOL_CMD) = _config_command('synctool_cmd', arr, 'synctool.py', configfile, lineno)
	return err


# keyword: logfile
def config_logfile(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'logfile' requires an argument: the full path to the file to write log messages to" % (configfile, lineno))
		return 1
	
	synctool_param.LOGFILE = synctool_lib.prepare_path(string.join(arr[1:]))
	return 0

		
# keyword: num_proc
def config_num_proc(arr, configfile, lineno):
	(err, synctool_param.NUM_PROC) = _config_integer('num_proc', arr[1], configfile, lineno)
	
	if not err and synctool_param.NUM_PROC < 1:
		stderr("%s:%d: invalid argument for num_proc" % (configfile, lineno))
		return 1
	
	return err


def expand_grouplist(grouplist):
	'''expand a list of (compound) groups recursively
	Returns the expanded group list'''
	
	groups = []
	
	for elem in grouplist:
		groups.append(elem)
		
		if synctool_param.GROUP_DEFS.has_key(elem):
			compound_groups = synctool_param.GROUP_DEFS[elem]
			
			# mind that GROUP_DEFS[group] can be None
			# for any groups that have no subgroups
			if compound_groups != None:
				groups.extend(compound_groups)
		else:
			# node names are often treated in the code as groups too ...
			# but they are special groups, and can not be in a compound group just
			# to prevent odd things from happening
			if synctool_param.NODES.has_key(elem):
				raise RuntimeError, 'node %s can not be part of compound group list' % elem
			
			synctool_param.GROUP_DEFS[elem] = None
	
	# remove duplicates
	# this looks pretty lame ... but Python sets are not usable here;
	# sets mess around with the order and Python sets changed in Python 2.6
	
	expanded_grouplist = []
	for elem in groups:
		if not elem in expanded_grouplist:
			expanded_grouplist.append(elem)
	
	return expanded_grouplist


# EOB
