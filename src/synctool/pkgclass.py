#
#	synctool_pkgclass.py	WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_lib

from synctool_lib import verbose

import string


class SyncPkg:
	'''generic package installer class'''

	# You may create a new class that has this interface
	# to make a plug-in for synctool-pkg
	# And/or you may use this class as a superclass

	def __init__(self):
		self.dryrun = synctool_lib.DRY_RUN


	def list(self, pkgs = None):
		if pkgs:
			verbose('list packages: %s' % string.join(pkgs))
		else:
			verbose('list all packages')


	def install(self, pkgs):
		verbose('install packages: %s' % string.join(pkgs))


	def remove(self, pkgs):
		verbose('removing packages: %s' % string.join(pkgs))


	def update(self):
		verbose('updating package database')


	def upgrade(self):
		verbose('upgrading packages')


	def clean(self):
		verbose('cleaning up caches')

# EOB
