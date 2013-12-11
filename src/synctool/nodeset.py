#
#    synctool.nodeset.py        WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''The nodeset helps making a set of nodes from command-line arguments
It is used by synctool-master, dsh, dcp, dsh-ping

usage:
  first make an instance of NodeSet
  then add nodes, groups, excluded nodes/groups
  call synctool.config.read_config()
  call nodeset.addresses(), which will return a list of addresses
  use the address list to contact the nodes
  use nodeset.get_nodename_from_address() to get a nodename
'''

import re

import synctool.config
import synctool.lib
from synctool.lib import verbose, stderr
import synctool.param

# a node expression may look like 'node1-[1,2,8-10/2]-mgmt'
# or something somewhat resembling that
# Take make matters worse, a line may have multiple of these
# separated by comma's
# The regex here is not super strict, but it suffices to split a line
SPLIT_EXPR = re.compile(
    r'([a-zA-Z0-9_+-]+\[\d+[0-9,/-]*\][a-zA-Z0-9_+-]*|[a-zA-Z0-9_+-]+)')

# This regex is used to take apart a single node range expression
NODE_EXPR = re.compile(
    r'([a-zA-Z]+[a-zA-Z0-9_+-]*)\[(\d+[0-9,/-]*)\]([a-zA-Z0-9_+-]*)$')


class NodeSet(object):
    '''class representing a set of nodes'''

    def __init__(self):
        self.nodelist = set()
        self.grouplist = set()
        self.exclude_nodes = set()
        self.exclude_groups = set()
        self.namemap = {}

    def add_node(self, nodelist):
        '''add a node to the nodeset'''

        self.nodelist = set()
        for node in split_nodelist(nodelist):
            if '[' in node:
                self.nodelist |= set(expand_expression(node))
            else:
                self.nodelist.add(node)

    def add_group(self, grouplist):
        '''add a group to the nodeset'''

        self.grouplist = set()
        for group in split_nodelist(grouplist):
            if '[' in group:
                self.grouplist |= set(expand_expression(group))
            else:
                self.grouplist.add(group)

    def exclude_node(self, nodelist):
        '''remove a node from the nodeset'''

        self.exclude_nodes = set()
        for node in split_nodelist(nodelist):
            if '[' in node:
                self.exclude_nodes |= set(expand_expression(node))
            else:
                self.exclude_nodes.add(node)

    def exclude_group(self, grouplist):
        '''remove a group from the nodeset'''

        self.exclude_groups = set()
        for group in split_nodelist(grouplist):
            if '[' in group:
                self.exclude_groups |= set(expand_expression(group))
            else:
                self.exclude_groups.add(group)

    def addresses(self):
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
        for node in unknown:
            stderr("no such node '%s'" % node)
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

        if synctool.lib.VERBOSE:
            for node in ignored_nodes:
                verbose('node %s is ignored' % node)

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
        if (len(ignored_nodes) > 0 and not synctool.lib.QUIET and
            not synctool.lib.UNIX_CMD):
            if synctool.param.TERSE:
                synctool.lib.terse(synctool.lib.TERSE_WARNING,
                                   'ignored nodes')
            else:
                ignored_str = ('warning: ignored nodes: ' +
                               ','.join(list(ignored_nodes)))
                if len(ignored_str) < 80:
                    print ignored_str
                else:
                    print 'warning: some nodes are ignored'

        return addrs

    def get_nodename_from_address(self, addr):
        '''map the address back to a nodename'''

        if addr in self.namemap:
            return self.namemap[addr]

        return addr


def split_nodelist(expr):
    '''split a string like 'node1,node2,node[3-6,8,10],node-x'
    Returns the array of elements'''

    arr = []

    # SPLIT_EXPR is a global compiled regex for splitting node expr lines
    for elem in SPLIT_EXPR.split(expr):
        if not elem:
            continue

        if elem == ',':
            continue

        if not SPLIT_EXPR.match(elem):
            # FIXME raise SyntaxError
            raise RuntimeError('syntax error')

        arr.append(elem)

    return arr


def expand_expression(expr):
    '''expand a node expression like 'node[1-10,20]-mgmt'
    Returns array of nodenames'''

    m = NODE_EXPR.match(expr)
    if not m:
        # FIXME raise SyntaxError
        # FIXME catch all these SyntaxErrors nicely
        raise RuntimeError('syntax error')

    (prefix, range_expr, postfix) = m.groups()

    # first split range expression by comma
    # then process each element

    arr = []
    for elem in range_expr.split(','):
        if '/' in elem:
            elem, step = elem.split('/')

            try:
                step = int(step)
            except ValueError:
                raise RuntimeError('syntax error in step')

            if step <= 0:
                raise RuntimeError('invalid step value')

        else:
            step = 1

        if '-' in elem:
            start, end = elem.split('-')
            width = len(end)

            try:
                start = int(start)
            except ValueError:
                raise RuntimeError('syntax error in range')

            try:
                end = int(end)
            except ValueError:
                raise RuntimeError('syntax error in range')

            if start > end:
                raise RuntimeError('invalid range')

            arr.extend(['%s%.*d%s' % (prefix, width, num, postfix)
                        for num in range(start, end + 1, step)])

        else:
            width = len(elem)
            try:
                num = int(elem)
            except ValueError:
                raise RuntimeError('syntax error')

            arr.append('%s%.*d%s' % (prefix, width, num, postfix))

    return arr

# EOB
