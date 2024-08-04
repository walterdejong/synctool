#
#   synctool.pkg.pacman.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''pacman package manager (ArchLinux)'''

from typing import List, Optional

import synctool.lib
import synctool.pkgclass


# I no longer have an ArchLinux system to test this on,
# but here it goes ... :P

class SyncPkgPacman(synctool.pkgclass.SyncPkg):
    '''package installer class for pacman'''

    def show_list(self, pkgs=None):
        # type: (Optional[List[str]]) -> None
        super().show_list(pkgs)

        cmd = 'pacman -Q'
        if pkgs:
            cmd = cmd + 's ' + ' '.join(pkgs)    # use pacman -Qs ...

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super().install(pkgs)

        cmd = 'pacman -S --noconfirm ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super().remove(pkgs)

        cmd = 'pacman -Rs --noconfirm ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super().update()

        synctool.lib.shell_command('pacman -Sy --noconfirm')

    def upgrade(self):
        # type: () -> None
        super().upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'pacman -Qu --noconfirm'        # query updates
        else:
            cmd = 'pacman -Su --noconfirm'        # do upgrade

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super().clean()

        synctool.lib.shell_command('pacman -Scc --noconfirm')

# EOB
