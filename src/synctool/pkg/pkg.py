#
#   synctool.pkg.pkg.py     WJ117
#
#   synctool Copyright 2017 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''FreeBSD pkg package manager'''

try:
    from typing import List
except ImportError:
    pass

import synctool.lib
import synctool.pkgclass


class SyncPkgPkg(synctool.pkgclass.SyncPkg):
    '''package installer class for FreeBSD pkg'''

    def list(self, pkgs=None):
        # type: (List[str]) -> None
        super(SyncPkgPkg, self).list(pkgs)

        cmd = 'pkg info'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)
        else:
            cmd = cmd + ' -a'        # list all installed packages

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgPkg, self).install(pkgs)

        cmd = 'pkg install -y ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgPkg, self).remove(pkgs)

        cmd = 'pkg delete -y ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super(SyncPkgPkg, self).update()

        synctool.lib.shell_command('pkg update')

    def upgrade(self):
        # type: () -> None
        super(SyncPkgPkg, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'pkg upgrade -y -n'
        else:
            cmd = 'pkg upgrade -y'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super(SyncPkgPkg, self).clean()

        synctool.lib.shell_command('pkg clean')

# EOB
