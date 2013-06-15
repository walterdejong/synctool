#! /bin/sh
#
#	setup.sh	WJ113
#
#   synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

PATH=/bin:/sbin:/usr/bin:/usr/sbin

# FIXME double check this script, because I changed the dir structure again

# FIXME PREFIX and '--prefix=' is wrong; use 'rootdir='
PREFIX=/opt/synctool

DRY_RUN="yes"
UNINSTALL="no"
BUILD_DOCS="no"

PROGS="synctool_master.py synctool_master_pkg.py synctool_launch.py
synctool_ssh.py synctool_scp.sh synctool_ping.py synctool_config.py
synctool_aggr.py synctool_client.py synctool_pkg.py"

LAUNCHER="synctool_launch.py"

LIBS="__init__.py aggr.py config.py configparser.py lib.py nodeset.py
object.py overlay.py param.py pkgclass.py stat.py unbuffered.py update.py"

LIBS_PKG="__init__.py aptget.py brew.py bsdpkg.py pacman.py yum.py zypper.py"

DOCS="chapter1.html chapter2.html chapter3.html chapter4.html chapter5.html
thank_you.html footer.html header.html toc.html single.html synctool_doc.css
synctool_logo.jpg synctool_logo_large.jpg"

SYMLINKS="synctool synctool-pkg dsh-pkg synctool-ssh dsh synctool-scp dcp
synctool-ping dsh-ping synctool-config synctool-aggr dsh-aggr"


if test "x$1" = x
then
	echo "setup.sh: error: expected command-line options"
	echo "setup.sh: use --help to show usage"
	exit 1
fi

# parse command-line options
# thanks to "configure" ...

prev=
for option
do
	if test -n "$prev"
	then
		eval "$prev=\$option"
		prev=
		continue
	fi

	case "$option" in
		-*=*)
			optarg=`echo "$option" | sed 's/[-_a-zA-Z0-9]*=//'`
			;;

		*)
			optarg=
			;;
	esac

	case "$option" in
		-prefix | --prefix )
			prev="PREFIX"
			;;

		-prefix=* | --prefix=*)
			PREFIX="$optarg"
			;;

		--build-docs)
			BUILD_DOCS="yes"
			;;

		-f | --fix)
			DRY_RUN="no"
			;;

		-h | -help | --help)
			cat << EOF
usage: setup.sh [options]
options:
  -h, --help        Display this information
  -f, --fix         Do the installation

  --prefix=PREFIX   Install synctool under PREFIX directory
  --build-docs      Also install documentation
                    This depends on m4 and bash
  --uninstall       Remove synctool from system

The default prefix is $PREFIX

By default setup.sh does a DRY RUN, use -f or --fix to
really setup synctool on the master node

synctool by Walter de Jong <walter@heiho.net> (c) 2003-2013
EOF
			exit 1
			;;

		-uninstall | --uninstall)
			UNINSTALL="yes"
			;;

		-*)
			echo "setup.sh: error: invalid option $option; use --help to show usage"
			exit 1
			;;

		*)
			echo "setup.sh: error: invalid argument $option; use --help to show usage"
			exit 1
			;;
	esac
done

makedir() {
	if test "x$DRY_RUN" = "xno"
	then
		mkdir -m $1 -p "$2"

		if test ! -d "$2"
		then
			echo "setup.sh: error: failed to create directory: $2"
			exit 2
		fi
	fi
}

remove_links() {
	for link in $SYMLINKS synctool-master
	do
		rm -f "$PREFIX/bin/$link"
	done
}

makelinks() {
	remove_links

	for link in $SYMLINKS
	do
		ln -s $LAUNCHER "$PREFIX/bin/$link"

		if test ! -e "$PREFIX/bin/$link"
		then
			echo "setup.sh: error: failed to create symlink $PREFIX/bin/$link"
			exit 3
		fi
	done
}

install_progs() {
	echo "installing programs"

	if test "x$DRY_RUN" = "xno"
	then
		makedir 755 "$PREFIX/bin"
		install -m 755 $LAUNCHER "$PREFIX/bin"

		makedir 755 "$PREFIX/sbin"
		install -m 755 $LAUNCHER "$PREFIX/sbin"

		makelinks
	fi
}

install_libs() {
	echo "installing modules"

	if test "x$DRY_RUN" = "xno"
	then
		makedir 755 "$PREFIX/lib/synctool/pkg"
		install -m 644 $LIBS "$PREFIX/lib/synctool"
		install -m 644 $PKG_LIBS "$PREFIX/lib/synctool/pkg"
	fi
}

install_docs() {
	if test "x$BUILD_DOCS" = "xyes"
	then
		echo "installing $PREFIX/doc"

		if test "x$DRY_RUN" = "xno"
		then
			makedir 755 "$PREFIX/doc"
			( cd doc && ./build.sh )
			install -m 644 $DOCS "$PREFIX/doc"
		fi
	fi
}

