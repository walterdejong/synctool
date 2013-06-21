#
#	synctool_pkgclass.py	WJ111
#
#   synctool Copyright 2013 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool.lib
from synctool.lib import verbose


class SyncPkg:
	'''generic package installer class'''

	# You may create a new class that has this interface
	# to make a plug-in for synctool-pkg
	# And/or you may use this class as a superclass

	def __init__(self):
		self.dryrun = synctool.lib.DRY_RUN


	def list(self, pkgs = None):
		if pkgs:
			verbose('list packages: %s' % ' '.join(pkgs))
		else:
			verbose('list all packages')


	def install(self, pkgs):
		verbose('install packages: %s' % ' '.join(pkgs))


	def remove(self, pkgs):
		verbose('removing packages: %s' % ' '.join(pkgs))


	def update(self):
		verbose('updating package database')


	def upgrade(self):
		verbose('upgrading packages')


	def clean(self):
		verbose('cleaning up caches')

# EOB
