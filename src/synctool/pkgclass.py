#
#   synctool.pkgclass.py    WJ111
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''base class for synctool package managers'''

from __future__ import annotations

from synctool.lib import dryrun_msg, log, verbose


class SyncPkg:
    '''generic package installer class'''

    # You may create a new class that has this interface
    # to make a plug-in for synctool-pkg
    # And/or you may use this class as a superclass

    def __init__(self) -> None:
        '''initialize instance'''

    def show_list(self, pkgs: list[str] | None = None) -> None:
        '''output list of packages'''

        if pkgs is not None:
            if len(pkgs) > 1:
                plural = 's'
            else:
                plural = ''

            verbose(f"list package{plural}: {' '.join(pkgs)}")
        else:
            verbose('list all packages')

    def install(self, pkgs: list[str]) -> None:
        '''install list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = f"installing package{plural}: {' '.join(pkgs)}"
        verbose(msg)
        log(msg)

    def remove(self, pkgs: list[str]) -> None:
        '''remove list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = f"removing package{plural}: {' '.join(pkgs)}"
        verbose(msg)
        log(msg)

    def update(self) -> None:
        '''update package database'''

        verbose('updating package database')

    def upgrade(self) -> None:
        '''upgrade packages'''

        msg = 'upgrading packages'
        verbose(dryrun_msg(msg))

        # log the upgrade action ...
        # don't know which packages are upgraded here, sorry
        log(msg)

    def clean(self) -> None:
        '''cleanup any package database caches'''

        verbose('cleaning up caches')

# EOB
