#
#   synctool.range.py        WJ113
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''The node range expression parser can expand expressions like
"node[1-10,15]" to a list of nodes. A check for existing nodes
is not made here; just the string expansion

The automatic number sequencer can convert strings that look like
IPv4 "192.168.1.[100]" or hexidecimal IPv6 "64:b9:e8:ff:fe:c2:fd:[20]"
or IPv6:v4 notation "64:b9:e8:[0a]:10.0.0.[100]"
or just a string "node-[10].sub[20].domain.org"
'''

import re

# a node expression may look like 'node1-[1,2,8-10/2]-mgmt'
# or something somewhat resembling that
# Take make matters worse, a line may have multiple of these
# separated by comma's
# The regex here is not super strict, but it suffices to split a line
SPLIT_EXPR = re.compile(r'([a-zA-Z0-9_+-]+\[\d+[0-9,/-]*\][a-zA-Z0-9_+-]*|'
                        r'[a-zA-Z0-9_+-]+)')

# This regex is used to take apart a single node range expression
NODE_EXPR = re.compile(r'([a-zA-Z][a-zA-Z0-9_+-]*)'
                       r'\[(\d+[0-9,/-]*)\]'
                       r'([a-zA-Z0-9_+-]*)$')

# match sequence notation "192.168.1.[200]" or "node[10].domain.org"
# supports hex for IPv6
MATCH_SEQ = re.compile(r'([^[]*)\[([0-9a-f]+)\](.*)')

# these look pretty naive, but note that they include brackets for
# sequence notation: automated numbering of sequences
# It's for recognising a pattern, not for checking validity of IP addresses
MATCH_IPv4 = re.compile(r'^[0-9\.\[\]]+$')
MATCH_IPv6 = re.compile(r'^[0-9a-f:\[\]]+$')
MATCH_IPv6_v4 = re.compile(r'^[0-9a-f:\[\]]+:[0-9\.\[\]]+$')
SPLIT_IPv6_v4 = re.compile(r'(?=[0-9a-f:\[\]]+):(?=[0-9\.\[\]]+)')

# this matches nodenames like "n8", "r1n8", "r1n8-mgmt"
# and is used by compress()
# It works like: "head,number,tail" or "prefix-number-postfix"
COMPRESSOR = re.compile(r'^([a-zA-Z0-9_+-]*[a-zA-Z_+-]+)'
                        r'(\d+)'
                        r'([a-zA-Z_+-]*)$')

# state used for automatic numbering of IP ranges
_EXPAND_SEQ = 0


class RangeSyntaxError(Exception):
    '''node range syntax error exception'''
    pass


def split_nodelist(expr):
    '''split a string like 'node1,node2,node[3-6,8,10],node-x'
    May throw RangeSyntaxError if there is a syntax error
    Returns the array of elements
    '''

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
    Returns array of node names
    '''

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

            if end - start > 100000:
                raise RangeSyntaxError('ignoring ridiculously large range')

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


def reset_sequence():
    '''reset a sequence to zero'''

    global _EXPAND_SEQ

    _EXPAND_SEQ = 0


def expand_sequence(arg):
    '''expand a sequence that looks like '192.168.1.[100]'
    or hexidecimal IPv6 "64:b9:e8:ff:fe:c2:fd:[20]"
    or IPv6:v4 notation "64:b9:e8:[0a]:10.0.0.[100]"
    or just a string "node-[10].sub[20].domain.org"
    '''

    global _EXPAND_SEQ

    if not '[' in arg:
        return arg

    if MATCH_IPv4.match(arg):
        # looks like IPv4 address
        result = expand_seq(arg)
        _EXPAND_SEQ += 1
        return result

    elif MATCH_IPv6.match(arg):
        # looks like IPv6 address
        result = expand_seq(arg, 16)
        _EXPAND_SEQ += 1
        return result

    elif MATCH_IPv6_v4.match(arg):
        # looks like IPv6:v4 address
        part_v6, part_v4 = SPLIT_IPv6_v4.split(arg)
        part_v6 = expand_seq(part_v6, 16)
        part_v4 = expand_seq(part_v4)
        _EXPAND_SEQ += 1
        return part_v6 + ':' + part_v4

    # else: regular string
    result = expand_seq(arg, overflow=True)
    _EXPAND_SEQ += 1
    return result


