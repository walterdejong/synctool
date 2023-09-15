#pylint: disable=consider-using-f-string
#
#   synctool.nodeset.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''The nodeset helps making a set of nodes from command-line arguments
It is used by synctool-master, dsh, dcp, dsh-ping and fully supports
node range expressions

usage:
  first make an instance of NodeSet
  then add nodes, groups, excluded nodes/groups
  call config.read_config()
  call nodeset.addresses(), which will return a list of addresses
  use the address list to contact the nodes
  use nodeset.get_nodename_from_address() to get a nodename
'''

import sys

try:
    from typing import List, Dict, Set
except ImportError:
    pass

from synctool import config, param
import synctool.lib
from synctool.lib import verbose, stderr, warning
import synctool.range


class NodeSet:
    '''class representing a set of nodes
    Some methods may throw RangeSyntaxError when parsing range expressions
    '''

    def __init__(self):
        # type: () -> None
        '''initialize instance'''

        self.nodelist = set()       # type: Set[str]
        self.grouplist = set()      # type: Set[str]
        self.exclude_nodes = set()  # type: Set[str]
        self.exclude_groups = set() # type: Set[str]
        self.namemap = {}           # type: Dict[str, str]

    def add_node(self, nodelist):
        # type: (str) -> None
        '''add a node to the nodeset'''

#        self.nodelist = set()
        for node in synctool.range.split_nodelist(nodelist):
            if '[' in node:
                self.nodelist |= set(synctool.range.expand(node))
            else:
                self.nodelist.add(node)

    def add_group(self, grouplist):
        # type: (str) -> None
        '''add a group to the nodeset'''

#        self.grouplist = set()
        for group in synctool.range.split_nodelist(grouplist):
            if '[' in group:
                self.grouplist |= set(synctool.range.expand(group))
            else:
                self.grouplist.add(group)

    def exclude_node(self, nodelist):
        # type: (str) -> None
        '''remove a node from the nodeset'''

#        self.exclude_nodes = set()
        for node in synctool.range.split_nodelist(nodelist):
            if '[' in node:
                self.exclude_nodes |= set(synctool.range.expand(node))
            else:
                self.exclude_nodes.add(node)

    def exclude_group(self, grouplist):
        # type: (str) -> None
        '''remove a group from the nodeset'''

#        self.exclude_groups = set()
        for group in synctool.range.split_nodelist(grouplist):
            if '[' in group:
                self.exclude_groups |= set(synctool.range.expand(group))
            else:
                self.exclude_groups.add(group)

    def addresses(self, silent=False):
#pylint: disable=too-many-branches
        # type: (bool) -> List[str]
        '''return list of addresses of relevant nodes'''

        # by default, work on default_nodeset
        if not self.nodelist and not self.grouplist:
            if not param.DEFAULT_NODESET:
                return []

            self.nodelist = param.DEFAULT_NODESET

        # check if the nodes exist at all
        # the user may have given bogus names
        all_nodes = set(config.get_all_nodes())
        unknown = (self.nodelist | self.exclude_nodes) - all_nodes
        if unknown:
            # it's nice to display "the first" unknown node
            # (at least, for numbered nodes)
            arr = list(unknown)
            arr.sort()
            stderr("no such node '%s'" % arr[0])
            return None

        # check if the groups exist at all
        unknown = ((self.grouplist | self.exclude_groups) -
                   param.ALL_GROUPS)
        for group in unknown:
            stderr("no such group '%s'" % group)
            return None

        self.nodelist |= config.get_nodes_in_groups(self.grouplist)
        self.exclude_nodes |= config.get_nodes_in_groups(self.exclude_groups)
        # remove excluded nodes from nodelist
        self.nodelist -= self.exclude_nodes

        if not self.nodelist:
            return []

        addrs = []  # type: List[str]

        ignored_nodes = self.nodelist & param.IGNORE_GROUPS
        self.nodelist -= ignored_nodes

        for node in self.nodelist:
            # ignoring a group results in also ignoring the node
            my_groups = set(config.get_groups(node))
            my_groups &= param.IGNORE_GROUPS
            if my_groups:
                verbose('node %s is ignored due to an ignored group' % node)
                ignored_nodes.add(node)
                continue

            addr = config.get_node_ipaddress(node)
            self.namemap[addr] = node

            # make sure we do not have duplicates
            if addr not in addrs:
                addrs.append(addr)

        # print message about ignored nodes
        if not silent and ignored_nodes and not synctool.lib.QUIET:
            if param.TERSE:
                synctool.lib.terse(synctool.lib.TERSE_WARNING,
                                   'ignored nodes')
            else:
                arr = list(ignored_nodes)
                arr.sort()
                ignored_str = 'ignored: ' + synctool.range.compress(arr)
                if len(ignored_str) < 70:
                    warning(ignored_str)
                else:
                    warning('some nodes are ignored')
                    if synctool.lib.VERBOSE:
                        for node in ignored_nodes:
                            verbose('ignored: %s' % node)

        return addrs

    def get_nodename_from_address(self, addr):
        # type: (str) -> str
        '''map the address back to a nodename'''

        if addr in self.namemap:
            return self.namemap[addr]

        return addr


def make_default_nodeset():
    # type: () -> None
    '''take the (temporary) DEFAULT_NODESET and expand it to
    the definitive DEFAULT_NODESET
    Return value: none, exit the program on error
    '''

    # Note: this function is called by config.read_config()

    temp_set = param.DEFAULT_NODESET
    param.DEFAULT_NODESET = set()
    nodeset = NodeSet()
    errors = 0
    for elem in temp_set:
        if elem in param.NODES:
            nodeset.add_node(elem)
        elif elem in param.ALL_GROUPS:
            nodeset.add_group(elem)
        else:
            stderr("config error: unknown node or group '%s' "
                   "in default_nodeset" % elem)
            errors += 1

    if not errors:
        if not nodeset.addresses(silent=True):
            # Note: silent=True suppresses warnings about ignored nodes
            # error message already printed
            errors += 1
        else:
            param.DEFAULT_NODESET = nodeset.nodelist

    if errors > 0:
        sys.exit(-1)

# EOB
