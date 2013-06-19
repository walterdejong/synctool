#
#	synctool.pkg.yum.py		WJ111
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


class SyncPkgYum(SyncPkg):
	'''package installer class for yum'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'yum list installed'

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'yum -y install ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'yum -y remove ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		# yum has no 'update' command, but will fetch a new database
		# next time when it has no metadata

		synctool.lib.shell_command('yum -y clean headers')
		synctool.lib.shell_command('yum -y clean metadata')


	def upgrade(self):
		SyncPkg.upgrade(self)

		if self.dryrun:
			cmd = 'yum -y check-update'
		else:
			cmd = 'yum -y update'

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool.lib.shell_command('yum clean packages')

# EOB
