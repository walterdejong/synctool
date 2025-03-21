#
#   synctool.main.client_pkg.py WJ111
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool package manager. It runs on the client node'''

import os
import sys
import getopt

from typing import List
from synctool.pkgclass import SyncPkg

import synctool.config
import synctool.lib
from synctool.lib import verbose, stderr, error, warning
from synctool.main.wrapper import catch_signals
import synctool.param
import synctool.syncstat

# hardcoded name because otherwise we get "synctool_pkg.py"
PROGNAME = 'synctool-client-pkg'

# enums for command-line options
ACTION_INSTALL = 1
ACTION_REMOVE = 2
ACTION_LIST = 3
ACTION_UPDATE = 4
ACTION_UPGRADE = 5
ACTION_CLEAN = 6

# map of /etc/os-release ID|ID_LIKE -> package manager
PKGMGR_BY_OS_ID = {'alpine': 'apk',
                   'arch': 'pacman',
                   'debian': 'apt-get',
                   'fedora': 'dnf',
                   'freebsd': 'pkg',
                   'opensuse': 'zypper',
                   'rhel': 'dnf',
                   'suse': 'zypper',
                   'ubuntu': 'apt-get'}

# list of other Linux package managers (that may or may not be supported yet)
LINUX_PACKAGE_MANAGERS = (('/etc/gentoo-release', 'portage'),
                          ('/etc/slackware-version', 'swaret'),
                          ('/etc/yellowdog-release', 'yum'),
                          ('/etc/mandrake-release', 'urpmi'))


class Options:
    '''represents program options'''

    def __init__(self) -> None:
        '''initialize instance'''

        self.action = 0
        self.packages: List[str] = []


def package_manager() -> SyncPkg:
    '''return instance of SyncPkg installer class

    Exits the program on error, when it fails to detect
    the system package manager
    '''

    detected = False

    if not synctool.param.PACKAGE_MANAGER:
        detect_installer()

        if not synctool.param.PACKAGE_MANAGER:
            error('failed to detect package management system')
            stderr('please configure it in synctool.conf')
            sys.exit(1)

        detected = True

    for mgr in synctool.param.KNOWN_PACKAGE_MANAGERS:
        if synctool.param.PACKAGE_MANAGER == mgr:
            short_mgr = mgr.replace('-', '')

            # load the module
            module = __import__('synctool.pkg.%s' % short_mgr)

            # step through module hierarchy
            module = getattr(module, 'pkg')
            module = getattr(module, short_mgr)

            # find the package manager class
            pkgclass = getattr(module, 'SyncPkg%s' % short_mgr.capitalize())

            # instantiate the class
            return pkgclass()

    if detected:
        error('package manager %s is not supported yet' %
              synctool.param.PACKAGE_MANAGER)
    else:
        error("unknown package manager defined: '%s'" %
              synctool.param.PACKAGE_MANAGER)

    sys.exit(1)


def detect_installer_from_os_release() -> str:
    '''Attempt to detect the package manager from /etc/os-release
    Returns the package manager string
    Raises KeyError if unknown system
    '''

    try:
        with open('/etc/os-release', encoding='utf-8') as file:
            lines = file.readlines()

        lineno = 0
        for line in lines:
            lineno += 1
            line = line.strip()
            if not line:
                continue
            if line[0] == '#':
                continue

            try:
                var, value = line.split('=', maxsplit=1)
            except ValueError:
                verbose('error: /etc/os-release: error in line {}: {!r}'.format(lineno, line))
                break

            value = value.strip("'\"")

            if var == 'ID':
                try:
                    distro = value
                    pkgmgr = PKGMGR_BY_OS_ID[distro]
                    verbose('os-release: {} uses package manager: {}'.format(distro, pkgmgr))
                    return pkgmgr
                except KeyError:
                    # try ID_LIKE (if it is present)
                    continue

            elif var == 'ID_LIKE':
                distro_list = value.split()
                for distro in distro_list:
                    try:
                        pkgmgr = PKGMGR_BY_OS_ID[distro]
                        verbose('os-release: {} uses package manager: {}'.format(distro, pkgmgr))
                        return pkgmgr
                    except KeyError:
                        continue

    except OSError as err:
        verbose('error: /etc/os-release: {}'.format(str(err)))

    raise KeyError('unable to determine package manager from /etc/os-release')


def detect_installer() -> None:
    '''Attempt to detect the operating system and package system'''

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
    # - I've seen apt-get work with dpkg, and/or with rpm
    # - OS X has no 'standard' software packaging (the App store??)
    #   There are ports, fink, brew. I prefer 'brew'
    # - FreeBSD has pkg and ports
    # - Most other BSDs have pkg_add and ports

    try:
        synctool.param.PACKAGE_MANAGER = detect_installer_from_os_release()
        return
    except KeyError:
        # try legacy method
        pass

    platform = os.uname()[0]

    if platform == 'Linux':
        verbose('detected platform Linux')

        stat = synctool.syncstat.SyncStat()

        # use release file to detect Linux distro,
        # and choose package manager based on that

        for (release_file, pkgmgr) in LINUX_PACKAGE_MANAGERS:
            stat.stat(release_file)
            if stat.exists():
                verbose('detected %s' % release_file)
                verbose('choosing package manager %s' % pkgmgr)
                synctool.param.PACKAGE_MANAGER = pkgmgr
                return

        warning('unknown Linux distribution')

    elif platform == 'Darwin':            # assume OS X
        verbose('detected platform OS X')
        # some people like port
        # some people like fink
        # I like homebrew
        verbose('choosing package manager brew')
        synctool.param.PACKAGE_MANAGER = 'brew'

    elif platform == 'FreeBSD':
        verbose('detected platform FreeBSD')
        synctool.param.PACKAGE_MANAGER = 'pkg'

    elif platform in ('NetBSD', 'OpenBSD'):
        verbose('detected platform %s' % platform)

        # choose bsdpkg
        # I know there are ports, but you can 'make' those easily in *BSD
        # or maybe ports will be a seperate module in the future

        verbose('choosing package manager bsdpkg')
        synctool.param.PACKAGE_MANAGER = 'bsdpkg'

    # platforms that are not supported yet, but I would like to support
    # or well, most of them
    # Want to know more OSes? See the source of autoconf's config.guess

    elif platform in ('4.4BSD', '4.3bsd', 'BSD/OS', 'SunOS', 'AIX', 'OSF1',
                      'HP-UX', 'HI-UX', 'IRIX', 'UNICOS', 'UNICOS/mp',
                      'ConvexOS', 'Minix', 'Windows_95', 'Windows_NT',
                      'CYGWIN', 'MinGW', 'LynxOS', 'UNIX_System_V', 'BeOS',
                      'TOPS-10', 'TOPS-20'):
        verbose('detected platform %s' % platform)
        warning('synctool package management under %s is not yet supported' %
                platform)

    else:
        warning("unknown platform '%s'" % platform)


def there_can_be_only_one() -> None:
    '''print usage information about actions'''

    print('''Specify only one of these options:
  -l, --list   [PACKAGE ...]     List installed packages
  -i, --install PACKAGE [..]     Install package
  -R, --remove  PACKAGE [..]     Uninstall package
  -u, --update                   Update the database of available packages
  -U, --upgrade                  Upgrade all outdated packages
  -C, --clean                    Cleanup caches of downloaded packages
