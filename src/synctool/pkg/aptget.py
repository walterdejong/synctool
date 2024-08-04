#
#   synctool.pkg.aptget.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''apt-get package manager (debian Linux)'''

import os

try:
    from typing import List
except ImportError:
    pass

import synctool.lib
import synctool.pkgclass


class SyncPkgAptget(synctool.pkgclass.SyncPkg):
    '''package installer class for apt-get + dpkg'''

    def list(self, pkgs=None):
        # type: (List[str]) -> None
        super().list(pkgs)

        cmd = 'dpkg -l'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super().install(pkgs)

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        cmd = 'apt-get -y install ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super().remove(pkgs)

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        cmd = 'apt-get -y remove ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super().update()

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        synctool.lib.shell_command('apt-get update')

    def upgrade(self):
        # type: () -> None
        super().upgrade()

        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

        if synctool.lib.DRY_RUN:
            cmd = 'apt-get -s upgrade'        # --simulate
        else:
            cmd = 'apt-get -y upgrade'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super().clean()

        synctool.lib.shell_command('apt-get clean')

# EOB
