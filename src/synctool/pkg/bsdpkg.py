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

import synctool.lib
import synctool.pkgclass


# I have no access to *BSD machines so here goes nothing ...

class SyncPkgBsdpkg(synctool.pkgclass.SyncPkg):
	'''package installer class for BSD pkg_add and family'''

	# PKG_PATH should be set already
	# set it in the environment of the root user

	def __init__(self):
		super(SyncPkgBsdpkg, self).__init__()


	def list(self, pkgs = None):
		super(SyncPkgBsdpkg, self).list(pkgs)

		cmd = 'pkg_info'

		if pkgs:
			cmd = cmd + ' ' + ' '.join(pkgs)
		else:
			cmd = cmd + ' -a'		# list all installed packages

		synctool.lib.DRY_RUN = False
		synctool.lib.shell_command(cmd)
		synctool.lib.DRY_RUN = self.dryrun


	def install(self, pkgs):
		super(SyncPkgBsdpkg, self).install(pkgs)

		cmd = 'pkg_add -v ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def remove(self, pkgs):
		super(SyncPkgBsdpkg, self).remove(pkgs)

		cmd = 'pkg_delete -v ' + ' '.join(pkgs)

		synctool.lib.shell_command(cmd)


	def update(self):
		super(SyncPkgBsdpkg, self).update()

		# There is no update command
		# or is there?


	def upgrade(self):
		super(SyncPkgBsdpkg, self).upgrade()

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
		super(SyncPkgBsdpkg, self).clean()

		# there is a PKG_TMPDIR but I won't touch it
		# because the man page says it defaults to /var/tmp

# EOB
