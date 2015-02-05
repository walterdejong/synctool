#! /usr/bin/env python
#
#   dsh_pkg.py  WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is dsh-pkg on the master node. It calls synctool-client-pkg
on the target nodes'''

import synctool.main.dsh_pkg

if __name__ == '__main__':
    synctool.main.dsh_pkg.main()

# EOB
