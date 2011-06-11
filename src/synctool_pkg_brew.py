#
#	synctool_pkgbrew.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_lib

from synctool_lib import verbose
from synctool_pkgclass import SyncPkg

import string


class SyncPkgBrew(SyncPkg):
	'''generic package installer class'''
	
	# You may create a new class that has this interface
	# to make a plug-in for synctool-pkg
	# And/or you may use this class as a superclass
	
	def __init__(self):
		SyncPkg.__init__(self)
	
	
	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)
		
		cmd = 'brew list'
		
		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)
		
		synctool_lib.DRY_RUN = False
		synctool_lib.QUIET = not synctool_lib.VERBOSE
		
		synctool_lib.shell_command(cmd)
		
		synctool_lib.DRY_RUN = self.dryrun
	
	
	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'brew install ' + string.join(pkgs)
		
		synctool_lib.QUIET = not synctool_lib.VERBOSE
		synctool_lib.shell_command(cmd)
	
	
	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)
		
		cmd = 'brew remove ' + string.join(pkgs)
		
		synctool_lib.QUIET = not synctool_lib.VERBOSE
		synctool_lib.shell_command(cmd)
	
	
	def upgrade(self):
		SyncPkg.upgrade(self)
		
		synctool_lib.QUIET = not synctool_lib.VERBOSE
		synctool_lib.shell_command('brew update')


# EOB
