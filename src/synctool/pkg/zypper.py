#
#   synctool.pkg.zypper.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''zypper package manager (SuSE Linux)'''

import synctool.lib
import synctool.pkgclass


class SyncPkgZypper(synctool.pkgclass.SyncPkg):
    '''package installer class for zypper'''

    def __init__(self):
        super(SyncPkgZypper, self).__init__()

    def list(self, pkgs = None):
        super(SyncPkgZypper, self).list(pkgs)

        cmd = 'rpm -qa'            # zypper has no 'list-installed' ?
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        super(SyncPkgZypper, self).install(pkgs)

        cmd = ('zypper --non-interactive install '
               '--auto-agree-with-licenses ' + ' '.join(pkgs))
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        super(SyncPkgZypper, self).remove(pkgs)

        cmd = 'zypper --non-interactive remove ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        super(SyncPkgZypper, self).update()

        synctool.lib.shell_command('zypper --non-interactive refresh')

    def upgrade(self):
        super(SyncPkgZypper, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'zypper --non-interactive list-updates'
        else:
            cmd = ('zypper --non-interactive update '
                   '--auto-agree-with-licenses')

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        super(SyncPkgZypper, self).clean()

        synctool.lib.shell_command('zypper clean')

# EOB
