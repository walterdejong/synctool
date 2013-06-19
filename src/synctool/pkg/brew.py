#
#	synctool.pkg.brew.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import string

import synctool.lib
from synctool.pkgclass import SyncPkg


class SyncPkgBrew(SyncPkg):
	'''package installer class for brew'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'brew list'

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'brew install ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'brew remove ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		synctool.lib.shell_command('brew update')


	def upgrade(self):
		SyncPkg.upgrade(self)

		if self.dryrun:
			cmd = 'brew outdated'
		else:
			cmd = 'brew upgrade'

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool.lib.shell_command('brew cleanup')

# EOB
