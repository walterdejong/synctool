# pylint: disable=consider-using-f-string, too-many-lines
# pylint: disable=too-few-public-methods,too-many-return-statements
# pylint: disable=too-many-branches
#
#   synctool.configparser.py    WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''config file parser'''

#
#   To make a new keyword for the config file, simply define a
#   function here like: def config_xxx(arr, configfile, lineno):
#   and it will just work (magic trick with getattr(module, functionname))
#

import os
import sys
import re

try:
    from typing import List, Dict, Tuple, Pattern
except ImportError:
    pass

from synctool import param
import synctool.lib
from synctool.lib import stderr
import synctool.range

# this allows alphanumeric concatenated by underscore, minus, or plus symbol
# and no other characters
# Valid names are: node1 node1-10 node_10_0_0_2 node1+node2
SPELLCHECK = re.compile(r'^[a-zA-Z](?:[_+-]?[a-zA-Z0-9])*$')    # type: Pattern

# this will match "60", "1h30m", "1w4d10h3m50s", "yes", etc.
PERSIST_TIME = re.compile(r'^\d+$|'
                          r'^(\d+[w])*(\d+[d])*(\d+[h])*(\d+[m])*(\d+[s])*$|'
                          r'^yes$|'
                          r'^none$')    # type: Pattern

# dict of defined Symbols
# to see if a parameter is being redefined
SYMBOLS = {}    # type: Dict[str, Symbol]


class Symbol:
    '''structure that says where a symbol was first defined'''

    def __init__(self, name=None, filename=None, lineno=0):
        # type: (str, str, int) -> None
        '''initialize instance'''

        self.name = name                    # not really used ...
        self.filename = filename
        self.lineno = lineno

    def origin(self):
        # type: () -> str
        '''Returns string "filename:lineno" where the symbol was
        first defined
        '''

        return '%s:%d' % (self.filename, self.lineno)


def read_config_file(configfile):
    # type: (str) -> int
    '''read a (included) config file
    Returns 0 on success, or error count on errors
    '''

    try:
        fconfig = open(configfile, 'r', encoding="utf-8")
    except IOError as err:
        stderr("error: failed to read config file '%s' : %s" % (configfile,
                                                                err.strerror))
        return 1

    this_module = sys.modules['synctool.configparser']

    lineno = 0
    errors = 0

    # read lines from the config file
    # variable tmp_line is used to be able to do multi-line reads
    # (backslash terminated)

    line = ''
    with fconfig:
        while True:
            tmp_line = fconfig.readline()
            if not tmp_line:
                break

            lineno += 1

            nhash = tmp_line.find('#')
            if nhash >= 0:
                tmp_line = tmp_line[:nhash]        # strip comment

            tmp_line = tmp_line.strip()
            if not tmp_line:
                continue

            if tmp_line[-1] == '\\':
                tmp_line = tmp_line[:-1].strip()
                line = line + ' ' + tmp_line
                continue

            line = line + ' ' + tmp_line
            tmp_line = ''

            arr = line.split()

            line = ''   # <-- line is being reset here;
                        # use arr[] from here on

            if len(arr) <= 1:
                stderr('%s:%d: syntax error ; expected key/value pair' %
                       (configfile, lineno))
                errors += 1
                continue

            keyword = arr[0].lower()

            # get the parser function
            try:
                func = getattr(this_module, 'config_%s' % keyword)
            except AttributeError:
                stderr("%s:%d: unknown keyword '%s'" % (configfile, lineno,
                                                        keyword))
                errors += 1
                continue

            errors += func(arr, configfile, lineno)

    return errors


def check_definition(keyword, configfile, lineno):
    # type: (str, str, int) -> bool
    '''check whether a param was not defined earlier
    Returns False on error, True if OK
    '''

    if keyword in SYMBOLS:
        stderr("%s:%d: redefinition of '%s'" % (configfile, lineno, keyword))
        stderr("%s: previous definition was here" % SYMBOLS[keyword].origin())
        return False

    SYMBOLS[keyword] = Symbol(keyword, configfile, lineno)
    return True


