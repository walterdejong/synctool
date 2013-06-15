#
#	synctool.configparser.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
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

import os
import sys
import string
import re

import synctool.lib
import synctool.param


# this allows alphanumeric concatenated by underscore, minus, or plus symbol
# and no other characters
#
# So valid names are: node1 node1-10 node_10_0_0_2 node1+node2
#
SPELLCHECK = re.compile(
	r'[a-zA-Z0-9]+(\_[a-zA-Z0-9]+|\-[a-zA-Z0-9]+|\+[a-zA-Z0-9]+)*')

# dict with {keyword: lineno}
# to see if a parameter is being redefined
DEFINED = {}


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
	else:
		this_module = sys.modules['synctool.configparser']

		lineno = 0
		errors = 0

		#
		# read lines from the config file
		# variable tmp_line is used to be able to do multi-line reads
		# (backslash terminated)
		#
		line = ''
		with f:
			while True:
				tmp_line = f.readline()
				if not tmp_line:
					break

				lineno += 1

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

				line = ''	# <-- line is being reset here;
							# use arr[] from here on

				if len(arr) <= 1:
					stderr('%s:%d: syntax error ; expected key/value pair' %
						(configfile, lineno))
					errors += 1
					continue

				keyword = string.lower(arr[0])

				# get the parser function
				try:
					func = getattr(this_module, 'config_%s' % keyword)
				except AttributeError:
					stderr("%s:%d: unknown keyword '%s'" %
						(configfile, lineno, keyword))
					errors += 1
					continue

				errors += func(arr, configfile, lineno)

	return errors


def check_definition(keyword, configfile, lineno):
	'''check whether a param was not defined earlier
	Returns False on error, True if OK'''

	global DEFINED

	if DEFINED.has_key(keyword):
		stderr("%s:%d: redefinition of '%s'" % (configfile, lineno, keyword))
		stderr("%s:%d: previous definition was at line %d" %
				(configfile, lineno, DEFINED[keyword]))
		return False

	DEFINED[keyword] = lineno
	return True


#
# config functions return the number of errors in the line
# This enables the 'include' keyword to return more than 1 error
#

def _config_boolean(param, value, configfile, lineno):
	if not check_definition(param, configfile, lineno):
		return (1, False)

	value = string.lower(value)
	if value in synctool.param.BOOLEAN_VALUE_TRUE:
		return (0, True)

	elif value in synctool.param.BOOLEAN_VALUE_FALSE:
		return (0, False)

	stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
	return (1, False)


def _config_integer(param, value, configfile, lineno, radix = 10):
	if not check_definition(param, configfile, lineno):
		return (1, 0)

	try:
		n = int(value, radix)
	except ValueError:
		stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
		return (1, 0)

	return (0, n)


def _config_color_variant(param, value, configfile, lineno):
	'''set a color by name'''

	if not check_definition(param, configfile, lineno):
		return 1

	value = string.lower(value)
	if value in synctool.lib.COLORMAP.keys():
		synctool.param.TERSE_COLORS[param[6:]] = value
		return 0

	stderr('%s:%d: invalid argument for %s' % (configfile, lineno, param))
	return 1


def _config_command(param, arr, short_cmd, configfile, lineno):
	'''helper for configuring rsync_cmd, ssh_cmd, synctool_cmd, etc.'''

	if not check_definition(param, configfile, lineno):
		return (1, None)

	if len(arr) < 2:
		stderr("%s:%d: '%s' requires an argument: "
			"the '%s' command, and any appropriate switches" %
			(configfile, lineno, param, short_cmd))
		return (1, None)

	# This function does not check the existence of the command
	# That is deferred until later; the client only runs diff_cmd,
	# while the master runs a bunch of commands

	return (0, synctool.lib.prepare_path(string.join(arr[1:])))


def spellcheck(name):
	'''Check for valid spelling of name
	Returns True if OK, False if not OK'''

	global SPELLCHECK

	m = SPELLCHECK.match(name)
	if not m:
		return False

	if m.group(0) != name:
		return False

	return True


