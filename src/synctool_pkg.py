#! /usr/bin/env python
#
#	synctool_pkg.py		WJ111
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2011
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

import synctool_param
import synctool_config
import synctool_lib

from synctool_lib import verbose,stdout,stderr,terse,unix_out,dryrun_msg

import os
import sys
import string
import getopt
import errno

# enums for command-line options
ACTION_INSTALL = 1
ACTION_REMOVE = 2
ACTION_LIST = 3
ACTION_UPGRADE = 4

# action to perform
ACTION = 0

# list of packages given on the command-line
PKG_LIST = None


class SyncPkg:
	'''generic package installer class'''
	
	# You may create a new class that has this interface
	# to make a plug-in for synctool-pkg
	
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
	
	def upgrade(self):
		verbose('upgrading packages')


class SyncPkgOops(SyncPkg):
	'''package installer class that only prints errors because
	it doesn't have any good implementation: unknown platform'''
	
	def __init__(self):
		SyncPkg.__init__(self)
	
	def oops(self):
		if not self.dryrun:
			stderr("error: don't know how to do that on this platform")
			sys.exit(127)
	
	def list(self, pkgs = None):
		SyncPkg.list(self, pkgs)
		self.dryrun = False
		self.oops()
	
	def install(self, pkgs):
		SyncPkg.install(self, pkgs)
		self.oops()
	
	def remove(self, pkgs):
		SyncPkg.remove(self, pkgs)
		self.oops()
	
	def upgrade(self):
		SyncPkg.upgrade(self)
		self.oops()


def detect_installer():
	'''Attempt to detect the operating system and package system
	Returns instance of a SyncPkg installer class'''
	
	return SyncPkgOops()


def rearrange_options(arglist):
	'''rearrange command-line options so that getopt() behaves in a GNUish way'''
	
	if not arglist:
		return arglist
	
	n = len(arglist)
	
	while n > 0:
		n = n - 1
		
		if arglist[-1] == '--':
			break
		
		if arglist[-1][0] != '-':
			break
		
		arg = arglist.pop()			# get from the back
		arglist.insert(0, arg)		# put last argument first
	
	return arglist
	

def there_can_be_only_one():
	print 'Specify only one of these options:'
	print '  -i, --install PACKAGE [..]     Install package'
	print '  -R, --remove  PACKAGE [..]     Uninstall package'
	print '  -l, --list   [PACKAGE ...]     List packages'
	print '  -U, --upgrade                  Upgrade packages'
	print
	sys.exit(1)


def usage():
	print 'usage: %s [options]' % os.path.basename(sys.argv[0])
	print 'options:'
	print '  -h, --help                     Display this information'
	print '  -c, --conf=dir/file            Use this config file'
	print '                                 (default: %s)' % synctool_param.DEFAULT_CONF
	print '  -i, --install PACKAGE [..]     Install package'
	print '  -R, --remove  PACKAGE [..]     Uninstall package'
	print '  -l, --list   [PACKAGE ...]     List packages'
	print '  -U, --upgrade                  Upgrade packages'
	print
	print '  -f, --fix                      Perform updates (otherwise, do dry-run)'
	print '  -v, --verbose                  Be verbose'
	print '      --unix                     Output actions as unix shell commands'
	print
	print 'Note that synctool-pkg does a dry run unless you specify --fix'
	print
	print 'synctool-pkg by Walter de Jong <walter@heiho.net> (c) 2011'


def get_options():
	global ACTION, PKG_LIST
	
	if len(sys.argv) <= 1:
		usage()
		sys.exit(1)

	synctool_lib.DRY_RUN = True				# set default dry-run
	
	# getopt() assumes that all options given after the first non-option
	# argument are all arguments (this is standard UNIX behavior, not GNU)
	# but in this case, I like the GNU way better, so re-arrange the options
	
	arglist = rearrange_options(sys.argv[1:])
	
	try:
		opts, args = getopt.getopt(arglist, 'hc:i:R:loUfvq',
			['help', 'conf=',
			'install=', 'remove=', 'list', 'outdated', 'upgrade',
			'verbose', 'unix', 'quiet'])
	except getopt.error, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)
	
	except getopt.GetoptError, (reason):
		print '%s: %s' % (os.path.basename(sys.argv[0]), reason)
#		usage()
		sys.exit(1)
	
	except:
		usage()
		sys.exit(1)
	
	# first read the config file
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?'):
			usage()
			sys.exit(1)
		
		if opt in ('-c', '--conf'):
			synctool_param.CONF_FILE = arg
			continue
		
	synctool_config.read_config()
	
	# then process the other options
	ACTION = 0
	PKG_LIST = []
	
	for opt, arg in opts:
		if opt in ('-h', '--help', '-?', '-c', '--conf'):
			# already done
			continue
		
		if opt in ('-i', '--install'):
			if ACTION > 0 and ACTION != ACTION_INSTALL:
				there_can_be_only_one()
			
			ACTION = ACTION_INSTALL
			
			PKG_LIST.append(arg)
			
			if args != None and len(args) > 0:
				PKG_LIST.extend(args)
				args = None
			
			continue
		
		if opt in ('-R', '--remove'):
			if ACTION > 0 and ACTION != ACTION_REMOVE:
				there_can_be_only_one()
			
			ACTION = ACTION_REMOVE
			
			PKG_LIST.append(arg)
			
			if args != None and len(args) > 0:
				PKG_LIST.extend(args)
				args = None
			
			continue
		
		if opt in ('-l', '--list'):
			if ACTION > 0 and ACTION != ACTION_LIST:
				there_can_be_only_one()
			
			ACTION = ACTION_LIST
			
			if args != None and len(args) > 0:
				PKG_LIST.extend(args)
				args = None
			
			continue
		
		if opt in ('-U', '--upgrade'):
			if ACTION > 0 and ACTION != ACTION_UPGRADE:
				there_can_be_only_one()
			
			ACTION = ACTION_UPGRADE
			continue
		
		if opt in ('-f', '--fix'):
			synctool_lib.DRY_RUN = False
			continue
		
		if opt in ('-v', '--verbose'):
			synctool_lib.VERBOSE = True
			continue
		
		if opt == '--unix':
			synctool_lib.UNIX_CMD = True
			continue
		
		if opt in ('-q', '--quiet'):
			# silently ignore this option
			continue
	
	if not ACTION:
		usage()
		sys.exit(1)
	
	if args != None and len(args) > 0:
		stderr('error: excessive arguments on command line')
		sys.exit(1)


def main():
	get_options()
	
	pkg = detect_installer()
	
	if ACTION == ACTION_LIST:
		pkg.list(PKG_LIST)
	
	elif ACTION == ACTION_INSTALL:
		pkg.install(PKG_LIST)
	
	elif ACTION == ACTION_REMOVE:
		pkg.remove(PKG_LIST)
	
	elif ACTION == ACTION_UPGRADE:
		pkg.upgrade()
	
	else:
		raise RuntimeError, 'BUG: unknown ACTION code %d' % ACTION


if __name__ == '__main__':
	try:
		main()
	except IOError, ioerr:
		if ioerr.errno == errno.EPIPE:		# Broken pipe
			pass
		else:
			print ioerr

	except KeyboardInterrupt:		# user pressed Ctrl-C
		pass


# EOB
