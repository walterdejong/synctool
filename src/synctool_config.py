#! /usr/bin/env python
#
#	synctool-config	WJ109
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_lib

import os
import sys
import string
import socket
import getopt

ACTION = 0
ACTION_OPTION = None
ARG_NODENAMES = None
ARG_GROUPS = None
ARG_CMDS = None

# these are enums for the "list" command-line options
ACTION_LIST_NODES = 1
ACTION_LIST_GROUPS = 2
ACTION_NODES = 3
ACTION_GROUPS = 4
ACTION_MASTERDIR = 5
ACTION_CMDS = 6
ACTION_NUMPROC = 7
ACTION_VERSION = 8
ACTION_PREFIX = 9
ACTION_LOGFILE = 10
ACTION_NODENAME = 11
ACTION_LIST_DIRS = 12

# optional: do not list hosts/groups that are ignored
OPT_FILTER_IGNORED = False
# optional: list interface names for the selected nodes
OPT_INTERFACE = False


def stderr(str):
	sys.stderr.write(str + '\n')


def read_config():
	'''read the config file and set a bunch of globals'''
	
	if not os.path.isfile(synctool_param.CONF_FILE):
		stderr("no such config file '%s'" % synctool_param.CONF_FILE)
		sys.exit(-1)
	
	errors = read_config_file(synctool_param.CONF_FILE)
	
	# if missing, set default directories
	if synctool_param.MASTERDIR == None:
		synctool_param.MASTERDIR = '.'			# hmmm ... nice for debugging, but shouldn't this be /var/lib/synctool ?
	
	if not synctool_param.OVERLAY_DIRS:
		synctool_param.OVERLAY_DIRS.append(os.path.join(synctool_param.MASTERDIR, 'overlay'))
		if not os.path.isdir(synctool_param.OVERLAY_DIRS[0]):
			stderr('error: no such directory: %s' % synctool_param.OVERLAY_DIRS[0])
			errors = errors + 1
	
	if not synctool_param.DELETE_DIRS:
		synctool_param.DELETE_DIRS.append(os.path.join(synctool_param.MASTERDIR, 'delete'))
		if not os.path.isdir(synctool_param.DELETE_DIRS[0]):
			stderr('error: no such directory: %s' % synctool_param.DELETE_DIRS[0])
			errors = errors + 1
	
	if not synctool_param.TASKS_DIRS:
		synctool_param.TASKS_DIRS.append(os.path.join(synctool_param.MASTERDIR, 'tasks'))
		if not os.path.isdir(synctool_param.TASKS_DIRS[0]):
			stderr('error: no such directory: %s' % synctool_param.TASKS_DIRS[0])
			errors = errors + 1
	
	if not synctool_param.SCRIPT_DIR:
		synctool_param.SCRIPT_DIR = os.path.join(synctool_param.MASTERDIR, 'scripts')
		if not os.path.isdir(synctool_param.SCRIPT_DIR):
			stderr('error: no such directory: %s' % synctool_param.SCRIPT_DIR)
			errors = errors + 1
	
	if errors > 0:
		sys.exit(-1)
	
	# implicitly add 'nodename' as first group
	for node in get_all_nodes():
		insert_group(node, node)
	
	# implicitly add group 'all'
	if not synctool_param.GROUP_DEFS.has_key('all'):
		synctool_param.GROUP_DEFS['all'] = None
	
	for node in get_all_nodes():
		if not 'all' in synctool_param.NODES[node]:
			synctool_param.NODES[node].append('all')
	
	# implicitly add group 'none'
	if not synctool_param.GROUP_DEFS.has_key('none'):
		synctool_param.GROUP_DEFS['none'] = None
	
	if not 'none' in synctool_param.IGNORE_GROUPS:
		synctool_param.IGNORE_GROUPS.append('none')
	
	# do not make new backup copies when --erase was given
	if synctool_lib.ERASE_SAVED:
		synctool_param.BACKUP_COPIES = False
	

