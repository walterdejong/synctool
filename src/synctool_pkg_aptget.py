#
#	synctool_pkg_aptget.py		WJ111
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


class SyncPkgAptget(SyncPkg):
	'''package installer class for apt-get + dpkg'''
	
	def __init__(self):
		SyncPkg.__init__(self)
	
	
	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)
		
		cmd = 'dpkg -l'
		
		if pkgs:
			cmd = cmd + ' ' + string.join(pkgs)
		
		synctool_lib.DRY_RUN = False
		synctool_lib.shell_command(cmd)
		synctool_lib.DRY_RUN = self.dryrun
	
	
	def install(self, pkgs):
		SyncPkg.install(self, pkgs)

		cmd = 'apt-get -y install ' + string.join(pkgs)
		
		synctool_lib.shell_command(cmd)
	
	
	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)
		
		cmd = 'apt-get -y remove ' + string.join(pkgs)
		
		synctool_lib.shell_command(cmd)
	
	
	def upgrade(self):
		SyncPkg.upgrade(self)
		
		synctool_lib.DRY_RUN = False
		synctool_lib.shell_command('apt-get update')
		
		if self.dryrun:
			cmd = 'apt-get -s upgrade'		# --simulate
		else:
			cmd = 'apt-get -y upgrade'
		
		synctool_lib.DRY_RUN = False
		synctool_lib.shell_command(cmd)
		synctool_lib.DRY_RUN = self.dryrun
	
	
	def clean(self):
		SyncPkg.clean(self)
		
		synctool_lib.shell_command('apt-get clean')


# EOB
