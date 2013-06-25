#
#	synctool.pkg.aptget.py		WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os

import synctool.lib
import synctool.pkgclass


class SyncPkgAptget(synctool.pkgclass.SyncPkg):
	'''package installer class for apt-get + dpkg'''

	def __init__(self):
		super(SyncPkgAptget, self).__init__()


	def list(self, pkgs = None):
		super(SyncPkgAptget, self).list(pkgs)

		cmd = 'dpkg -l'

		if pkgs:
			cmd = cmd + ' ' + ' '.join(pkgs)

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		super(SyncPkgAptget, self).install(pkgs)

		os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

		cmd = 'apt-get -y install ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		super(SyncPkgAptget, self).remove(pkgs)

		os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

		cmd = 'apt-get -y remove ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		super(SyncPkgAptget, self).update()

		os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
		synctool.lib.shell_command('apt-get update')


	def upgrade(self):
		super(SyncPkgAptget, self).upgrade()

		os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

		if self.dryrun:
			cmd = 'apt-get -s upgrade'		# --simulate
		else:
			cmd = 'apt-get -y upgrade'

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		super(SyncPkgAptget, self).clean()

		synctool.lib.shell_command('apt-get clean')

# EOB