do_install() {
	# can I find the sources?

	if ! test -f src/synctool/overlay.py
	then
		echo "setup.sh: error: unable to find my sources"
		echo "setup.sh: are you in the top synctool source directory?"
		exit 4
	fi

	if test "x$DRY_RUN" = "xyes"
	then
		echo "installing synctool (dry-run)"
	else
		echo "installing synctool"
	fi

	if test -e "$PREFIX/sbin/synctool"
	then
		echo "Detected an old synctool installation under $PREFIX"
		echo "You should move it out of the way first"
		exit 1
	fi

	if test -e "$PREFIX/bin/synctool_master.py"
	then
		echo "Detected an previous install of synctool under $PREFIX"
		echo "You should move it out of the way or uninstall with:"
		echo "  setup.sh --prefix=$PREFIX --uninstall"
		exit 1
	fi

	install_progs
	install_clientprogs
	install_libs
	install_docs

	echo "making $PREFIX/var"
	makedir 700 "$PREFIX/var"
	echo "making $PREFIX/var/overlay"
	makedir 755 "$PREFIX/var/overlay"
	echo "making $PREFIX/var/delete"
	makedir 750 "$PREFIX/var/delete"

	# FIXME mkdir etc/
	echo "copying -> $PREFIX/etc/synctool.conf.example"
	if test "x$DRY_RUN" = "xno"
	then
		install -m 644 synctool.conf.example "$PREFIX/etc"
	fi

	if test -f "x$PREFIX" != "x/var/lib/synctool"
	then
		if test -d "/var/lib/synctool"
		then
			echo
			echo "warning: /var/lib/synctool is obsolete"
			echo "You should migrate /var/lib/synctool/overlay/ and delete/"
			echo "to $PREFIX/var/overlay/ and delete/"
			echo "Note that scripts/ and tasks/ have been obsoleted"
		fi
	fi

	if test -f "/var/lib/synctool/synctool.conf"
	then
		echo
		echo "warning: /var/lib/synctool/synctool.conf is obsolete"
		echo "You should migrate to $PREFIX/etc/synctool.conf"
	fi

	if test "x$DRY_RUN" = "xno"
	then
		echo
		echo "Please add $PREFIX to your PATH"
		echo "and edit $PREFIX/etc/synctool.conf to suit your needs"
		echo
	fi
}

remove_progs() {
	echo "removing synctool from $PREFIX/bin"
	if test "x$DRY_RUN" = "xno"
	then
		remove_links

		for prog in $PROGS
		do
			rm -f "$PREFIX/bin/$prog"
		done
	fi
}

remove_client_progs() {
	echo "removing synctool from $PREFIX/sbin"
	if test "x$DRY_RUN" = "xno"
	then
		for prog in $CLIENT_PROGS
		do
			rm -f "$PREFIX/sbin/$prog"
		done
	fi
}

remove_libs() {
	echo "removing synctool from $PREFIX/lib"
	if test "x$DRY_RUN" = "xno"
	then
		for lib in $PKG_LIBS
		do
			rm -f "$PREFIX/lib/synctool/pkg/$lib"
		done
		rmdir "$PREFIX/lib/synctool/pkg"

		for lib in $LIBS
		do
			rm -f "$PREFIX/lib/synctool/$lib"
		done
		rmdir "$PREFIX/lib/synctool/lib"
		rmdir "$PREFIX/lib/synctool"
	fi
}

remove_docs() {
	if test -d "$PREFIX/doc"
	then
		echo "removing synctool from $PREFIX/doc"
		if test "x$DRY_RUN" = "xno"
		then
			for doc in $DOCS
			do
				rm -f "$PREFIX/doc/$doc"
			done
		fi
	fi
}

remove_overlay() {
	# do not delete any data
	# just try to remove any empty directories

	if test "x$DRY_RUN" = "xno"
	then
		rmdir "$PREFIX/var/overlay/all" 2>/dev/null
		rmdir "$PREFIX/var/overlay" 2>/dev/null
		rmdir "$PREFIX/var/delete/all" 2>/dev/null
		rmdir "$PREFIX/var/delete" 2>/dev/null
		rmdir "$PREFIX/var" 2>/dev/null
	fi

	if test -d "$PREFIX/var/overlay"
	then
		echo "leaving behind $PREFIX/var/overlay/"
	fi
	if test -d "$PREFIX/var/delete"
	then
		echo "leaving behind $PREFIX/var/delete/"
	fi
}

remove_dirs() {
	echo "cleaning up directories"
	if test "x$DRY_RUN" = "xno"
	then
		# try to remove empty directories

		rmdir "$PREFIX/sbin" 2>/dev/null
		rmdir "$PREFIX/bin" 2>/dev/null
		rmdir "$PREFIX/lib" 2>/dev/null
		rmdir "$PREFIX/doc" 2>/dev/null
		rmdir "$PREFIX" 2>/dev/null

		rmdir /tmp/synctool 2>/dev/null
	fi

	if test -d "$PREFIX"
	then
		echo "leaving behind $PREFIX/"
	fi
}

do_uninstall() {
	if test ! -d "$PREFIX"
	then
		echo "setup.sh: error: so such directory: $PREFIX"
		exit 5
	fi

	remove_progs
	remove_client_progs
	remove_libs
	remove_docs
	remove_overlay
	remove_dirs

	if test -f "$PREFIX/etc/synctool.conf"
	then
		echo "leaving behind $PREFIX/etc/synctool.conf"
	fi
}

if test "x$UNINSTALL" = "xyes"
then
	do_uninstall
else
	do_install
fi

if test "x$DRY_RUN" = "xyes"
then
	echo
	echo "This was a DRY RUN, actions not performed"
	echo
fi

# EOB
