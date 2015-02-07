#
#   synctool.config.py    WJ109
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''functions that extract variables from configuration
It's not the config parser ... that code is in module configparser
'''

import os
import sys
import socket

import synctool.configparser
import synctool.lib
from synctool.lib import stderr, error
import synctool.param


def read_config():
    '''read the config file and set a bunch of globals
    Return value: none, exit the program on error
    '''

    if not os.path.isfile(synctool.param.CONF_FILE):
        stderr("no such config file '%s'" % synctool.param.CONF_FILE)
        sys.exit(-1)

    errors = synctool.configparser.read_config_file(synctool.param.CONF_FILE)

    # overlay/ and delete/ must be under ROOTDIR
    if not os.path.isdir(synctool.param.OVERLAY_DIR):
        error('no such directory: %s' % synctool.param.OVERLAY_DIR)
        errors += 1

    if not os.path.isdir(synctool.param.DELETE_DIR):
        error('no such directory: %s' % synctool.param.DELETE_DIR)
        errors += 1

    if not os.path.isdir(synctool.param.PURGE_DIR):
        error('no such directory: %s' % synctool.param.PURGE_DIR)
        errors += 1

    if not synctool.param.TEMP_DIR:
        synctool.param.TEMP_DIR = '/tmp/synctool'
        # do not make temp dir here; it is only used on the master node

    # if commands not set, select sensible defaults
    # the existence of the commands is checked later ...
    if not synctool.param.SYNCTOOL_CMD:
        synctool.param.SYNCTOOL_CMD = os.path.join(synctool.param.ROOTDIR,
                                                   'bin', 'synctool-client')

    if not synctool.param.PKG_CMD:
        synctool.param.PKG_CMD = os.path.join(synctool.param.ROOTDIR,
                                              'bin', 'synctool-client-pkg')

    # check master node
    if not synctool.param.MASTER:
        error("'master' is not configured")
        errors += 1

    for node in synctool.param.SLAVES:
        if not node in synctool.param.NODES:
            error("slave '%s': no such node" % node)
            errors += 1

    # implicitly add group 'all'
    if not 'all' in synctool.param.GROUP_DEFS:
        synctool.param.GROUP_DEFS['all'] = None

    # implicitly add 'nodename' as first group
    # implicitly add 'all' as last group
    for node in get_all_nodes():
        insert_group(node, node)
        synctool.param.NODES[node].append('all')

    # implicitly add group 'none'
    if not 'none' in synctool.param.GROUP_DEFS:
        synctool.param.GROUP_DEFS['none'] = None

    synctool.param.IGNORE_GROUPS.add('none')

    # initialize ALL_GROUPS
    synctool.param.ALL_GROUPS = make_all_groups()

    if errors > 0:
        sys.exit(-1)


def check_cmd_config(param_name, cmd):
    '''check whether the command given in the config exists
    Returns (True, full pathed command) when OK,
    and (False, None) on error
    '''

    if not cmd:
        stderr("%s: error: parameter '%s' is missing" %
               (synctool.param.CONF_FILE, param_name))
        return (False, None)

    arr = cmd.split()
    path = synctool.lib.search_path(arr[0])
    if not path:
        stderr("%s: error: %s '%s' not found in PATH" %
               (synctool.param.CONF_FILE, param_name, arr[0]))
        return (False, None)

    # reassemble command with full path
    arr[0] = path
    cmd = ' '.join(arr)
    return (True, cmd)


def init_mynodename():
    '''determine the nodename of the current host
    and initialize MY_GROUPS
    '''

    # In practice, the nodename is determined by the master in synctool.conf
    # The master then tells the client what its nodename is
    # In two special cases, we still need to detect the nodename:
    # 1. user runs synctool.py in stand-alone mode on a node
    # 2. master node itself is being managed by synctool
    #
    # In older versions, the hostname was implicitly treated as a group
    # This is no longer the case

    # get my hostname
    synctool.param.HOSTNAME = hostname = socket.getfqdn()

    arr = hostname.split('.')
    short_hostname = arr[0]

    all_nodes = get_all_nodes()

    nodename = synctool.param.NODENAME
    if nodename != None:
        # nodename was already set
        # the master set it because it already knows the node's nodename
        pass

    elif synctool.param.HOST_ID != None:
        arr = synctool.param.HOST_ID.split('.')
        nodename = arr[0]

    elif hostname in synctool.param.HOSTNAMES:
        nodename = synctool.param.HOSTNAMES[hostname]

    elif short_hostname in synctool.param.HOSTNAMES:
        nodename = synctool.param.HOSTNAMES[short_hostname]

    elif short_hostname in all_nodes:
        nodename = short_hostname

    elif hostname in all_nodes:
        nodename = hostname

    else:
        # try to find a node that has the (short) hostname
        # listed as interface or as a group
        for node in all_nodes:
            addr = get_node_ipaddress(node)
            if addr == short_hostname or addr == hostname:
                nodename = node
                break

            groups = get_groups(node)
            if short_hostname in groups or hostname in groups:
                nodename = node
                break

    # At this point, nodename can still be None
    # It only really matters for synctool.py, which checks this condition

    synctool.param.NODENAME = nodename
    synctool.param.MY_GROUPS = get_my_groups()


def insert_group(node, group):
    '''add group to node definition'''

    if node in synctool.param.NODES:
        if group in synctool.param.NODES[node]:
            # remove the group and reinsert it to make sure it comes first
            synctool.param.NODES[node].remove(group)

        synctool.param.NODES[node].insert(0, group)
    else:
        synctool.param.NODES[node] = [group]


def get_all_nodes():
    '''Returns array with all node names'''

    return synctool.param.NODES.keys()


def get_node_ipaddress(node):
    '''Return IPaddress of node, or node name if unknown'''

    if node in synctool.param.IPADDRESSES:
        return synctool.param.IPADDRESSES[node]

    return node


def get_node_hostname(node):
    '''Return hostname of node, or node name if unknown'''

    if node in synctool.param.HOSTNAMES_BY_NODE:
        return synctool.param.HOSTNAMES_BY_NODE[node]

    return node


def make_all_groups():
    '''make a set of all possible groups
    This is a set of all group names plus all node names
    '''

    s = set(synctool.param.GROUP_DEFS.keys())
    s |= set(synctool.param.NODES.keys())
    return s


def get_groups(nodename):
    '''returns the groups for the node'''

    if nodename in synctool.param.NODES:
        return synctool.param.NODES[nodename]

    return []


def get_my_groups():
    '''returns the groups for this node'''

    if synctool.param.NODENAME in synctool.param.NODES:
        return synctool.param.NODES[synctool.param.NODENAME]

    return []


def get_nodes_in_groups(groups):
    '''returns a set of nodes that are in a set or list of groups'''

    s = set()

    for g in groups:
        for node in synctool.param.NODES.keys():
            # NODES[node] is an ordered list (groups in order of importance)
            # so we can not do neat tricks with combining sets here ...
            if g in synctool.param.NODES[node]:
                s.add(node)

    return s

# EOB
