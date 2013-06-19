#
#	synctool.pkg.zypper.py		WJ111
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


class SyncPkgZypper(SyncPkg):
	'''package installer class for zypper'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'rpm -qa'			# zypper has no 'list-installed' ?

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = ('zypper --non-interactive install '
			'--auto-agree-with-licenses ' + string.join(pkgs))

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'zypper --non-interactive remove ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		synctool.lib.shell_command('zypper --non-interactive refresh')


	def upgrade(self):
		SyncPkg.upgrade(self)

		if self.dryrun:
			cmd = 'zypper list-updates'
		else:
			cmd = ('zypper --non-interactive update '
				'--auto-agree-with-licenses')

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command('zypper clean')
		synctool.lib.DRY_RUN = self.dryrun

# EOB
