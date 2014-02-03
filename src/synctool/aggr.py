#
#   synctool.aggr.py    WJ109
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''aggregate: group together output that is the same'''

import subprocess
import re

from synctool.lib import stderr

# this matches nodenames like "n8", "r1n8", "r1n8-mgmt"
NODE_PATTERN = re.compile(r'^([a-zA-Z0-9_+-]*)([a-zA-Z_+-]+)(\d+)'
                          r'([a-zA-Z_+-]*)$')


def aggregate(f):
    '''group together input lines that are the same'''

    lines = f.readlines()
    if not lines:
        return

    lines = [x.strip() for x in lines]

    output_per_node = {}

    for line in lines:
        arr = line.split(':')

        if len(arr) <= 1:
            print line
            continue

        node = arr[0]
        output = ':'.join(arr[1:])

        if not node in output_per_node:
            output_per_node[node] = [output]
        else:
            output_per_node[node].append(output)

    nodes = output_per_node.keys()
    if not nodes:
        return

    nodes.sort()

    while len(nodes) > 0:
        node = nodes.pop(0)

        out = output_per_node[node]

        nodelist = [node]

        for node2 in nodes[:]:
            if out == output_per_node[node2]:
                nodelist.append(node2)
                del output_per_node[node2]
                nodes.remove(node2)

        print _compressed(nodelist) + ':'
        for line in out:
            print line


def _compressed(nodes):
    '''Return comma-separated list of nodes in range syntax
    'nodes' is a sorted list of nodes

    Note: This routine doesn't check whether node exists or not
    but that shouldn't be a problem in normal circumstances
    '''

    nodes = nodes[:]    # do not modify the 'input' nodes list

    arr = []    # prepare output list in arr

    while len(nodes) > 0:
        node = nodes.pop(0)

        # try to match a number in the node name
        m = NODE_PATTERN.match(node)
        if not m:
            arr.append(node)
            continue

        # take the matched string parts
        node_a, node_b, node_c, node_d = m.groups()
        # this number is (maybe) start of a sequence
        start = int(node_c)

        # it's not a sequence if the list is too small
        if len(nodes) <= 1:
            arr.append(node)
            continue

        # it's only a sequence if the next N are in sequence
        # outcome should be N >= 2
        seq = start
        seqnodes = nodes[:]
        while len(seqnodes) > 0:
            nextnode = seqnodes[0]
            m = NODE_PATTERN.match(nextnode)
            if not m:
                break
            else:
                a, b, c, d = m.groups()
                if (a != node_a or b != node_b or len(c) != len(node_c) or
                    d != node_d):
                    break

                num = int(c)
                if num != seq + 1:
                    break

                seq = num
                seqnodes.pop(0)

        if seq - start >= 2:
            # we have a sequence!
            seq_str = '%s%s[%.*d-%.*d]%s' % (node_a, node_b,
                                             len(node_c), start,
                                             len(node_c), seq, node_d)
            arr.append(seq_str)
            nodes = seqnodes
        else:
            # not a sequence
            arr.append(node)

    # return comma-separated string of node ranges
    return ','.join(arr)


def run(cmd_arr):
    '''pipe the output through the aggregator
    Returns False on error, else True
    '''

    # simply re-run this command, but with a pipe

    if '-a' in cmd_arr:
        cmd_arr.remove('-a')

    if '--aggregate' in cmd_arr:
        cmd_arr.remove('--aggregate')

    try:
        f = subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT).stdout
    except OSError as err:
        stderr('failed to run command %s: %s' % (cmd_arr[0], err.strerror))
        return False

    with f:
        aggregate(f)

    return True

# EOB