# keyword: include
def config_include(arr, configfile, lineno):
	# recursively read the given config file
	return read_config_file(synctool.lib.prepare_path(arr[1]))


# keyword: prefix
def config_prefix(arr, configfile, lineno):
	if not check_definition(arr[0], configfile, lineno):
		return 1

	d = string.join(arr[1:])
	d = synctool.lib.strip_multiple_slashes(d)
	d = synctool.lib.strip_trailing_slash(d)

	synctool.param.PREFIX = d

	if not os.path.isdir(d):
		stderr('%s:%d: no such directory for prefix' % (configfile, lineno))
		return 1

	return 0


# keyword: tempdir
def config_tempdir(arr, configfile, lineno):
	if not check_definition(arr[0], configfile, lineno):
		return 1

	d = string.join(arr[1:])
	d = synctool.lib.prepare_path(d)

	if not os.path.isabs(d):
		stderr("%s:%d: tempdir must be an absolute path" %
			(configfile, lineno))
		return 1

	synctool.param.TEMP_DIR = d
	return 0


# keyword: package_manager
def config_package_manager(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'package_manager' requires an argument" %
			(configfile, lineno))
		return 1

	if not check_definition(arr[0], configfile, lineno):
		return 1

	if not arr[1] in synctool.param.KNOWN_PACKAGE_MANAGERS:
		stderr("%s:%d: unknown or unsupported package manager '%s'" %
			(configfile, lineno))
		return 1

	synctool.param.PACKAGE_MANAGER = arr[1]
	return 0


# keyword: symlink_mode
def config_symlink_mode(arr, configfile, lineno):
	(err, synctool.param.SYMLINK_MODE) = _config_integer('symlink_mode',
		arr[1], configfile, lineno, 8)
	return err


# keyword: require_extension
def config_require_extension(arr, configfile, lineno):
	(err, synctool.param.REQUIRE_EXTENSION) = _config_boolean(
		'require_extension', arr[1], configfile, lineno)
	return err


# keyword: full_path
def config_full_path(arr, configfile, lineno):
	(err, synctool.param.FULL_PATH) = _config_boolean('full_path',
		arr[1], configfile, lineno)
	return err


# keyword: backup_copies
def config_backup_copies(arr, configfile, lineno):
	(err, synctool.param.BACKUP_COPIES) = _config_boolean('backup_copies',
		arr[1], configfile, lineno)
	return err


# keyword: ignore_dotfiles
def config_ignore_dotfiles(arr, configfile, lineno):
	(err, synctool.param.IGNORE_DOTFILES) = _config_boolean('ignore_dotfiles',
		arr[1], configfile, lineno)
	return err


# keyword: ignore_dotdirs
def config_ignore_dotdirs(arr, configfile, lineno):
	(err, synctool.param.IGNORE_DOTDIRS) = _config_boolean('ignore_dotdirs',
		arr[1], configfile, lineno)
	return err


# keyword: ignore
def config_ignore(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'ignore' requires at least 1 argument: "
			"the file or directory to ignore" %	(configfile, lineno))
		return 1

	for file in arr[1:]:
		# if file has wildcards, put it in array IGNORE_FILES_WITH_WILDCARDS
		if string.find(file, '*') >= 0 or string.find(file, '?') >= 0 \
			or (string.find(file, '[') >= 0 and string.find(file, ']') >= 0):
			if not file in synctool.param.IGNORE_FILES_WITH_WILDCARDS:
				synctool.param.IGNORE_FILES_WITH_WILDCARDS.append(file)
		else:
			# no wildcards, do a regular ignore
			if not file in synctool.param.IGNORE_FILES:
				synctool.param.IGNORE_FILES.append(file)

	return 0


# keyword: terse
def config_terse(arr, configfile, lineno):
	(err, synctool.param.TERSE) = _config_boolean('terse', arr[1],
		configfile, lineno)
	return err


