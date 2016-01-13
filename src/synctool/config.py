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
        if node not in synctool.param.NODES:
            error("slave '%s': no such node" % node)
            errors += 1

    # implicitly add group 'all'
    if 'all' not in synctool.param.GROUP_DEFS:
        synctool.param.GROUP_DEFS['all'] = None

    # implicitly add 'nodename' as first group
    # implicitly add 'all' as last group
    for node in get_all_nodes():
        insert_group(node, node)
        synctool.param.NODES[node].append('all')

    # implicitly add group 'none'
    if 'none' not in synctool.param.GROUP_DEFS:
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

    # The nodename is determined by the master in synctool.conf
    # The master tells the client what its nodename is
    # If the user runs synctool-client in stand-alone mode on a node
    # then we need to detect what node that is
    # The best way of identifying a node is by its IP address
    # This fails when a host is multi-homed and the FQDN is not
    # listed as 'ipaddress:' in synctool.conf
    # synctool makes no further assumptions about the nodename

    # get my hostname
    synctool.param.HOSTNAME = hostname = socket.getfqdn()

    nodename = synctool.param.NODENAME
    if nodename is None:
        # try to find out who am I
        all_nodes = get_all_nodes()

        ipaddresses = get_ipaddresses(hostname)
        if ipaddresses is not None:
            # try find a node that lists any of our IP addresses
            for node in all_nodes:
                if node in synctool.param.IPADDRESSES:
                    addr = synctool.param.IPADDRESSES[node]
                else:
                    # unknown (explicit) IP address for node
                    continue

                addrs = get_ipaddresses(addr)
                if addrs is None:
                    continue

                found = False
                for addr in addrs:
                    if addr in ipaddresses:
                        nodename = node
                        found = True
                        break

                if found:
                    break

    # At this point, nodename can still be None
    # It only really matters for client.py, which checks this condition
    # Note that synctool-client does _not_ use the short hostname to
    # identify the node it is running on

    synctool.param.NODENAME = nodename
    synctool.param.MY_GROUPS = get_my_groups()


def get_ipaddresses(name):
    '''Returns list of IP addresses for DNS name
    or None on error
    '''

    try:
        addrinfo = socket.getaddrinfo(name, None)
    except socket.gaierror:
        return None

    if addrinfo is None or len(addrinfo) < 1:
        return []

    ipaddresses = set([])

    # address info is a list of tuples:
    # [(family, socktype, proto, canonname, sockaddr), ]
    # sockaddr is a tuple (address, port) for IPv4
    # or a tuple for IPv6 (address, port, flow, scope)
    for tup in addrinfo:
        sockaddr = tup[4]
        ipaddresses.add(sockaddr[0])

    return list(ipaddresses)


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
