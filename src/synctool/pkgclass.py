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

from synctool.lib import verbose, log, dryrun_msg


class SyncPkg(object):
    '''generic package installer class'''

    # You may create a new class that has this interface
    # to make a plug-in for synctool-pkg
    # And/or you may use this class as a superclass

    def __init__(self):
        '''initialize instance'''

        pass

    def list(self, pkgs=None):
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
        '''install list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = 'installing package%s: %s' % (plural, ' '.join(pkgs))
        verbose(msg)
        log(msg)

    def remove(self, pkgs):
        '''remove list of packages'''

        if len(pkgs) > 1:
            plural = 's'
        else:
            plural = ''

        msg = 'removing package%s: %s' % (plural, ' '.join(pkgs))
        verbose(msg)
        log(msg)

    def update(self):
        '''update package database'''

        verbose('updating package database')

    def upgrade(self):
        '''upgrade packages'''

        msg = 'upgrading packages'
        verbose(dryrun_msg(msg))

        # log the upgrade action ...
        # don't know which packages are upgraded here, sorry
        log(msg)

    def clean(self):
        '''cleanup any package database caches'''

        verbose('cleaning up caches')

# EOB
