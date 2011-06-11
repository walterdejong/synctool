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

import synctool_config
import synctool_param
import synctool_stat
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

# list of supported package managers
KNOWN_PACKAGE_MANAGERS = (
	'apt-get', 'yum', 'zypper', 'brew',
#	'pacman', 'urpmi', 'portage', 'port', 'swaret', 'pkg_add'
)

# list of Linux package managers: (Linux release file, package manager)
LINUX_PACKAGE_MANAGERS = (
	( '/etc/debian_version', 'apt-get' ),
	( '/etc/SuSE-release', 'zypper' ),
	( '/etc/redhat-release', 'yum' ),
	( '/etc/arch-release', 'pacman' ),
	( '/etc/gentoo-release', 'portage' ),
	( '/etc/slackware-version', 'swaret' ),
	( '/etc/fedora-release', 'yum' ),
	( '/etc/yellowdog-release', 'yum' ),
	( '/etc/mandrake-release', 'urpmi' ),
)


def package_manager():
	'''return instance of SyncPkg installer class'''
	
	detected = False
	
	if not synctool_param.PACKAGE_MANAGER:
		detect_installer()
		
		if not synctool_param.PACKAGE_MANAGER:
			stderr('failed to detect package management system')
			stderr('please configure it in synctool.conf')
			sys.exit(1)
		
		detected = True
	
	for mgr in KNOWN_PACKAGE_MANAGERS:
		if synctool_param.PACKAGE_MANAGER == mgr:
			short_mgr = string.replace(mgr, '-', '')
			
			# load the module
			module = __import__('synctool_pkg_%s' % short_mgr)
			
			# find the package manager class
			pkgclass = getattr(module, 'SyncPkg%s' % string.capitalize(short_mgr))
			
			# instantiate the class
			return pkgclass()
	
	if detected:
		stderr('package manager %s is not supported yet' % synctool_param.PACKAGE_MANAGER)
	else:
		stderr("unknown package manager defined: '%s'" % synctool_param.PACKAGE_MANAGER)
	
	sys.exit(1)


def detect_installer():
	'''Attempt to detect the operating system and package system
	Returns instance of a SyncPkg installer class'''
	
	#
	# attempt a best effort at detecting OSes for the purpose of
	# choosing a package manager
	# It's probably not 100% fool-proof, but as said, it's a best effort
	#
	# Problems:
	# - there are too many platforms and too many Linux distros
	# - there are too many different packaging systems
	# - there are RedHat variants that all have /etc/redhat-release but
	#   use different package managers
	# - SuSE has three (!) package managers that are all in use
	#   and it seems to be by design (!?)
	# - I've seen apt-get work with dpkg, and I've seen apt-get work with rpm
	# - MacOS X has no 'standard' software packaging (the App store??)
	#   There are ports, fink, brew. I prefer 'brew'
	# - The *BSDs have both pkg_add and ports, and I have heard about rpm-based
	#   FreeBSD as well
	#
	
	platform = os.uname()[0]
	
	if platform == 'Linux':
		verbose('detected platform Linux')
		
		stat = synctool_stat.SyncStat()
		
		# use release file to detect Linux distro,
		# and choose package manager based on that
		
		for (release_file, pkgmgr) in LINUX_PACKAGE_MANAGERS:
			stat.stat(release_file)
			if stat.exists():
				verbose('detected %s' % release_file)
				verbose('choosing package manager %s' % pkgmgr)
				synctool_param.PACKAGE_MANAGER = pkgmgr
				return
		
		stderr('unknown Linux distribution')
	
	elif platform == 'Darwin':			# assume MacOS X
		verbose('detected platform MacOS X')
		# some people like port
		# some like fink
		# I like brew
		verbose('choosing package manager brew')
		synctool_param.PACKAGE_MANAGER = 'brew'
	
	elif platform in ('NetBSD', 'OpenBSD', 'FreeBSD'):
		verbose('detected platform %s' % platform)
		
		# choose pkg_add
		# I know there are ports, but you can 'make' those easily in *BSD
		
		verbose('choosing package manager pkg_add')
		synctool_param.PACKAGE_MANAGER = 'pkg_add'
	
	# platforms that are not supported yet, but I would like to support
	# or well, most of them
	# Want to know more OSes? See the source of autoconf's config.guess
	
	elif platform in ('4.4BSD', '4.3bsd', 'BSD/OS', 'SunOS', 'AIX', 'OSF1',
		'HP-UX', 'HI-UX', 'IRIX', 'UNICOS', 'UNICOS/mp', 'ConvexOS', 'Minix',
		'Windows_95', 'Windows_NT', 'CYGWIN', 'MinGW',
		'LynxOS', 'UNIX_System_V', 'BeOS', 'TOPS-10', 'TOPS-20'):
		verbose('detected platform %s' % platform)
		stderr('synctool package management under %s is not yet supported' % platform)
	
	else:
		stderr("unknown platform '%s'" % platform)


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
	
	synctool_lib.QUIET = not synctool_lib.VERBOSE
	
	pkg = package_manager()
	
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
