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
  call synctool.config.read_config()
  call nodeset.addresses(), which will return a list of addresses
  use the address list to contact the nodes
  use nodeset.get_nodename_from_address() to get a nodename
'''

import sys

import synctool.config
import synctool.lib
from synctool.lib import verbose, stderr, warning
import synctool.param
import synctool.range


class NodeSet(object):
    '''class representing a set of nodes
    Some methods may throw RangeSyntaxError when parsing range expressions
    '''

    def __init__(self):
        '''initialize instance'''

        self.nodelist = set()
        self.grouplist = set()
        self.exclude_nodes = set()
        self.exclude_groups = set()
        self.namemap = {}

    def add_node(self, nodelist):
        '''add a node to the nodeset'''

#        self.nodelist = set()
        for node in synctool.range.split_nodelist(nodelist):
            if '[' in node:
                self.nodelist |= set(synctool.range.expand(node))
            else:
                self.nodelist.add(node)

    def add_group(self, grouplist):
        '''add a group to the nodeset'''

#        self.grouplist = set()
        for group in synctool.range.split_nodelist(grouplist):
            if '[' in group:
                self.grouplist |= set(synctool.range.expand(group))
            else:
                self.grouplist.add(group)

    def exclude_node(self, nodelist):
        '''remove a node from the nodeset'''

#        self.exclude_nodes = set()
        for node in synctool.range.split_nodelist(nodelist):
            if '[' in node:
                self.exclude_nodes |= set(synctool.range.expand(node))
            else:
                self.exclude_nodes.add(node)

    def exclude_group(self, grouplist):
        '''remove a group from the nodeset'''

#        self.exclude_groups = set()
        for group in synctool.range.split_nodelist(grouplist):
            if '[' in group:
                self.exclude_groups |= set(synctool.range.expand(group))
            else:
                self.exclude_groups.add(group)

    def addresses(self, silent=False):
        '''return list of addresses of relevant nodes'''

        # by default, work on default_nodeset
        if not self.nodelist and not self.grouplist:
            if not synctool.param.DEFAULT_NODESET:
                return []

            self.nodelist = synctool.param.DEFAULT_NODESET

        # check if the nodes exist at all
        # the user may have given bogus names
        all_nodes = set(synctool.config.get_all_nodes())
        unknown = (self.nodelist | self.exclude_nodes) - all_nodes
        if len(unknown) > 0:
            # it's nice to display "the first" unknown node
            # (at least, for numbered nodes)
            arr = list(unknown)
            arr.sort()
            stderr("no such node '%s'" % arr[0])
            return None

        # check if the groups exist at all
        unknown = ((self.grouplist | self.exclude_groups) -
                   synctool.param.ALL_GROUPS)
        for group in unknown:
            stderr("no such group '%s'" % group)
            return None

        self.nodelist |= synctool.config.get_nodes_in_groups(self.grouplist)

        self.exclude_nodes |= synctool.config.get_nodes_in_groups(
                                self.exclude_groups)

        # remove excluded nodes from nodelist
        self.nodelist -= self.exclude_nodes

        if not self.nodelist:
            return []

        addrs = []

        ignored_nodes = self.nodelist & synctool.param.IGNORE_GROUPS
        self.nodelist -= ignored_nodes

        for node in self.nodelist:
            # ignoring a group results in also ignoring the node
            my_groups = set(synctool.config.get_groups(node))
            my_groups &= synctool.param.IGNORE_GROUPS
            if len(my_groups) > 0:
                verbose('node %s is ignored due to an ignored group' % node)
                ignored_nodes.add(node)
                continue

            addr = synctool.config.get_node_ipaddress(node)
            self.namemap[addr] = node

            if not addr in addrs:    # make sure we do not have duplicates
                addrs.append(addr)

        # print message about ignored nodes
        if not silent and len(ignored_nodes) > 0 and not synctool.lib.QUIET:
            if synctool.param.TERSE:
                synctool.lib.terse(synctool.lib.TERSE_WARNING,
                                   'ignored nodes')
            else:
                arr = list(ignored_nodes)
                arr.sort()
                ignored_str = ('ignored: ' + synctool.range.compress(arr))
                if len(ignored_str) < 70:
                    warning(ignored_str)
                else:
                    warning('some nodes are ignored')
                    if synctool.lib.VERBOSE:
                        for node in ignored_nodes:
                            verbose('ignored: %s' % node)

        return addrs

    def get_nodename_from_address(self, addr):
        '''map the address back to a nodename'''

        if addr in self.namemap:
            return self.namemap[addr]

        return addr


def make_default_nodeset():
    '''take the (temporary) DEFAULT_NODESET and expand it to
    the definitive DEFAULT_NODESET
    Return value: none, exit the program on error
    '''

    # Note: this function is called by synctool.config.read_config()

    temp_set = synctool.param.DEFAULT_NODESET
    synctool.param.DEFAULT_NODESET = set()
    nodeset = NodeSet()
    errors = 0
    for elem in temp_set:
        if elem in synctool.param.NODES:
            nodeset.add_node(elem)
        elif elem in synctool.param.ALL_GROUPS:
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
            synctool.param.DEFAULT_NODESET = nodeset.nodelist

    if errors > 0:
        sys.exit(-1)

# EOB
