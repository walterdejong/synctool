#
#	synctool.pkg.aptget.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import string

import synctool.lib
from synctool.lib import verbose
from synctool.pkgclass import SyncPkg


class SyncPkgAptget(SyncPkg):
	'''package installer class for apt-get + dpkg'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'dpkg -l'

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		os.putenv('DEBIAN_FRONTEND', 'noninteractive')

		cmd = 'apt-get -y install ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		os.putenv('DEBIAN_FRONTEND', 'noninteractive')

		cmd = 'apt-get -y remove ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		os.putenv('DEBIAN_FRONTEND', 'noninteractive')
		synctool.lib.shell_command('apt-get update')


	def upgrade(self):
		SyncPkg.upgrade(self)

		os.putenv('DEBIAN_FRONTEND', 'noninteractive')

		if self.dryrun:
			cmd = 'apt-get -s upgrade'		# --simulate
		else:
			cmd = 'apt-get -y upgrade'

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool.lib.shell_command('apt-get clean')

# EOB
