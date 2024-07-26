# pylint: disable=consider-using-f-string
#
#   synctool.aggr.py    WJ109
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''aggregate: group together output that is the same'''

import subprocess

try:
    from typing import List, Dict, IO
except ImportError:
    pass

from synctool.lib import stderr
import synctool.range


def aggregate(fresult):
    # type: (IO) -> None
    '''group together input lines that are the same'''

    lines = fresult.readlines()
    if not lines:
        return

    lines = [x.strip() for x in lines]

    output_per_node = {}    # type: Dict[str, List[str]]

    for line in lines:
        arr = line.split(':', 1)

        if len(arr) <= 1:
            print(line)
            continue

        node = arr[0]
        output = arr[1]

        if node not in output_per_node:
            output_per_node[node] = [output,]
        else:
            output_per_node[node].append(output)

    nodes = list(output_per_node.keys())
    if not nodes:
        return

    nodes.sort()

    while nodes:
        node = nodes.pop(0)

        out = output_per_node[node]

        nodelist = [node,]

        for node2 in nodes[:]:
            if out == output_per_node[node2]:
                nodelist.append(node2)
                del output_per_node[node2]
                nodes.remove(node2)

        print(synctool.range.compress(nodelist) + ':')
        for line in out:
            print(line)


def run(cmd_arr):
    # type: (List[str]) -> bool
    '''pipe the output through the aggregator
    Returns False on error, else True
    '''

    # simply re-run this command, but with a pipe

    if '-a' in cmd_arr:
        cmd_arr.remove('-a')

    if '--aggregate' in cmd_arr:
        cmd_arr.remove('--aggregate')

    try:
        with subprocess.Popen(cmd_arr, shell=False, bufsize=4096,
                stdout=subprocess.PIPE, text=True,
                stderr=subprocess.STDOUT) as pipe:
            fresult = pipe.stdout

    except OSError as err:
        stderr("failed to run command {0}: {1}".format(cmd_arr[0],err.strerror))
        return False

    with fresult:
        aggregate(fresult)

    return True

# EOB