''')
    sys.exit(1)


def usage() -> None:
    '''print usage information'''

    print('usage: %s [options] [package [..]]' % PROGNAME)
    print('options:')
    print('  -h, --help                     Display this information')
    print('  -c, --conf=FILE                Use this config file')
    print(('                                 (default: %s)' %
           synctool.param.DEFAULT_CONF))
    print('''  -l, --list   [PACKAGE ...]     List installed packages
  -i, --install PACKAGE [..]     Install package
  -R, --remove  PACKAGE [..]     Uninstall package
  -u, --update                   Update the database of available packages
  -U, --upgrade                  Upgrade all outdated packages
  -C, --clean                    Cleanup caches of downloaded packages

  -f, --fix                      Perform upgrade (otherwise, do dry-run)
  -v, --verbose                  Be verbose
      --unix                     Output actions as unix shell commands
  -m, --manager PACKAGE_MANAGER  (Force) select this package manager

Supported package managers are:''')

    # print list of supported package managers
    # format it at 78 characters wide
    print(' ', end=' ')
    npms = 2
    for pkg in synctool.param.KNOWN_PACKAGE_MANAGERS:
        if npms + len(pkg) + 1 <= 78:
            npms = npms + len(pkg) + 1
            print(pkg, end=' ')
        else:
            npms = 2 + len(pkg) + 1
            print()
            print(' ', pkg, end=' ')

    print('''

