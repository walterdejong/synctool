#
#   synctool.main.aggr.py   WJ109
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''aggregate: group together output that is the same'''

import os
import sys
import getopt

import synctool.aggr
from synctool.main.wrapper import catch_signals


def usage():
    '''print usage information'''

    print '''Typical use of synctool-aggr is:

  command | synctool-aggr

synctool-aggr is built in to synctool-master and synctool-ssh
and activated by the '-a' option
'''


def get_options():
    '''parse command-line options'''

    if len(sys.argv) <= 1:
        return

    try:
        opts, _ = getopt.getopt(sys.argv[1:], 'h', ['help'])
    except getopt.GetoptError as reason:
        print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#       usage()
        sys.exit(1)

    for opt, _ in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)


@catch_signals
def main():
    '''run the program'''

    get_options()
    synctool.aggr.aggregate(sys.stdin)

# EOB