def check_node_definition(node, configfile, lineno):
    # type: (str, str, int) -> bool
    '''check whether a node was not defined earlier
    Returns False on error, True if OK
    '''

    key = 'node %s' % node

    if key in SYMBOLS:
        stderr("%s:%d: redefinition of node '%s'" % (configfile, lineno,
                                                     node))
        stderr("%s: previous definition was here" % SYMBOLS[key].origin())
        return False

    SYMBOLS[key] = Symbol(node, configfile, lineno)
    return True


def check_group_definition(group, configfile, lineno):
    # type: (str, str, int) -> bool
    '''check whether a group was not defined earlier
    Returns False on error, True if OK
    '''

    key = 'group %s' % group

    if key in SYMBOLS:
        stderr("%s:%d: redefinition of group '%s'" % (configfile, lineno,
                                                      group))
        stderr("%s: previous definition was here" % SYMBOLS[key].origin())
        return False

    SYMBOLS[key] = Symbol(group, configfile, lineno)
    return True


#
# config functions return the number of errors in the line
# This enables the 'include' keyword to return more than 1 error
#

def _config_boolean(label, value, configfile, lineno):
    # type: (str, str, str, int) -> Tuple[int, bool]
    '''a boolean parameter can be "true|false|yes|no|on|off|1|0"'''

    if not check_definition(label, configfile, lineno):
        return 1, False

    value = value.lower()
    if value in param.BOOLEAN_VALUE_TRUE:
        return 0, True

    if value in param.BOOLEAN_VALUE_FALSE:
        return 0, False

    stderr('%s:%d: invalid argument for %s' % (configfile, lineno, label))
    return 1, False


def _config_integer(label, value, configfile, lineno, radix=10):
    # type: (str, str, str, int, int) -> Tuple[int, int]
    '''get numeric integer value'''

    if not check_definition(label, configfile, lineno):
        return 1, 0

    try:
        nvalue = int(value, radix)
    except ValueError:
        stderr('%s:%d: invalid argument for %s' % (configfile, lineno, label))
        return 1, 0

    return 0, nvalue


def _config_color_variant(label, value, configfile, lineno):
    # type: (str, str, str, int) -> int
    '''set a color by name'''

    if not check_definition(label, configfile, lineno):
        return 1

    value = value.lower()
    if value in synctool.lib.COLORMAP:
        param.TERSE_COLORS[label[6:]] = value
        return 0

    stderr('%s:%d: invalid argument for %s' % (configfile, lineno, label))
    return 1


def _config_command(label, arr, short_cmd, configfile, lineno):
    # type: (str, List[str], str, str, int) -> Tuple[int, str]
    '''helper for configuring rsync_cmd, ssh_cmd, synctool_cmd, etc.'''

    if not check_definition(label, configfile, lineno):
        return 1, None

    if len(arr) < 2:
        stderr("%s:%d: '%s' requires an argument: "
               "the '%s' command, and any appropriate switches" %
               (configfile, lineno, label, short_cmd))
        return 1, None

    # This function does not check the existence of the command
    # That is deferred until later; the client only runs diff_cmd,
    # while the master runs a bunch of commands

    return 0, synctool.lib.prepare_path(' '.join(arr[1:]))


def spellcheck(name):
    # type: (str) -> bool
    '''Check for valid spelling of name
    Returns True if OK, False if not OK
    '''

    mfound = SPELLCHECK.match(name)
    if not mfound:
        return False

    if mfound.group(0) != name:
        return False

    return True