def expand_seq(arg, radix=10, overflow=False):
    '''expand an automatic numbering sequence like "192.168.1.[200]"
    or IPv6 "64:b9:e8:ff:fe:c2:fd:[0a]" or "64:b9:e8:[0a]:10.0.0.[100]"
    or just a string "node[10].sub[20].domain.org"
    '''

    if not '[' in arg:
        return arg

    m = MATCH_SEQ.match(arg)
    if not m:
        raise RangeSyntaxError('syntax error in numbering sequence')

    (prefix, num, postfix) = m.groups()
    width = len(num)
    try:
        num = int(num, radix)
    except ValueError:
        raise RangeSyntaxError('invalid value in numbering sequence')

    num += _EXPAND_SEQ
    if num > 255 and not overflow:
        raise RangeSyntaxError('IP address extends beyond 255')

    if radix == 10:
        result = '%s%.*d%s' % (prefix, width, num, postfix)
    elif radix == 16:
        result = '%s%.*x%s' % (prefix, width, num, postfix)
    else:
        raise RuntimeError("bug: radix == %d" % radix)

    if '[' in result:
        # recurse to replace all occurrences
        return expand_seq(result, radix, overflow)

    return result


def _sort_compress(a, b):
    '''sorting function
    a and b are tuples: (nodename, prefix, number_str, number, postfix)
    '''

    if a[1] != b[1]:
        # sort by prefix
        return cmp(a[1], b[1])

    if a[3] != b[3]:
        # sort by postfix
        return cmp(a[3], b[3])

    if len(a[2]) != len(b[2]):
        # sort by length number_str
        return cmp(len(a[2]), len(b[2]))

    if a[3] != b[3]:
        # sort by number
        return cmp(a[3], b[3])

    # lastly, sort by node name
    return cmp(a[0], b[0])


def uniq(seq):
    '''remove duplicates from set, preserving order'''

    # mostly taken from StackOverflow

    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def compress(nodelist):
    '''Return comma-separated list of nodes, using range syntax

    This is the opposite of function expand()
    It can not do step-notation but it's good at finding sequences
    like "n[1-5,7,8]"
    '''

    # make all_grouped a list of lists, of grouped splitted nodenames
    all_grouped = []
    grouped = []
    prev_prefix = prev_postfix = None
    for node in uniq(nodelist):
        # try to match a number in the nodename
        m = COMPRESSOR.match(node)
        if not m:
            # no number in node name
            if len(grouped) > 0:
                grouped.sort(_sort_compress)
                all_grouped.append(grouped[:],)
                grouped = []

            grouped = [(node, '', '0', 0, ''),]
            all_grouped.append(grouped[:],)
            grouped = []
            prev_prefix = prev_postfix = None
        else:
            # group nodes with the same prefix and postfix together
            prefix, number, postfix = m.groups()
            if prefix == prev_prefix and postfix == prev_postfix:
                grouped.append((node, prefix, number, int(number), postfix),)
            else:
                if len(grouped) > 0:
                    grouped.sort(_sort_compress)
                    all_grouped.append(grouped[:],)
                    grouped = []

                grouped.append((node, prefix, number, int(number), postfix),)
                prev_prefix = prefix
                prev_postfix = postfix

    if len(grouped) > 0:
        grouped.sort(_sort_compress)
        all_grouped.append(grouped[:],)
        grouped = []

    # make out, a list of strings (with range-based node syntax)
    out = []
    for arr in all_grouped:
        (node, prefix, number_str, num, postfix) = arr[0]
        if len(arr) == 1:
            # add single node name
            out.append(node)
            continue

        # make range syntax
        range_str = prefix + '[' + number_str

        if len(arr) == 2:
            (node, prefix, number_str, num, postfix) = arr[1]
            range_str += ',' + number_str
        else:
            start = num
            prev_number_str = None
            prev_len = len(number_str)
            in_seq = 0
            for (node, prefix, number_str, num, postfix) in arr[1:]:
                if num == start + 1 and 0 <= len(number_str) - prev_len <= 1:
                    # it's in sequence
                    in_seq += 1
                else:
                    # not in sequence
                    if in_seq == 0:
                        pass
                    elif in_seq == 1:
                        range_str += ',' + prev_number_str
                    else:
                        range_str += '-' + prev_number_str

                    range_str += ',' + number_str
                    in_seq = 0

                start = num
                prev_number_str = number_str
                prev_len = len(number_str)

            if in_seq == 0:
                pass
            elif in_seq == 1:
                range_str += ',' + prev_number_str
            else:
                range_str += '-' + prev_number_str

        range_str += ']' + postfix
        out.append(range_str)

    # return comma-separated string of node ranges
    return ','.join(out)

# EOB
