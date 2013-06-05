#
#	synctool_pkg_brew.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2012
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_lib

from synctool_lib import verbose
from synctool_pkgclass import SyncPkg

import string


class SyncPkgBrew(SyncPkg):
	'''package installer class for brew'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'brew list'

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)

		synctool_lib.DRY_RUN = False
		synctool_lib.shell_command(cmd)
		synctool_lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'brew install ' + string.join(pkgs)

		synctool_lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'brew remove ' + string.join(pkgs)

		synctool_lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		synctool_lib.shell_command('brew update')


	def upgrade(self):
		SyncPkg.upgrade(self)

		if self.dryrun:
			cmd = 'brew outdated'
		else:
			cmd = 'brew upgrade'

		synctool_lib.DRY_RUN = False
		synctool_lib.shell_command(cmd)
		synctool_lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool_lib.shell_command('brew cleanup')


# EOB
