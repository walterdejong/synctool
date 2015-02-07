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

import synctool.lib
import synctool.pkgclass


class SyncPkgBrew(synctool.pkgclass.SyncPkg):
    '''package installer class for brew'''

    def __init__(self):
        super(SyncPkgBrew, self).__init__()

    def list(self, pkgs = None):
        super(SyncPkgBrew, self).list(pkgs)

        cmd = 'brew list'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        super(SyncPkgBrew, self).install(pkgs)

        cmd = 'brew install ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        super(SyncPkgBrew, self).remove(pkgs)

        cmd = 'brew remove ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        super(SyncPkgBrew, self).update()

        synctool.lib.shell_command('brew update')

    def upgrade(self):
        super(SyncPkgBrew, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'brew outdated'
        else:
            cmd = 'brew upgrade'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        super(SyncPkgBrew, self).clean()

        synctool.lib.shell_command('brew cleanup')

# EOB