# keyword: colorize
def config_colorize(arr, configfile, lineno):
	(err, synctool.param.COLORIZE) = _config_boolean('colorize', arr[1],
		configfile, lineno)
	return err


# keyword: colorize_full_line
def config_colorize_full_line(arr, configfile, lineno):
	(err, synctool.param.COLORIZE_FULL_LINE) = _config_boolean(
		'colorize_full_line', arr[1], configfile, lineno)
	return err


# keyword: colorize_full_lines
# nice for typo's
def config_colorize_full_lines(arr, configfile, lineno):
	(err, synctool.param.COLORIZE_FULL_LINE) = _config_boolean(
		'colorize_full_line', arr[1], configfile, lineno)
	return err


# keyword: colorize_bright
def config_colorize_bright(arr, configfile, lineno):
	(err, synctool.param.COLORIZE_BRIGHT) = _config_boolean(
		'colorize_bright', arr[1], configfile, lineno)
	return err


# keyword: colorize_bold
def config_colorize_bold(arr, configfile, lineno):
	(err, synctool.param.COLORIZE_BRIGHT) = _config_boolean('colorize_bold',
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


# keyword: default_nodeset
def config_default_nodeset(arr, configfile, lineno):
	if not check_definition(arr[0], configfile, lineno):
		return 1

	if len(arr) < 2:
		stderr("%s:%d: 'default_nodeset' requires an argument" %
			(configfile, lineno))
		return 1

	synctool.param.DEFAULT_NODESET = set()

	for g in arr[1:]:
		if not spellcheck(g):
			stderr("%s:%d: invalid name '%s'" % (configfile, lineno, g))
			return 1

		if g == 'none':
			synctool.param.DEFAULT_NODESET = set()
		else:
			synctool.param.DEFAULT_NODESET.add(g)

	# for now, accept this as the default nodeset
	# There can be compound groups in it, so
	# synctool_config.read_config() will expand it to a list of nodes


# keyword: group
def config_group(arr, configfile, lineno):
	if len(arr) < 3:
		stderr("%s:%d: 'group' requires at least 2 arguments: "
			"the compound group name and at least 1 member group" %
			(configfile, lineno))
		return 1

	group = arr[1]

	if not spellcheck(group):
		stderr("%s:%d: invalid group name '%s'" %
			(configfile, lineno, group))
		return 1

	if group in ('all', 'none'):
		stderr("%s:%d: implicit group '%s' can not be redefined" %
			(configfile, lineno, group))
		return 1

	if synctool.param.GROUP_DEFS.has_key(group):
		stderr('%s:%d: redefinition of group %s' % (configfile, lineno, group))
		return 1

	if synctool.param.NODES.has_key(group):
		stderr('%s:%d: %s was previously defined as a node' %
			(configfile, lineno, group))
		return 1

	try:
		synctool.param.GROUP_DEFS[group] = expand_grouplist(arr[2:])
	except RuntimeError, e:
		stderr('%s:%d: compound groups can not contain node names' %
			(configfile, lineno))
		return 1

	return 0


# keyword: node
def config_node(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'node' requires at least 1 argument: the nodename" %
			(configfile, lineno))
		return 1

	node = arr[1]

	if not spellcheck(node):
		stderr("%s:%d: invalid node name '%s'" %
			(configfile, lineno, node))
		return 1

	groups = arr[2:]

	if synctool.param.NODES.has_key(node):
		stderr('%s:%d: redefinition of node %s' % (configfile, lineno, node))
		# TODO "previous definition of %s was here"
		return 1

	if synctool.param.GROUP_DEFS.has_key(node):
		stderr('%s:%d: %s was previously defined as a group' %
			(configfile, lineno, node))
		# TODO "previous definition of %s was here"
		return 1

	for g in groups:
		if g == 'all':
			stderr("%s:%d: illegal to use group 'all' in node definition" %
				(configfile, lineno))
			stderr("%s:%d: group 'all' automatically applies to all nodes" %
				(configfile, lineno))
			return 1

		if g == 'none':
			stderr("%s:%d: illegal to use group 'none' in node definition" %
				(configfile, lineno))
			stderr("%s:%d: use 'ignore_node' to disable a node" %
				(configfile, lineno))
			return 1

	if node in groups:
		stderr("%s:%d: illegal to list '%s' as group for node %s" %
			(configfile, lineno, node, node))
		return 1

	# node lines may end with special optional qualifiers like
	# 'ipaddress:', 'hostname:', 'hostid:'

	while len(groups) >= 1:
		n = string.find(groups[-1], ':')
		if n < 0:
			break

		if n == 0:
			stderr("%s:%d: syntax error in node qualifier '%s'" %
				(configfile, lineno, groups[-1]))
			return 1

		if n > 0:
			option = groups.pop()
			qualifier = option[:n]
			arg = option[n+1:]

			if qualifier == 'ipaddress':
				if synctool.param.IPADDRESSES.has_key(node):
					stderr('%s:%d: redefinition of IP address for node %s' %
						(configfile, lineno, node))
					return 1

				if not arg:
					stderr("%s:%d: missing argument to node qualifier '%s'" %
						(configfile, lineno, qualifier))
					return 1

				synctool.param.IPADDRESSES[node] = arg

			elif qualifier == 'hostname':
				if synctool.param.HOSTNAMES.has_key(arg):
					stderr('%s:%d: hostname %s already in use for node %s' %
						(configfile, lineno, arg,
						synctool.param.HOSTNAMES[arg]))
					return 1

				if not arg:
					stderr("%s:%d: missing argument to node qualifier "
						"'hostname'" % (configfile, lineno))
					return 1

				synctool.param.HOSTNAMES[arg] = node
				synctool.param.HOSTNAMES_BY_NODE[node] = arg

			elif qualifier == 'hostid':
				try:
					f = open(arg, 'r')
				except IOError:
					# this is a real error ... but it doesn't matter on
					# the master node
					# So how to handle this?
					continue

				hostid = f.readline()

				f.close()

				if not hostid:
					continue

				hostid = string.strip(hostid)
				if not hostid:
					continue

				synctool.param.HOST_ID = hostid

			else:
				stderr('%s:%d: unknown node qualifier %s' %
					(configfile, lineno, qualifier))
				return 1

	try:
		synctool.param.NODES[node] = expand_grouplist(groups)
	except RuntimeError, e:
		stderr('%s:%d: a group list can not contain node names' %
			(configfile, lineno))
		return 1

	return 0


# keyword: ignore_node
def config_ignore_node(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: 'ignore_node' requires 1 argument: "
			"the nodename to ignore" % (configfile, lineno))
		return 1

	errors = 0

	for node in arr[1:]:
		if not spellcheck(node):
			stderr("%s:%d: invalid node name '%s'" % (configfile, lineno,
														node))
			errors += 1
			continue

		if node == 'none':
			continue

		if node == 'all':
			stderr("%s:%d: illegal to ignore 'all'" % (configfile, lineno))
			errors += 1
			continue

		synctool.param.IGNORE_GROUPS.add(node)

	return errors


# keyword: ignore_group
def config_ignore_group(arr, configfile, lineno):
	if len(arr) < 2:
		stderr("%s:%d: '%s' requires 1 argument: the groupname to ignore" %
			(configfile, lineno, arr[0]))
		return 1

	errors = 0

	for group in arr[1:]:
		if not spellcheck(group):
			stderr("%s:%d: invalid group name '%s'" %
				(configfile, lineno, group))
			errors += 1
			continue

		if group == 'none':
			continue

		if group == 'all':
			stderr("%s:%d: illegal to ignore 'all'" % (configfile, lineno))
			errors += 1
			continue

		synctool.param.IGNORE_GROUPS.add(group)

		# add any (yet) unknown group names to the group_defs dict
		if not synctool.param.GROUP_DEFS.has_key(group):
			synctool.param.GROUP_DEFS[group] = None

	return errors


# keyword: diff_cmd
def config_diff_cmd(arr, configfile, lineno):
	(err, synctool.param.DIFF_CMD) = _config_command('diff_cmd', arr,
		'diff', configfile, lineno)
	return err


# keyword: ping_cmd
def config_ping_cmd(arr, configfile, lineno):
	(err, synctool.param.PING_CMD) = _config_command('ping_cmd', arr,
		'ping', configfile, lineno)
	return err


# keyword: ssh_cmd
def config_ssh_cmd(arr, configfile, lineno):
	(err, synctool.param.SSH_CMD) = _config_command('ssh_cmd', arr,
		'ssh', configfile, lineno)
	return err


# keyword: scp_cmd
def config_scp_cmd(arr, configfile, lineno):
	(err, synctool.param.SCP_CMD) = _config_command('scp_cmd', arr,
		'scp', configfile, lineno)
	return err


# keyword: rsync_cmd
def config_rsync_cmd(arr, configfile, lineno):

	# Note! strip_multiple_slashes() will break "rsync://" paths
	# and strip_trailing_slashes() may break rsync paths
	# but these are usually not used in rsync_cmd

	(err, synctool.param.RSYNC_CMD) = _config_command('rsync_cmd', arr,
		'rsync', configfile, lineno)
	return err


# keyword: synctool_cmd
def config_synctool_cmd(arr, configfile, lineno):
	(err, synctool.param.SYNCTOOL_CMD) = _config_command('synctool_cmd', arr,
		'synctool.py', configfile, lineno)
	return err


# keyword: pkg_cmd
def config_pkg_cmd(arr, configfile, lineno):
	(err, synctool.param.PKG_CMD) = _config_command('pkg_cmd', arr,
		'synctool_pkg.py', configfile, lineno)
	return err


# keyword: logfile
def config_logfile(arr, configfile, lineno):
	if not check_definition(arr[0], configfile, lineno):
		return 1

	if len(arr) < 2:
		stderr("%s:%d: 'logfile' requires an argument: "
			"the full path to the file to write log messages to" %
			(configfile, lineno))
		return 1

	synctool.param.LOGFILE = synctool.lib.prepare_path(string.join(arr[1:]))
	return 0


# keyword: num_proc
def config_num_proc(arr, configfile, lineno):
	(err, synctool.param.NUM_PROC) = _config_integer('num_proc', arr[1],
		configfile, lineno)

	if not err and synctool.param.NUM_PROC < 1:
		stderr("%s:%d: invalid argument for num_proc" % (configfile, lineno))
		return 1

	return err


def expand_grouplist(grouplist):
	'''expand a list of (compound) groups recursively
	Returns the expanded group list'''

	groups = []

	for elem in grouplist:
		groups.append(elem)

		if synctool.param.GROUP_DEFS.has_key(elem):
			compound_groups = synctool.param.GROUP_DEFS[elem]

			# mind that GROUP_DEFS[group] can be None
			# for any groups that have no subgroups
			if compound_groups != None:
				groups.extend(compound_groups)
		else:
			# node names are treated as groups too ...
			# but they are special groups, and can not be in a compound group
			# just to prevent odd things from happening
			if synctool.param.NODES.has_key(elem):
				raise RuntimeError, ('node %s can not be part of '
									'compound group list' % elem)

			synctool.param.GROUP_DEFS[elem] = None

	# remove duplicates
	# this looks pretty lame ... but Python sets are not usable here;
	# sets mess around with the order and Python sets changed in Python 2.6

	expanded_grouplist = []
	for elem in groups:
		if not elem in expanded_grouplist:
			expanded_grouplist.append(elem)

	return expanded_grouplist


# EOB