def config_include(arr, _configfile, _lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: include'''

    # recursively read the given config file
    return read_config_file(synctool.lib.prepare_path(arr[1]))


def config_tempdir(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: tempdir'''

    if not check_definition(arr[0], configfile, lineno):
        return 1

    dirpath = ' '.join(arr[1:])
    dirpath = synctool.lib.prepare_path(dirpath)

    if not os.path.isabs(dirpath):
        stderr("%s:%d: tempdir must be an absolute path" % (configfile,
                                                            lineno))
        return 1

    param.TEMP_DIR = dirpath
    return 0


def config_package_manager(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: package_manager'''

    if len(arr) < 2:
        stderr("%s:%d: 'package_manager' requires an argument" %
               (configfile, lineno))
        return 1

    if not check_definition(arr[0], configfile, lineno):
        return 1

    if arr[1] not in param.KNOWN_PACKAGE_MANAGERS:
        stderr("%s:%d: unknown or unsupported package manager '%s'" %
               (configfile, lineno, arr[1]))
        return 1

    param.PACKAGE_MANAGER = arr[1]
    return 0


def config_ssh_control_persist(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ssh_control_persist'''

    if len(arr) != 2:
        stderr("%s:%d: 'ssh_control_persist' requires a single argument" %
               (configfile, lineno))
        return 1

    persist = arr[1].lower()

    matchp = PERSIST_TIME.match(persist)
    if not matchp:
        stderr("%s:%d: invalid value '%s'" % (configfile, lineno, persist))
        return 1

    param.CONTROL_PERSIST = persist
    return 0


def config_require_extension(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: require_extension'''

    err, param.REQUIRE_EXTENSION = _config_boolean('require_extension',
                                                   arr[1], configfile, lineno)
    return err


def config_full_path(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: full_path'''

    err, param.FULL_PATH = _config_boolean('full_path', arr[1], configfile,
                                           lineno)
    return err


def config_backup_copies(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: backup_copies'''

    err, param.BACKUP_COPIES = _config_boolean('backup_copies', arr[1],
                                               configfile, lineno)
    return err


def config_syslogging(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: syslogging'''

    err, param.SYSLOGGING = _config_boolean('syslogging', arr[1], configfile,
                                            lineno)
    return err

def config_sync_times(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: sync_times'''

    err, param.SYNC_TIMES = _config_boolean('sync_times', arr[1], configfile,
                                            lineno)
    return err

def config_ignore_dotfiles(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ignore_dotfiles'''

    err, param.IGNORE_DOTFILES = _config_boolean('ignore_dotfiles', arr[1],
                                                 configfile, lineno)
    return err


def config_ignore_dotdirs(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ignore_dotdirs'''

    err, param.IGNORE_DOTDIRS = _config_boolean('ignore_dotdirs', arr[1],
                                                configfile, lineno)
    return err


def config_ignore(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ignore'''

    if len(arr) < 2:
        stderr("%s:%d: 'ignore' requires at least 1 argument: "
               "the file or directory to ignore" % (configfile, lineno))
        return 1

    for filenam in arr[1:]:
        # if filenam has wildcards, put it in array IGNORE_FILES_WITH_WILDCARDS
        if (filenam.find('*') >= 0 or filenam.find('?') >= 0 or
                (filenam.find('[') >= 0 and filenam.find(']') >= 0)):
            if filenam not in param.IGNORE_FILES_WITH_WILDCARDS:
                param.IGNORE_FILES_WITH_WILDCARDS.append(filenam)
        else:
            # no wildcards, do a regular ignore
            param.IGNORE_FILES.add(filenam)

    return 0


def config_terse(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: terse'''

    err, param.TERSE = _config_boolean('terse', arr[1], configfile, lineno)
    return err


def config_colorize(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: colorize'''

    err, param.COLORIZE = _config_boolean('colorize', arr[1], configfile,
                                          lineno)
    return err


def config_colorize_full_line(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: colorize_full_line'''

    err, param.COLORIZE_FULL_LINE = _config_boolean('colorize_full_line',
                                                    arr[1], configfile,
                                                    lineno)
    return err


# nice for typo's
def config_colorize_full_lines(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: colorize_full_lines'''

    err, param.COLORIZE_FULL_LINE = _config_boolean('colorize_full_line',
                                                    arr[1], configfile,
                                                    lineno)
    return err


def config_colorize_bright(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: colorize_bright'''

    err, param.COLORIZE_BRIGHT = _config_boolean('colorize_bright', arr[1],
                                                 configfile, lineno)
    return err


def config_colorize_bold(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: colorize_bold'''

    err, param.COLORIZE_BRIGHT = _config_boolean('colorize_bold', arr[1],
                                                 configfile, lineno)
    return err


def config_color_info(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_info'''

    return _config_color_variant('color_info', arr[1], configfile, lineno)


def config_color_warn(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_warn'''

    return _config_color_variant('color_warn', arr[1], configfile, lineno)


def config_color_error(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_error'''

    return _config_color_variant('color_error', arr[1], configfile, lineno)


def config_color_fail(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_fail'''

    return _config_color_variant('color_fail', arr[1], configfile, lineno)


def config_color_sync(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_sync'''

    return _config_color_variant('color_sync', arr[1], configfile, lineno)


def config_color_link(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_link'''

    return _config_color_variant('color_link', arr[1], configfile, lineno)


def config_color_mkdir(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_mkdir'''

    return _config_color_variant('color_mkdir', arr[1], configfile, lineno)


def config_color_rm(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_rm'''

    return _config_color_variant('color_rm', arr[1], configfile, lineno)


def config_color_chown(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_chown'''

    return _config_color_variant('color_chown', arr[1], configfile, lineno)


def config_color_chmod(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_chmod'''

    return _config_color_variant('color_chmod', arr[1], configfile, lineno)


def config_color_exec(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_exec'''

    return _config_color_variant('color_exec', arr[1], configfile, lineno)


def config_color_upload(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_upload'''

    return _config_color_variant('color_upload', arr[1], configfile, lineno)


def config_color_new(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_new'''

    return _config_color_variant('color_new', arr[1], configfile, lineno)


def config_color_type(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_type'''

    return _config_color_variant('color_type', arr[1], configfile, lineno)


def config_color_dryrun(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_dryrun'''

    return _config_color_variant('color_dryrun', arr[1], configfile, lineno)


def config_color_fixing(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_fixing'''

    return _config_color_variant('color_fixing', arr[1], configfile, lineno)


def config_color_ok(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: color_ok'''

    return _config_color_variant('color_ok', arr[1], configfile, lineno)


def config_default_nodeset(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: default_nodeset'''

    if not check_definition(arr[0], configfile, lineno):
        return 1

    if len(arr) < 2:
        stderr("%s:%d: 'default_nodeset' requires an argument" %
               (configfile, lineno))
        return 1

    param.DEFAULT_NODESET = set()

    for elem in arr[1:]:
        if '[' in elem:
            try:
                for expanded in synctool.range.expand(elem):
                    if '[' in expanded:
                        raise RuntimeError("bug: expanded range contains "
                                           "'[' character")

                    param.DEFAULT_NODESET.add(expanded)
            except synctool.range.RangeSyntaxError as err:
                stderr("%s:%d: %s" % (configfile, lineno, err))
                return 1

        else:
            if not spellcheck(elem):
                stderr("%s:%d: invalid name '%s'" % (configfile, lineno,
                                                     elem))
                return 1

            if elem == 'none':
                param.DEFAULT_NODESET = set()
            else:
                param.DEFAULT_NODESET.add(elem)

    # for now, accept this as the default nodeset
    # There can be compound groups in it, so
    # synctool_config.read_config() will expand it to a list of nodes
    return 0


def config_master(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: master'''

    if len(arr) != 2:
        stderr("%s:%d: 'master' requires one argument: the hostname" %
               (configfile, lineno))
        return 1

    param.MASTER = arr[1]
    return 0


def config_slave(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: slave'''

    if len(arr) < 2:
        stderr("%s:%d: 'slave' requires at least one argument: a nodename" %
               (configfile, lineno))
        return 1

    for node in arr[1:]:
        # range expression syntax: 'node generator'
        if '[' in node:
            try:
                for expanded_node in synctool.range.expand(node):
                    if '[' in expanded_node:
                        raise RuntimeError("bug: expanded range contains "
                                           "'[' character")

                    expanded_arr = ['slave', expanded_node]
                    # recurse
                    if config_slave(expanded_arr, configfile, lineno) != 0:
                        return 1
            except synctool.range.RangeSyntaxError as err:
                stderr("%s:%d: %s" % (configfile, lineno, err))
                return 1

            return 0

        if not spellcheck(node):
            stderr("%s:%d: invalid node name '%s'" %
                   (configfile, lineno, node))
            return 1

        SYMBOLS['node %s' % node] = Symbol(node, configfile, lineno)
        param.SLAVES.add(node)

    # check for valid nodes is made later
    return 0


def config_group(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: group'''

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

    if group in ('all', 'none', 'template'):
        stderr("%s:%d: implicit group '%s' can not be redefined" %
               (configfile, lineno, group))
        return 1

    if not check_group_definition(group, configfile, lineno):
        return 1

    key = 'node %s' % group
    if key in SYMBOLS:
        stderr('%s:%d: %s was previously defined as a node' % (configfile,
                                                               lineno, group))
        stderr('%s: previous definition was here' % SYMBOLS[key].origin())
        return 1

    grouplist = []          # type: List[str]
    for grp in arr[2:]:
        # range expression syntax: 'group generator'
        if '[' in grp:
            try:
                grouplist.extend(synctool.range.expand(grp))
            except synctool.range.RangeSyntaxError as err:
                stderr("%s:%d: %s" % (configfile, lineno, err))
                return 1
        else:
            grouplist.append(grp)

    try:
        param.GROUP_DEFS[group] = expand_grouplist(grouplist)
    except RuntimeError:
        stderr('%s:%d: compound groups can not contain node names' %
               (configfile, lineno))
        return 1

    return 0


def config_node(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: node'''

    if len(arr) < 2:
        stderr("%s:%d: 'node' requires at least 1 argument: the nodename" %
               (configfile, lineno))
        return 1

    node = arr[1]

    # range expression syntax: 'node generator'
    if '[' in node:
        # setup automatic numbering of IP adresses
        synctool.range.reset_sequence()
        try:
            for expanded_node in synctool.range.expand(node):
                if '[' in expanded_node:
                    raise RuntimeError("bug: expanded range contains "
                                       "'[' character")
                expanded_arr = arr[:]
                expanded_arr[1] = expanded_node
                # recurse
                if config_node(expanded_arr, configfile, lineno) != 0:
                    synctool.range.reset_sequence()
                    return 1
        except synctool.range.RangeSyntaxError as err:
            stderr("%s:%d: %s" % (configfile, lineno, err))
            synctool.range.reset_sequence()
            return 1

        synctool.range.reset_sequence()
        return 0

    if not spellcheck(node):
        stderr("%s:%d: invalid node name '%s'" % (configfile, lineno, node))
        return 1

    groups = arr[2:]

    if not check_node_definition(node, configfile, lineno):
        # error message already printed
        return 1

    key = 'group %s' % node
    if key in SYMBOLS:
        stderr('%s:%d: %s was previously defined as a group' %
               (configfile, lineno, node))
        stderr('%s: previous definition was here' % SYMBOLS[key].origin())
        return 1

    # grouplist will be the list of groups for this node
    grouplist = []

    # examine groups and list of node specifiers
    for group in groups:
        if ':' in group:
            # it's a node specifier
            if not _node_specifier(configfile, lineno, node, group):
                return 1

            continue

        if group == 'all':
            stderr("%s:%d: illegal to use group 'all' in node definition" %
                   (configfile, lineno))
            stderr("%s:%d: group 'all' automatically applies to all nodes" %
                   (configfile, lineno))
            return 1

        if group == 'none':
            stderr("%s:%d: illegal to use group 'none' in node definition" %
                   (configfile, lineno))
            stderr("%s:%d: use 'ignore_node' to disable a node" %
                   (configfile, lineno))
            return 1

        if group == 'template':
            stderr("%s:%d: illegal to use group 'template' "
                   "in node definition" % (configfile, lineno))
            stderr("%s:%d: file extension _template is reserved for "
                   "template files" % (configfile, lineno))
            return 1

        if group == node:
            stderr("%s:%d: illegal to list '%s' as group for node %s" %
                   (configfile, lineno, node, node))
            return 1

        if not spellcheck(group):
            stderr("%s:%d: invalid group name '%s'" % (configfile, lineno,
                                                       group))
            return 1

        # it looks like a good group
        grouplist.append(group)

    try:
        param.NODES[node] = expand_grouplist(grouplist)
    except RuntimeError:
        stderr('%s:%d: a group list can not contain node names' %
               (configfile, lineno))
        return 1

    return 0


def _node_specifier(configfile, lineno, node, spec):
    # type: (str, int, str, str) -> bool
    '''parse optional node specifiers like 'ipaddress:', 'rsync:' etc.
    Returns True if OK, False on error
    '''

    specifier, arg = spec.split(':', 1)
    if not specifier or not arg:
        stderr("%s:%d: syntax error in node specifier '%s'" %
               (configfile, lineno, spec))
        return False

    # got specifier, arg

    if specifier == 'ipaddress':
        if node in param.IPADDRESSES:
            stderr('%s:%d: redefinition of IP address for node %s' %
                   (configfile, lineno, node))
            return False

        # support IP address sequence syntax
        try:
            param.IPADDRESSES[node] = \
                synctool.range.expand_sequence(arg)
        except synctool.range.RangeSyntaxError as err:
            stderr('%s:%d: %s' % (configfile, lineno, err))
            return False

    elif specifier == 'rsync':
        if arg == 'yes':
            pass
        elif arg == 'no':
            param.NO_RSYNC.add(node)
        else:
            stderr("%s:%d: node specifier 'rsync' can have value "
                   "'yes' or 'no'" % (configfile, lineno))
            return False

    elif specifier in ('hostname', 'hostid'):
        stderr("%s:%d: node specifier '%s:' is deprecated" %
               (configfile, lineno, specifier))

    else:
        stderr('%s:%d: unknown node specifier %s' %
               (configfile, lineno, specifier))
        return False

    return True


def config_ignore_node(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ignore_node'''

    if len(arr) < 2:
        stderr("%s:%d: 'ignore_node' requires 1 argument: "
               "the nodename to ignore" % (configfile, lineno))
        return 1

    errors = 0

    for node in arr[1:]:
        # range expression syntax: 'node generator'
        if '[' in node:
            try:
                for expanded_node in synctool.range.expand(node):
                    if '[' in expanded_node:
                        raise RuntimeError("bug: expanded range contains "
                                           "'[' character")

                    expanded_arr = ['ignore_node', expanded_node]
                    # recurse
                    if config_ignore_node(expanded_arr, configfile,
                                          lineno) != 0:
                        return 1
            except synctool.range.RangeSyntaxError as err:
                stderr("%s:%d: %s" % (configfile, lineno, err))
                return 1

            return 0

        if not spellcheck(node):
            stderr("%s:%d: invalid node name '%s'" % (configfile, lineno,
                                                      node))
            errors += 1
            continue

        if node == 'none':
            continue

        if node in ('all', 'template'):
            stderr("%s:%d: illegal to ignore '%s'" % (configfile, lineno,
                                                      node))
            errors += 1
            continue

        param.IGNORE_GROUPS.add(node)

    return errors


def config_ignore_group(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ignore_group'''

    if len(arr) < 2:
        stderr("%s:%d: '%s' requires 1 argument: the groupname to ignore" %
               (configfile, lineno, arr[0]))
        return 1

    errors = 0

    for group in arr[1:]:
        # range expression syntax: 'group generator'
        if '[' in group:
            try:
                for expanded_group in synctool.range.expand(group):
                    if '[' in expanded_group:
                        raise RuntimeError("bug: expanded range contains "
                                           "'[' character")

                    expanded_arr = ['ignore_group', expanded_group]
                    # recurse
                    if config_ignore_group(expanded_arr, configfile,
                                           lineno) != 0:
                        return 1
            except synctool.range.RangeSyntaxError as err:
                stderr("%s:%d: %s" % (configfile, lineno, err))
                return 1

            return 0

        if not spellcheck(group):
            stderr("%s:%d: invalid group name '%s'" % (configfile, lineno,
                                                       group))
            errors += 1
            continue

        if group == 'none':
            continue

        if group in ('all', 'template'):
            stderr("%s:%d: illegal to ignore '%s'" % (configfile, lineno,
                                                      group))
            errors += 1
            continue

        param.IGNORE_GROUPS.add(group)

        # add any (yet) unknown group names to the group_defs dict
        if group not in param.GROUP_DEFS:
            param.GROUP_DEFS[group] = None

    return errors


def config_diff_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: diff_cmd'''

    err, param.DIFF_CMD = _config_command('diff_cmd', arr, 'diff', configfile,
                                          lineno)
    return err


def config_ping_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ping_cmd'''

    err, param.PING_CMD = _config_command('ping_cmd', arr, 'ping', configfile,
                                          lineno)
    return err


def config_ssh_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: ssh_cmd'''

    err, param.SSH_CMD = _config_command('ssh_cmd', arr, 'ssh', configfile,
                                         lineno)
    return err


def config_rsync_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: rsync_cmd'''

    # Note! strip_multiple_slashes() will break "rsync://" paths
    # and strip_trailing_slashes() may break rsync paths
    # but these are usually not used in rsync_cmd

    err, param.RSYNC_CMD = _config_command('rsync_cmd', arr, 'rsync',
                                           configfile, lineno)
    return err


def config_synctool_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: synctool_cmd'''

    err, param.SYNCTOOL_CMD = _config_command('synctool_cmd', arr,
                                              'synctool.py', configfile,
                                              lineno)
    return err


def config_pkg_cmd(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: pkg_cmd'''

    err, param.PKG_CMD = _config_command('pkg_cmd', arr, 'synctool_pkg.py',
                                         configfile, lineno)
    return err


def config_num_proc(arr, configfile, lineno):
    # type: (List[str], str, int) -> int
    '''parse keyword: num_proc'''

    err, param.NUM_PROC = _config_integer('num_proc', arr[1], configfile,
                                          lineno)

    if not err and param.NUM_PROC < 1:
        stderr("%s:%d: invalid argument for num_proc" % (configfile, lineno))
        return 1

    return err


def expand_grouplist(grouplist):
    # type: (List[str]) -> List[str]
    '''expand a list of (compound) groups recursively
    Returns the expanded group list
    '''

    groups = []

    for elem in grouplist:
        groups.append(elem)

        if elem in param.GROUP_DEFS:
            compound_groups = param.GROUP_DEFS[elem]

            # mind that GROUP_DEFS[group] can be None
            # for any groups that have no subgroups
            if compound_groups is not None:
                groups.extend(compound_groups)
        else:
            # node names are treated as groups too ...
            # but they are special groups, and can not be in a compound group
            # just to prevent odd things from happening
            if elem in param.NODES:
                raise RuntimeError('node %s can not be part of '
                                   'compound group list' % elem)

            param.GROUP_DEFS[elem] = None

    # remove duplicates
    # this looks pretty lame ... but Python sets are not usable here;
    # sets have no order and order is important here

    expanded_grouplist = []     # type: List[str]
    for elem in groups:
        if elem not in expanded_grouplist:
            expanded_grouplist.append(elem)

    return expanded_grouplist

# EOB
