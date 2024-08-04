#
#   synctool.pkgclass.py    WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''base class for synctool package managers'''

try:
    from typing import List
except ImportError:
    pass

from synctool.lib import verbose, log, dryrun_msg


class SyncPkg:
    '''generic package installer class'''

    # You may create a new class that has this interface
    # to make a plug-in for synctool-pkg
    # And/or you may use this class as a superclass

    def __init__(self):
        # type: () -> None
        '''initialize instance'''


    def list(self, pkgs=None):
        # type: (List[str]) -> None
        '''output list of packages'''

        if pkgs:
            if len(pkgs) > 1:
                plural = 's'
            else:
                plural = ''

            verbose('list package%s: %s' % (plural, ' '.join(pkgs)))
        else:
            verbose('list all packages')

    def install(self, pkgs):
        # type: (List[str]) -> None
        '''install list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = 'installing package%s: %s' % (plural, ' '.join(pkgs))
        verbose(msg)
        log(msg)

    def remove(self, pkgs):
        # type: (List[str]) -> None
        '''remove list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = 'removing package%s: %s' % (plural, ' '.join(pkgs))
        verbose(msg)
        log(msg)

    def update(self):
        # type: () -> None
        '''update package database'''

        verbose('updating package database')

    def upgrade(self):
        # type: () -> None
        '''upgrade packages'''

        msg = 'upgrading packages'
        verbose(dryrun_msg(msg))

        # log the upgrade action ...
        # don't know which packages are upgraded here, sorry
        log(msg)

    def clean(self):
        # type: () -> None
        '''cleanup any package database caches'''

        verbose('cleaning up caches')

# EOB
