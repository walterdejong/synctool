#
#	synctool.pkg.pacman.py		WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool.lib
from synctool.pkgclass import SyncPkg


# I no longer have an ArchLinux system to test this on,
# but here it goes ... :P

class SyncPkgPacman(SyncPkg):
	'''package installer class for pacman'''

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'pacman -Q'

		if pkgs:
			cmd = cmd + 's ' + ' '.join(pkgs)	# use pacman -Qs ...

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'pacman -S --noconfirm ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'pacman -Rs --noconfirm ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		synctool.lib.shell_command('pacman -Sy --noconfirm')


	def upgrade(self):
		SyncPkg.upgrade(self)

		synctool.lib.DRY_RUN = False

		if self.dryrun:
			cmd = 'pacman -Qu --noconfirm'		# query updates
		else:
			cmd = 'pacman -Su --noconfirm'		# do upgrade

		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		synctool.lib.shell_command('pacman -Scc --noconfirm')

# EOB
