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

import synctool.lib
import synctool.pkgclass


# I no longer have an ArchLinux system to test this on,
# but here it goes ... :P

class SyncPkgPacman(synctool.pkgclass.SyncPkg):
    '''package installer class for pacman'''

    def __init__(self):
        super(SyncPkgPacman, self).__init__()

    def list(self, pkgs = None):
        super(SyncPkgPacman, self).list(pkgs)

        cmd = 'pacman -Q'
        if pkgs:
            cmd = cmd + 's ' + ' '.join(pkgs)    # use pacman -Qs ...

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        super(SyncPkgPacman, self).install(pkgs)

        cmd = 'pacman -S --noconfirm ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        super(SyncPkgPacman, self).remove(pkgs)

        cmd = 'pacman -Rs --noconfirm ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        super(SyncPkgPacman, self).update()

        synctool.lib.shell_command('pacman -Sy --noconfirm')

    def upgrade(self):
        super(SyncPkgPacman, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'pacman -Qu --noconfirm'        # query updates
        else:
            cmd = 'pacman -Su --noconfirm'        # do upgrade

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        super(SyncPkgPacman, self).clean()

        synctool.lib.shell_command('pacman -Scc --noconfirm')

# EOB
