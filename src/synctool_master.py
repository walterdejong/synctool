#! /usr/bin/env python
#
#   synctool_master.py  WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is synctool on the master node. It calls synctool-client
on the target nodes
'''

import synctool.main.master

if __name__ == '__main__':
    synctool.main.master.main()

# EOB
