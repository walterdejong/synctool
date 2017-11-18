#
#   synctool.pkg.yum.py        WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''yum package manager (CentOS Linux)'''

try:
    from typing import List
except ImportError:
    pass

import synctool.lib
import synctool.pkgclass


class SyncPkgYum(synctool.pkgclass.SyncPkg):
    '''package installer class for yum'''

    def list(self, pkgs=None):
        # type: (List[str]) -> None
        super(SyncPkgYum, self).list(pkgs)

        cmd = 'yum list installed'
        if pkgs:
            cmd = cmd + ' ' + ' '.join(pkgs)

        synctool.lib.shell_command(cmd)

    def install(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgYum, self).install(pkgs)

        cmd = 'yum -y install ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        super(SyncPkgYum, self).remove(pkgs)

        cmd = 'yum -y remove ' + ' '.join(pkgs)
        synctool.lib.shell_command(cmd)

    def update(self):
        # type: () -> None
        super(SyncPkgYum, self).update()

        # yum has no 'update' command, but will fetch a new database
        # next time when it has no metadata

        synctool.lib.shell_command('yum -y clean headers')
        synctool.lib.shell_command('yum -y clean metadata')

    def upgrade(self):
        # type: () -> None
        super(SyncPkgYum, self).upgrade()

        if synctool.lib.DRY_RUN:
            cmd = 'yum -y check-update'
        else:
            cmd = 'yum -y update'

        tmp = synctool.lib.DRY_RUN
        synctool.lib.DRY_RUN = False
        synctool.lib.shell_command(cmd)
        synctool.lib.DRY_RUN = tmp

    def clean(self):
        # type: () -> None
        super(SyncPkgYum, self).clean()

        synctool.lib.shell_command('yum clean packages')

# EOB