def read_config_file(configfile):
	'''read a (included) config file'''
	'''returns 0 on success, or error count on errors'''
	
	try:
		f = open(configfile, 'r')
	except IOError, reason:
		stderr("failed to read config file '%s' : %s" % (configfile, reason))
		return 1

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

		#
		#	keyword: masterdir
		#
		if keyword == 'masterdir':
			if synctool_param.MASTERDIR != None:
				stderr("%s:%d: redefinition of masterdir" % (configfile, lineno))
				errors = errors + 1
				continue
			
			if not os.path.isdir(arr[1]):
				stderr('%s:%d: no such directory for masterdir' % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.MASTERDIR = synctool_lib.strip_multiple_slashes(arr[1])
			synctool_param.MASTERDIR = synctool_lib.strip_trailing_slash(synctool_param.MASTERDIR)
			synctool_param.MASTER_LEN = len(synctool_param.MASTERDIR) + 1
			
			if synctool_param.MASTERDIR == '$masterdir':
				stderr("%s:%d: masterdir can not be set to '$masterdir', sorry" % (configfile, lineno))
				sys.exit(1)
			
			continue

		#
		#	keyword: include
		#
		if keyword == 'include':
			# recursively read the given config file
			file = synctool_lib.prepare_path(arr[1])
			errors = errors + read_config_file(file)
			continue

		#
		#	keyword: overlaydir
		#
		if keyword == 'overlaydir':
			if arr[1] in synctool_param.OVERLAY_DIRS:
				stderr("%s:%d: already in overlaydir" % (configfile, lineno))
				errors = errors + 1
				continue
			
			the_dir = synctool_lib.prepare_path(arr[1])
			
			if not os.path.isdir(the_dir):
				stderr('%s:%d: no such directory for overlaydir' % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.OVERLAY_DIRS.append(the_dir)
			continue
		
		#
		#	keyword: deletedir
		#
		if keyword == 'deletedir':
			if arr[1] in synctool_param.DELETE_DIRS:
				stderr("%s:%d: already in deletedir" % (configfile, lineno))
				errors = errors + 1
				continue
			
			the_dir = synctool_lib.prepare_path(arr[1])
			
			if not os.path.isdir(the_dir):
				stderr('%s:%d: no such directory for deletedir' % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.DELETE_DIRS.append(the_dir)
			continue
		
		#
		#	keyword: tasksdir
		#
		if keyword == 'tasksdir':
			if arr[1] in synctool_param.TASKS_DIRS:
				stderr("%s:%d: already in tasksdir" % (configfile, lineno))
				errors = errors + 1
				continue
			
			the_dir = synctool_lib.prepare_path(arr[1])
			
			if not os.path.isdir(the_dir):
				stderr('%s:%d: no such directory for tasksdir' % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.TASKS_DIRS.append(the_dir)
			continue
		
		#
		#	keyword: scriptdir
		#
		if keyword == 'scriptdir':
			if synctool_param.SCRIPT_DIR != None:
				stderr("%s:%d: redefinition of scriptdir" % (configfile, lineno))
				errors = errors + 1
				continue
			
			the_dir = synctool_lib.prepare_path(arr[1])
			
			if not os.path.isdir(the_dir):
				stderr('%s:%d: no such directory for scriptdir' % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.SCRIPT_DIR = the_dir
			continue
		
		#
		#	keyword: symlink_mode
		#
		if keyword == 'symlink_mode':
			try:
				mode = int(arr[1], 8)
			except ValueError:
				stderr("%s:%d: invalid argument for symlink_mode" % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.SYMLINK_MODE = mode
			continue
		
		#
		#	keyword: require_extension
		#
		if keyword == 'require_extension':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.REQUIRE_EXTENSION = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.REQUIRE_EXTENSION = False
			
			else:
				stderr('%s:%d: invalid argument for require_extension' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: full_path
		#
		if keyword == 'full_path':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.FULL_PATH = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				# this does nothing!
				# The default value for FULL_PATH is False
				# This value can be overridden on the command-line in which
				# case FULL_PATH will be set to True from get_options()
				pass
			
			else:
				stderr('%s:%d: invalid argument for full_path' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: backup_copies
		#
		if keyword == 'backup_copies':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.BACKUP_COPIES = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.BACKUP_COPIES = False
				pass
			
			else:
				stderr('%s:%d: invalid argument for backup_copies' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: ignore_dotfiles
		#
		if keyword == 'ignore_dotfiles':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.IGNORE_DOTFILES = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.IGNORE_DOTFILES = False
			
			else:
				stderr('%s:%d: invalid argument for ignore_dotfiles' % (configfile, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: ignore_dotdirs
		#
		if keyword == 'ignore_dotdirs':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.IGNORE_DOTDIRS = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.IGNORE_DOTDIRS = False
			
			else:
				stderr('%s:%d: invalid argument for ignore_dotdirs' % (configfile, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: ignore
		#
		if keyword in ('ignore', 'ignore_file', 'ignore_files', 'ignore_dir', 'ignore_dirs'):
			if len(arr) < 2:
				stderr("%s:%d: 'ignore' requires at least 1 argument: the file or directory to ignore" % (configfile, lineno))
				errors = errors + 1
				continue

			synctool_param.IGNORE_FILES.extend(arr[1:])
			continue
		
		#
		#	keyword: colorize
		#
		if keyword == 'colorize':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.COLORIZE = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				# TODO this may be overridden from the cmdline
				synctool_param.COLORIZE = False
			
			else:
				stderr('%s:%d: invalid argument for colorize' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: colorize_full_lines
		#
		if keyword == 'colorize_full_lines':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.COLORIZE_FULL_LINES = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.COLORIZE_FULL_LINES = False
			
			else:
				stderr('%s:%d: invalid argument for colorize_full_lines' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: colorize_bright/colorize_bold
		#
		if keyword == 'colorize_bright' or keyword == 'colorize_bold':
			value = string.lower(arr[1])
			if value in synctool_param.BOOLEAN_VALUE_TRUE:
				synctool_param.COLORIZE_BRIGHT = True
			
			elif value in synctool_param.BOOLEAN_VALUE_FALSE:
				synctool_param.COLORIZE_BRIGHT = False
			
			else:
				stderr('%s:%d: invalid argument for colorize_bright/colorize_bold' % (synctool_param.CONF_FILE, lineno))
				errors = errors + 1
			continue
		
		#
		#	keyword: color_xxx
		#
		if keyword in ('color_info', 'color_warning', 'color_error', 'color_fail',
			'color_sync', 'color_link', 'color_mkdir', 'color_rm',
			'color_chown', 'color_chmod', 'color_exec'):
			value = string.lower(arr[1])
			if value in synctool_lib.COLORMAP.keys():
				synctool_param.TERSE_COLORS[keyword[6:]] = value
			
			else:
				stderr('%s:%d: invalid argument for %s' % (synctool_param.CONF_FILE, lineno, keyword))
				errors = errors + 1
			continue
		
		#
		#	keyword: group
		#
		if keyword == 'group':
			if len(arr) < 3:
				stderr("%s:%d: 'group' requires at least 2 arguments: the compound group name and at least 1 member group" % (configfile, lineno))
				errors = errors + 1
				continue
			
			group = arr[1]
			
			if synctool_param.GROUP_DEFS.has_key(group):
				stderr("%s:%d: redefiniton of group %s" % (configfile, lineno, group))
				errors = errors + 1
				continue
			
			if synctool_param.NODES.has_key(group):
				stderr("%s:%d: %s was previously defined as a node" % (configfile, lineno, group))
				errors = errors + 1
				continue
			
			try:
				synctool_param.GROUP_DEFS[group] = expand_grouplist(arr[2:])
			except RuntimeError, e:
				stderr("%s:%d: compound groups can not contain node names" % (configfile, lineno))
				errors = errors + 1
				continue
			
			continue

		#
		#	keyword: host / node
		#
		if keyword == 'host' or keyword == 'node':
			if len(arr) < 2:
				stderr("%s:%d: '%s' requires at least 1 argument: the nodename" % (configfile, lineno, keyword))
				errors = errors + 1
				continue
			
			node = arr[1]
			groups = arr[2:]
			
			if synctool_param.NODES.has_key(node):
				stderr("%s:%d: redefinition of node %s" % (configfile, lineno, node))
				errors = errors + 1
				continue
			
			if synctool_param.GROUP_DEFS.has_key(node):
				stderr("%s:%d: %s was previously defined as a group" % (configfile, lineno, node))
				errors = errors + 1
				continue
			
			if len(groups) >= 1 and groups[-1][:10] == 'interface:':
				interface = groups[-1][10:]
				groups = groups[:-1]
				
				if synctool_param.INTERFACES.has_key(node):
					stderr("%s:%d: redefinition of interface for node %s" % (configfile, lineno, node))
					errors = errors + 1
					continue
				
				synctool_param.INTERFACES[node] = interface
			
			try:
				synctool_param.NODES[node] = expand_grouplist(groups)
			except RuntimeError, e:
				stderr("%s:%d: a group list can not contain node names" % (configfile, lineno))
				errors = errors + 1
				continue
			
			continue

		#
		#	keyword: ignore_host / ignore_node
		#
		if keyword == 'ignore_host' or keyword == 'ignore_node':
			if len(arr) < 2:
				stderr("%s:%d: '%s' requires 1 argument: the nodename to ignore" % (configfile, lineno, keyword))
				errors = errors + 1
				continue
			
			synctool_param.IGNORE_GROUPS.append(arr[1])
			continue
		
		#
		#	keyword: ignore_group
		#
		if keyword == 'ignore_group':
			if len(arr) < 2:
				stderr("%s:%d: 'ignore_group' requires at least 1 argument: the group to ignore" % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.IGNORE_GROUPS.extend(arr[1:])
			
			# add any (yet) unknown group names to the group_defs dict
			for elem in arr[1:]:
				if not synctool_param.GROUP_DEFS.has_key(elem):
					synctool_param.GROUP_DEFS[elem] = None
			
			continue
		
		#
		#	keyword: on_update
		#
		if keyword == 'on_update':
			if len(arr) < 3:
				stderr("%s:%d: 'on_update' requires at least 2 arguments: filename and shell command to run" % (configfile, lineno))
				errors = errors + 1
				continue
			
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
				errors = errors + 1
				continue
			
			synctool_param.ON_UPDATE[file] = cmd
			continue
		
		#
		#	keyword: always_run
		#
		if keyword == 'always_run':
			if len(arr) < 2:
				stderr("%s:%d: 'always_run' requires an argument: the shell command to run" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = string.join(arr[1:])
			cmd = synctool_lib.prepare_path(cmd)
			
			if cmd in synctool_param.ALWAYS_RUN:
				stderr("%s:%d: same command defined again: %s" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
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
				errors = errors + 1
				continue
			
			synctool_param.ALWAYS_RUN.append(cmd)
			continue
		
		#
		#	keyword: diff_cmd
		#
		if keyword == 'diff_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'diff_cmd' requires an argument: the full path to the 'diff' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			synctool_param.DIFF_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue

		#
		#	keyword: ping_cmd
		#
		if keyword == 'ping_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'ping_cmd' requires an argument: the full path to the 'ping' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			synctool_param.PING_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: ssh_cmd
		#
		if keyword == 'ssh_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'ssh_cmd' requires an argument: the full path to the 'ssh' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			synctool_param.SSH_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: scp_cmd
		#
		if keyword == 'scp_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'scp_cmd' requires an argument: the full path to the 'scp' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			synctool_param.SCP_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: rsync_cmd
		#
		if keyword == 'rsync_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'rsync_cmd' requires an argument: the full path to the 'rsync' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			# argh ... strip_multiple_slashes() will break "rsync://" paths
			# and strip_trailing_slashes() may break rsync paths
			# but these are usually not used in rsync_cmd
			synctool_param.RSYNC_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: synctool_cmd
		#
		if keyword == 'synctool_cmd':
			if len(arr) < 2:
				stderr("%s:%d: 'synctool_cmd' requires an argument: the full path to the remote 'synctool' command" % (configfile, lineno))
				errors = errors + 1
				continue
			
			cmd = synctool_lib.prepare_path(arr[1])
			if not os.path.isfile(cmd):
				stderr("%s:%d: no such command '%s'" % (configfile, lineno, cmd))
				errors = errors + 1
				continue
			
			synctool_param.SYNCTOOL_CMD = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: logfile
		#
		if keyword == 'logfile':
			if len(arr) < 2:
				stderr("%s:%d: 'logfile' requires an argument: the full path to the file to write log messages to" % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.LOGFILE = synctool_lib.prepare_path(string.join(arr[1:]))
			continue
		
		#
		#	keyword: num_proc
		#
		if keyword == 'num_proc':
			try:
				num_proc = int(arr[1])
			except ValueError:
				stderr("%s:%d: invalid argument for num_proc" % (configfile, lineno))
				errors = errors + 1
				continue
			
			if num_proc < 1:
				stderr("%s:%d: invalid argument for num_proc" % (configfile, lineno))
				errors = errors + 1
				continue
			
			synctool_param.NUM_PROC = num_proc
			continue
		
		stderr("%s:%d: unknown keyword '%s'" % (configfile, lineno, keyword))
		errors = errors + 1
	
	f.close()
	return errors


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
	# sets mess around with the order (probably because the elements are string values)
	
	expanded_grouplist = []
	for elem in groups:
		if not elem in expanded_grouplist:
			expanded_grouplist.append(elem)
	
	return expanded_grouplist


def add_myhostname():
	'''add the hostname of the current host to the configuration, so that it can be used'''
	'''also determine the nodename of the current host'''
	
	#
	#	get my hostname
	#
	synctool_param.HOSTNAME = hostname = socket.gethostname()
	
	arr = string.split(hostname, '.')
	short_hostname = arr[0]
	
	all_nodes = get_all_nodes()
	
	if hostname != short_hostname and hostname in all_nodes and short_hostname in all_nodes:
		stderr("%s: conflict; node %s and %s are both defined" % (synctool_param.CONF_FILE, hostname, arr[0]))
		sys.exit(-1)
	
	nodename = None
	
	if short_hostname in all_nodes:
		nodename = short_hostname
	
	elif hostname in all_nodes:
		nodename = hostname
	
	else:
		# try to find a node that has the (short) hostname listed as interface
		# or as a group
		for node in all_nodes:
			iface = get_node_interface(node)
			if iface == short_hostname or iface == hostname:
				nodename = node
				break
			
			groups = get_groups(node)
			if short_hostname in groups or hostname in groups:
				nodename = node
				break
	
	synctool_param.NODENAME = nodename
	
	if nodename != None:
		# implicitly add hostname as first group
		insert_group(nodename, hostname)
		insert_group(nodename, short_hostname)
		insert_group(nodename, nodename)


def remove_ignored_groups():
	'''remove ignored groups from all node definitions'''
	
	for host in synctool_param.NODES.keys():
		changed = False
		groups = synctool_param.NODES[host]
		for ignore in synctool_param.IGNORE_GROUPS:
			if ignore in groups:
				groups.remove(ignore)
				changed = True

		if changed:
			synctool_param.NODES[host] = groups


def insert_group(node, group):
	'''add group to node definition'''

	if synctool_param.NODES.has_key(node):
		if group in synctool_param.NODES[node]:
			synctool_param.NODES[node].remove(group)		# this is to make sure it comes first

		synctool_param.NODES[node].insert(0, group)
	else:
		synctool_param.NODES[node] = [group]


def get_all_nodes():
	return synctool_param.NODES.keys()


def get_node_interface(node):
	if synctool_param.INTERFACES.has_key(node):
		return synctool_param.INTERFACES[node]
	
	return node


def list_all_nodes():
	nodes = get_all_nodes()
	nodes.sort()
	
	if synctool_param.IGNORE_GROUPS != None:
		ignore_nodes = get_nodes_in_groups(synctool_param.IGNORE_GROUPS)
	else:
		ignore_nodes = []
	
	for host in nodes:
		if host in ignore_nodes:
			if OPT_INTERFACE:
				host = get_node_interface(host)
			
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % host
		else:
			if OPT_INTERFACE:
				host = get_node_interface(host)
			
			print host


def make_all_groups():
	'''make a list of all possible groups
	This is a set of all group names plus all node names'''
	
	arr = synctool_param.GROUP_DEFS.keys()
	arr.extend(synctool_param.NODES.keys())
	
# older versions of python do not support sets BUT that doesn't matter ...
# all groups + nodes should have no duplicates anyway
#	return list(set(arr))
	return arr


def list_all_groups():
	groups = synctool_param.GROUP_DEFS.keys()
	groups.sort()
	
	for group in groups:
		if group in synctool_param.IGNORE_GROUPS:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_groups(nodename):
	'''returns the groups for the node'''
	
	if synctool_param.NODES.has_key(nodename):
		return synctool_param.NODES[nodename]
	
	return []


def get_my_groups():
	'''returns the groups for this node'''
	
	if synctool_param.NODES.has_key(synctool_param.NODENAME):
		return synctool_param.NODES[synctool_param.NODENAME]
	
	return []


def list_nodes(nodenames):
	groups = []
	
	for nodename in nodenames:
		if not synctool_param.NODES.has_key(nodename):
			stderr("no such node '%s' defined" % nodename)
			sys.exit(1)
		
		for group in get_groups(nodename):
			if not group in groups:
				groups.append(group)
	
#	groups.sort()							# group order is important
	
	for group in groups:
		if group in synctool_param.IGNORE_GROUPS:
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % group
		else:
			print group


def get_nodes_in_groups(nodegroups):
	'''returns the nodes that are in [groups]'''
	
	arr = []
	
	nodes = synctool_param.NODES.keys()
	
	for nodegroup in nodegroups:
		for node in nodes:
			if nodegroup in synctool_param.NODES[node] and not node in arr:
				arr.append(node)
	
	return arr


def list_nodegroups(nodegroups):
	all_groups = make_all_groups()
	
	for nodegroup in nodegroups:
		if not nodegroup in all_groups:
			stderr("no such nodegroup '%s' defined" % nodegroup)
			sys.exit(1)
	
	arr = get_nodes_in_groups(nodegroups)
	arr.sort()
	
	for node in arr:
		if node in synctool_param.IGNORE_GROUPS:
			if OPT_INTERFACE:
				node = get_node_interface(node)
			
			if not OPT_FILTER_IGNORED:
				print '%s (ignored)' % node
		else:
			if OPT_INTERFACE:
				node = get_node_interface(node)
			
			print node


def list_commands(cmds):
	'''display command setting'''
	
	for cmd in cmds:
		if cmd == 'diff':
			print synctool_param.DIFF_CMD
		
		elif cmd == 'ssh':
			print synctool_param.SSH_CMD
		
		elif cmd == 'rsync':
			print synctool_param.RSYNC_CMD
		
		elif cmd == 'synctool':
			print synctool_param.SYNCTOOL_CMD
		
		else:
			stderr("no such command '%s' available in synctool" % cmd)


def list_dirs():
	'''display directory settings'''
	
	print 'masterdir', synctool_param.MASTERDIR
	
	# Note: do not use prettypath() here, for shell scripters
	# They will still have to awk, and multiple paths are possible ...
	
	for path in synctool_param.OVERLAY_DIRS:
		print 'overlaydir', path
	
	for path in synctool_param.DELETE_DIRS:
		print 'deletedir', path
	
	for path in synctool_param.TASKS_DIRS:
		print 'tasksdir', path
	
	print 'scriptdir', synctool_param.SCRIPT_DIR


def set_action(a, opt):
	global ACTION, ACTION_OPTION
	
	if ACTION > 0:
		stderr('the options %s and %s can not be combined' % (ACTION_OPTION, opt))
		sys.exit(1)
	
	ACTION = a
	ACTION_OPTION = opt


def usage():
	print 'usage: %s [options] [<argument>]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help               Display this information'
	print '  -c, --conf=dir/file      Use this config file'
	print '                           (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -l, --list-nodes         List all configured nodes'
	print '  -L, --list-groups        List all configured groups'
	print '  -n, --node=nodelist      List all groups this node is in'
	print '  -g, --group=grouplist    List all nodes in this group'
	print '  -i, --interface          List selected nodes by interface'
	print '  -f, --filter-ignored     Do not list ignored nodes and groups'
	print
	print '  -C, --command=command    Display setting for command'
	print '  -p, --numproc            Display numproc setting'
	print '  -m, --masterdir          Display the masterdir setting'
	print '  -d, --list-dirs          Display directory settings'
	print '      --prefix             Display installation prefix'
	print '      --nodename           Display my nodename'
	print '      --logfile            Display configured logfile'
	print '      --nodename           Display my nodename'
	print '  -v, --version            Display synctool version'
	print
	print 'A node/group list can be a single value, or a comma-separated list'
	print 'A command is a list of these: diff, ssh, rsync, synctool'
	print
	print 'synctool-config by Walter de Jong <walter@heiho.net> (c) 2009-2011'


def get_options():
	global CONF_FILE, ARG_NODENAMES, ARG_GROUPS, ARG_CMDS
	global OPT_FILTER_IGNORED, OPT_INTERFACE
	
	progname = os.path.basename(sys.argv[0])
	
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)
	
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'hc:mdlLn:g:ifC:pv',
			['help', 'conf=', 'masterdir', 'list-dirs', 'list-nodes', 'list-groups',
			'node=', 'group=', 'interface', 'filter-ignored', 'command', 'numproc',
			'version', 'prefix', 'nodename', 'logfile'])
	
	except getopt.error, (reason):
		print
		print '%s: %s' % (progname, reason)
		print
		usage()
		sys.exit(1)
	
	except getopt.GetoptError, (reason):
		print
		print '%s: %s' % (progname, reason)
		print
		usage()
		sys.exit(1)
	
	except:
		usage()
		sys.exit(1)
	
	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command-line')
		sys.exit(1)
	
	errors = 0
	
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE=arg
			continue
		
		if opt in ('-m', '--masterdir'):
			set_action(ACTION_MASTERDIR, '--masterdir')
			continue
		
		if opt in ('-d', '--list-dirs'):
			set_action(ACTION_LIST_DIRS, '--list-dirs')
			continue
		
		if opt in ('-l', '--list-nodes'):
			set_action(ACTION_LIST_NODES, '--list-nodes')
			continue
		
		if opt in ('-L', '--list-groups'):
			set_action(ACTION_LIST_GROUPS, '--list-groups')
			continue
		
		if opt in ('-n', '--node'):
			set_action(ACTION_NODES, '--node')
			ARG_NODENAMES = string.split(arg, ',')
			continue
		
		if opt in ('-g', '--group'):
			set_action(ACTION_GROUPS, '--group')
			ARG_GROUPS = string.split(arg, ',')
			continue
		
		if opt in ('-i', '--interface'):
			OPT_INTERFACE = True
			continue
		
		if opt in ('-f', '--filter-ignored'):
			OPT_FILTER_IGNORED = True
			continue
		
		if opt in ('-C', '--command'):
			set_action(ACTION_CMDS, '--command')
			ARG_CMDS = string.split(arg, ',')
			continue
		
		if opt in ('-p', '--numproc'):
			set_action(ACTION_NUMPROC, '--numproc')
			continue
		
		if opt in ('-v', '--version'):
			set_action(ACTION_VERSION, '--version')
			continue
		
		if opt == '--prefix':
			set_action(ACTION_PREFIX, '--prefix')
			continue
		
		if opt == '--nodename':
			set_action(ACTION_NODENAME, '--nodename')
			continue
		
		if opt == '--logfile':
			set_action(ACTION_LOGFILE, '--logfile')
			continue
		
		if opt == '--nodename':
			set_action(ACTION_NODENAME, '--nodename')
			continue
		
		stderr("unknown command line option '%s'" % opt)
		errors = errors + 1
	
	if errors:
		usage()
		sys.exit(1)
	
	if not ACTION:
		usage()
		sys.exit(1)


if __name__ == '__main__':
	get_options()
	
	if ACTION == ACTION_VERSION:
		print synctool_param.VERSION
		sys.exit(0)
	
	read_config()
	
	if ACTION == ACTION_LIST_NODES:
		list_all_nodes()
	
	elif ACTION == ACTION_LIST_GROUPS:
		list_all_groups()
	
	elif ACTION == ACTION_NODES:
		if not ARG_NODENAMES:
			stderr("option '--node' requires an argument; the node name")
			sys.exit(1)
		
		list_nodes(ARG_NODENAMES)
	
	elif ACTION == ACTION_GROUPS:
		if not ARG_GROUPS:
			stderr("option '--node-group' requires an argument; the node group name")
			sys.exit(1)
		
		list_nodegroups(ARG_GROUPS)
	
	elif ACTION == ACTION_MASTERDIR:
		print synctool_param.MASTERDIR
	
	elif ACTION == ACTION_CMDS:
		list_commands(ARG_CMDS)
	
	elif ACTION == ACTION_NUMPROC:
		print synctool_param.NUM_PROC
	
	elif ACTION == ACTION_PREFIX:
		print os.path.abspath(os.path.dirname(sys.argv[0]))
	
	elif ACTION == ACTION_LIST_DIRS:
		list_dirs()
	
	elif ACTION == ACTION_LOGFILE:
		print synctool_param.LOGFILE
	
	elif ACTION == ACTION_NODENAME:
		add_myhostname()
		
		if synctool_param.NODENAME == None:
			stderr('unable to determine my nodename, please check %s' % synctool_param.CONF_FILE)
			sys.exit(1)
		
		if synctool_param.NODENAME in synctool_param.IGNORE_GROUPS:
			if not synctool_param.OPT_FILTER_IGNORED:
				if synctool_param.OPT_INTERFACE:
					print 'none (%s ignored)' % get_node_interface(synctool_param.NODENAME)
				else:
					print 'none (%s ignored)' % synctool_param.NODENAME
			
			sys.exit(0)
		
		if synctool_param.OPT_INTERFACE:
			print get_node_interface(synctool_param.NODENAME)
		else:
			print synctool_param.NODENAME
	
	elif ACTION == ACTION_NODENAME:
		add_myhostname()
		
		if NODENAME == None:
			stderr('unable to determine my nodename, please check %s' % CONF_FILE)
			sys.exit(1)
		
		if NODENAME in IGNORE_GROUPS:
			if not OPT_FILTER_IGNORED:
				if OPT_INTERFACE:
					print 'none (%s ignored)' % get_node_interface(NODENAME)
				else:
					print 'none (%s ignored)' % NODENAME
			
			sys.exit(0)
		
		if OPT_INTERFACE:
			print get_node_interface(NODENAME)
		else:
			print NODENAME
	
	else:
		raise RuntimeError, 'bug: unknown ACTION %d' % ACTION


# EOB
