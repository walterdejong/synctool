#! /usr/bin/env python
#
#   synctool_master_pkg.py    WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''This program is dsh-pkg on the master node. It calls synctool-pkg on
the target nodes'''

import synctool.main.master_pkg

if __name__ == '__main__':
    synctool.main.master_pkg.main()

# EOB
