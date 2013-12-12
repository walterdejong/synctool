#
#    synctool.range.py        WJ113
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''The node range expression parser can expand expressions like
"node[1-10,15]" to a list of nodes. A check for existing nodes
is not made here; just the string expansion'''

# this code is in its own small module because of circular imports

import re

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


class RangeSyntaxError(Exception):
    '''node range syntax error exception'''
    pass


def split_nodelist(expr):
    '''split a string like 'node1,node2,node[3-6,8,10],node-x'
    May throw RangeSyntaxError if there is a syntax error
    Returns the array of elements'''

    arr = []

    # SPLIT_EXPR is a global compiled regex for splitting node expr lines
    for elem in SPLIT_EXPR.split(expr):
        if not elem:
            continue

        if elem == ',':
            continue

        if not SPLIT_EXPR.match(elem):
            raise RangeSyntaxError('syntax error in range expression')

        arr.append(elem)

    return arr


def expand(expr):
    '''expand a range expression like 'node[1-10,20]-mgmt'
    May throw RangeSyntaxError if there is a syntax error
    Returns array of node names'''

    # NODE_EXPR is a global compiled regex for recognising expression
    m = NODE_EXPR.match(expr)
    if not m:
        raise RangeSyntaxError('syntax error in range expression')

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
                raise RangeSyntaxError('syntax error in range expression')

            if step <= 0:
                raise RangeSyntaxError('invalid step value in range '
                                       'expression')
            # else: pass
        else:
            step = 1

        if '-' in elem:
            start, end = elem.split('-')
            # width allows for numbers with leading zeroes: 'n001 to n999'
            width = len(start)

            try:
                start = int(start)
            except ValueError:
                raise RangeSyntaxError('syntax error in range expression')

            try:
                end = int(end)
            except ValueError:
                raise RangeSyntaxError('syntax error in range expression')

            if start > end:
                raise RangeSyntaxError('invalid range in range expression')

            arr.extend(['%s%.*d%s' % (prefix, width, num, postfix)
                        for num in range(start, end + 1, step)])
        else:
            width = len(elem)
            try:
                num = int(elem)
            except ValueError:
                raise RangeSyntaxError('syntax error in range expression')

            arr.append('%s%.*d%s' % (prefix, width, num, postfix))

    return arr

# EOB
