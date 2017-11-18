#
#   synctool.pkg.bsdpkg.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''bsdpkg package manager (Open/Net/DragonFly BSD)'''

# Note: for FreeBSD, use the 'pkg' package manager (not 'bsdpkg')

import os

try:
    from typing import List
except ImportError:
    pass

import synctool.lib
import synctool.pkgclass


# I have no access to *BSD machines so here goes nothing ...

class SyncPkgBsdpkg(synctool.pkgclass.SyncPkg):
    '''package installer class for BSD pkg_add and family'''

    # PKG_PATH should be set already
    # set it in the environment of the root user

    def list(self, pkgs=None):
        # type: (List[str]) -> None
        super(SyncPkgBsdpkg, self).list(pkgs)

        cmd = 'pkg_info'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)
        else:
            cmd = cmd + ' -a'        # list all installed packages

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgBsdpkg, self).install(pkgs)

        cmd = 'pkg_add -v ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgBsdpkg, self).remove(pkgs)

        cmd = 'pkg_delete -v ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super(SyncPkgBsdpkg, self).update()

        # There is no update command
        # or is there?

    def upgrade(self):
        # type: () -> None
        super(SyncPkgBsdpkg, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'pkg_add -uvn'
        else:
            cmd = 'pkg_add -uv'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super(SyncPkgBsdpkg, self).clean()

        # there is a PKG_TMPDIR but I won't touch it
        # because the man page says it defaults to /var/tmp

# EOB