The package list must be given last
Note that --upgrade does a dry run unless you specify --fix
''')


def get_options() -> Options:
    '''parse command-line options'''

    # pylint: disable=too-many-statements,too-many-branches

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hc:iRluUCm:fvq',
                                   ['help', 'conf=', 'list', 'install',
                                    'remove', 'update', 'upgrade', 'clean',
                                    'cleanup', 'manager=', 'masterlog',
                                    'fix', 'verbose', 'unix', 'quiet'])
    except getopt.GetoptError as reason:
        print('%s: %s' % (PROGNAME, reason))
        # usage()
        sys.exit(1)

    options = Options()

    # first read the config file
    for opt, arg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-c', '--conf'):
            synctool.param.CONF_FILE = arg
            continue

    synctool.config.read_config()
    # synctool.nodeset.make_default_nodeset()

    # then process the other options

    for opt, arg in opts:
        if opt in ('-h', '--help', '-?', '-c', '--conf'):
            # already done
            continue

        if opt in ('-i', '--install'):
            if options.action > 0 and options.action != ACTION_INSTALL:
                there_can_be_only_one()

            options.action = ACTION_INSTALL
            continue

        if opt in ('-R', '--remove'):
            if options.action > 0 and options.action != ACTION_REMOVE:
                there_can_be_only_one()

            options.action = ACTION_REMOVE
            continue

        if opt in ('-l', '--list'):
            if options.action > 0 and options.action != ACTION_LIST:
                there_can_be_only_one()

            options.action = ACTION_LIST
            continue

        if opt in ('-u', '--update'):
            if options.action > 0 and options.action != ACTION_UPDATE:
                there_can_be_only_one()

            options.action = ACTION_UPDATE
            continue

        if opt in ('-U', '--upgrade'):
            if options.action > 0 and options.action != ACTION_UPGRADE:
                there_can_be_only_one()

            options.action = ACTION_UPGRADE
            continue

        if opt in ('-C', '--clean', '--cleanup'):
            if options.action > 0 and options.action != ACTION_CLEAN:
                there_can_be_only_one()

            options.action = ACTION_CLEAN
            continue

        if opt in ('-m', '--manager'):
            if arg not in synctool.param.KNOWN_PACKAGE_MANAGERS:
                error("unknown or unsupported package manager '%s'" % arg)
                sys.exit(1)

            synctool.param.PACKAGE_MANAGER = arg
            continue

        if opt == '--masterlog':
            # used by the master for message logging purposes
            synctool.lib.MASTERLOG = True
            continue

        if opt in ('-f', '--fix'):
            synctool.lib.DRY_RUN = False
            continue

        if opt in ('-v', '--verbose'):
            synctool.lib.VERBOSE = True
            continue

        if opt == '--unix':
            synctool.lib.UNIX_CMD = True
            continue

        if opt in ('-q', '--quiet'):
            synctool.lib.QUIET = True
            continue

    if not options.action:
        usage()
        sys.exit(1)

    if options.action in (ACTION_LIST, ACTION_INSTALL, ACTION_REMOVE):
        options.packages = args

        if options.action in (ACTION_INSTALL, ACTION_REMOVE) and not args:
            error('options --install and --remove require a package name')
            sys.exit(1)

    elif args is not None and args:
        error('excessive arguments on command line')
        sys.exit(1)

    # disable dry-run unless --upgrade was given
    # a normal --upgrade will do a dry-run and
    # show what upgrades are available
    # --upgrade -f will do the upgrade
    #
    # The other actions will execute immediatly
    if options.action != ACTION_UPGRADE:
        synctool.lib.DRY_RUN = False

    return options


@catch_signals
def main() -> int:
    '''run the program'''

    synctool.param.init()

    opts = get_options()

    synctool.lib.QUIET = not synctool.lib.VERBOSE

    if synctool.param.NODENAME in synctool.param.IGNORE_GROUPS:
        # this is only a warning ...
        # you can still run synctool-pkg on the client by hand
        warning('warning: node %s is disabled in the config file' %
                synctool.param.NODENAME)

    pkg = package_manager()

    if opts.action == ACTION_LIST:
        pkg.show_list(opts.packages)

    elif opts.action == ACTION_INSTALL:
        pkg.install(opts.packages)

    elif opts.action == ACTION_REMOVE:
        pkg.remove(opts.packages)

    elif opts.action == ACTION_UPDATE:
        pkg.update()

    elif opts.action == ACTION_UPGRADE:
        pkg.upgrade()

    elif opts.action == ACTION_CLEAN:
        pkg.clean()

    else:
        raise RuntimeError('BUG: unknown action code %d' % opts.action)
    return 0

# EOB
