#
#   synctool.pkg.brew.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''brew package manager (Mac OS X)'''

try:
    from typing import List
except ImportError:
    pass

import synctool.lib
import synctool.pkgclass


class SyncPkgBrew(synctool.pkgclass.SyncPkg):
    '''package installer class for brew'''

    def list(self, pkgs=None):
        # type: (List[str]) -> None
        super().list(pkgs)

        cmd = 'brew list'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super().install(pkgs)

        cmd = 'brew install ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super().remove(pkgs)

        cmd = 'brew remove ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super().update()

        synctool.lib.shell_command('brew update')

    def upgrade(self):
        # type: () -> None
        super().upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'brew outdated'
        else:
            cmd = 'brew upgrade'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super().clean()

        synctool.lib.shell_command('brew cleanup')

# EOB
