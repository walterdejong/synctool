#
#   synctool.pkg.apk.py         WJ124
#
#   synctool Copyright 2026 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''apk package manager (alpine Linux)'''

from __future__ import annotations

import synctool.lib
import synctool.pkgclass


class SyncPkgApk(synctool.pkgclass.SyncPkg):
    '''package installer class for apk'''

    def show_list(self, pkgs: list[str] | None = None) -> None:
        super().show_list(pkgs)

        cmd = 'apk list --installed'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs: list[str]) -> None:
        super().install(pkgs)

        cmd = 'apk add ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs: list[str]) -> None:
        super().remove(pkgs)

        cmd = 'apk del ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self) -> None:
        super().update()

        synctool.lib.shell_command('apk update')

    def upgrade(self) -> None:
        super().upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'apk upgrade --simulate'
        else:
            cmd = 'apk upgrade'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self) -> None:
        super().clean()

        synctool.lib.shell_command('apk cache clean')

# EOB
