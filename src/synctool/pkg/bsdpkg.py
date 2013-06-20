#
#	synctool.pkg.bsdpkg.py		WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import os
import string

import synctool.lib
from synctool.pkgclass import SyncPkg


# I have no access to *BSD machines so here goes nothing ...

class SyncPkgBsdpkg(SyncPkg):
	'''package installer class for BSD pkg_add and family'''

	# PKG_PATH should be set already
	# set it in the environment of the root user

	def __init__(self):
		SyncPkg.__init__(self)


	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)

		cmd = 'pkg_info'

		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)
		else:
			cmd = cmd + ' -a'		# list all installed packages

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'pkg_add -v ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)

		cmd = 'pkg_delete -v ' + string.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		SyncPkg.update(self)

		# There is no update command
		# or is there?


	def upgrade(self):
		SyncPkg.upgrade(self)

		if os.uname()[0] == 'FreeBSD':
			# FreeBSD has no pkg_add -u, but freebsd-update instead

			if self.dryrun:
				cmd = 'freebsd-update fetch'
			else:
				cmd = 'freebsd-update fetch install'

		else:
			# OpenBSD/NetBSD/other BSD, use pkg_add -u

			if self.dryrun:
				cmd = 'pkg_add -uvn'
			else:
				cmd = 'pkg_add -uv'

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def clean(self):
		SyncPkg.clean(self)

		# there is a PKG_TMPDIR but I won't touch it
		# because the man page says it defaults to /var/tmp

# EOB
