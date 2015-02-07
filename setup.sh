#! /bin/sh
#
#	setup.sh	WJ113
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

DEFAULT_INSTALL_ROOT="/opt/synctool"
INSTALL_ROOT="$DEFAULT_INSTALL_ROOT"

DRY_RUN="yes"
UNINSTALL="no"
BUILD_DOCS="no"

PROGS="synctool_master.py synctool_launch.py
dsh.py dsh_cp.py dsh_ping.py dsh_pkg.py synctool_config.py
synctool_aggr.py synctool_client.py synctool_client_pkg.py
synctool_template.py synctool_list.py"

LAUNCHER="synctool_launch.py"

LIBS="__init__.py aggr.py config.py configparser.py lib.py multiplex.py
nodeset.py object.py overlay.py parallel.py param.py pkgclass.py pwdgrp.py
range.py syncstat.py unbuffered.py update.py upload.py"

MAIN_LIBS="__init__.py aggr.py client.py config.py master.py dsh_pkg.py
client_pkg.py dsh_ping.py dsh_cp.py dsh.py template.py wrapper.py"

PKG_LIBS="__init__.py aptget.py brew.py bsdpkg.py pacman.py yum.py zypper.py"

DOCS="chapter1.md chapter2.md chapter3.md chapter4.md chapter5.md chapter6.md
thank_you.md toc.md footer.html header.html line.html synctool_doc.css
synctool_logo.jpg synctool_logo_large.jpg build.sh"

SYMLINKS="synctool dsh-pkg dsh dsh-cp dsh-ping synctool-config
synctool-client synctool-client-pkg synctool-template"


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
		-installdir | --installdir )
			prev="INSTALL_ROOT"
			;;

		-installdir=* | --installdir=*)
			INSTALL_ROOT="$optarg"
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
  -h, --help         Display this information
  -f, --fix          Do the installation

  --installdir=DIR   Install synctool under this directory
  --build-docs       Also build HTML documentation
                     This requires 'markdown' and 'smartypants'
  --uninstall        Remove synctool from system

The default installdir is $DEFAULT_INSTALL_ROOT
Whatever you do, do NOT put synctool directly under /usr or /usr/local
Use a _dedicated_ installdir like /opt/synctool or /home/synctool

By default setup.sh does a DRY RUN, use -f or --fix to
really setup synctool on the master node

synctool by Walter de Jong <walter@heiho.net> (c) 2003-2015
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
		rm -f "$INSTALL_ROOT/bin/$link"
	done
}

makelinks() {
	remove_links

	for link in $SYMLINKS
	do
		ln -s $LAUNCHER "$INSTALL_ROOT/bin/$link"

		if test ! -e "$INSTALL_ROOT/bin/$link"
		then
			echo "setup.sh: error: failed to create symlink $INSTALL_ROOT/bin/$link"
			exit 3
		fi
	done
}

install_progs() {
	echo "installing programs"

	if test "x$DRY_RUN" = "xno"
	then
		makedir 755 "$INSTALL_ROOT/bin"
		install -m 755 src/$LAUNCHER "$INSTALL_ROOT/bin"

		makedir 755 "$INSTALL_ROOT/sbin"
		( cd src && install -m 755 $PROGS "$INSTALL_ROOT/sbin" )

		makelinks
	fi
}

install_libs() {
	echo "installing modules"

	if test "x$DRY_RUN" = "xno"
	then
		makedir 755 "$INSTALL_ROOT/lib/synctool/pkg"
		makedir 755 "$INSTALL_ROOT/lib/synctool/main"
		( cd src/synctool && install -m 644 $LIBS "$INSTALL_ROOT/lib/synctool" )
		( cd src/synctool/main && install -m 644 $MAIN_LIBS "$INSTALL_ROOT/lib/synctool/main" )
		( cd src/synctool/pkg && install -m 644 $PKG_LIBS "$INSTALL_ROOT/lib/synctool/pkg" )
	fi
}

install_docs() {
	echo "installing documentation"

	if test "x$DRY_RUN" = "xno"
	then
		makedir 755 "$INSTALL_ROOT/doc"
		( cd doc && install -m 644 $DOCS "$INSTALL_ROOT/doc" )
		chmod +x "$INSTALL_ROOT/doc/build.sh"

		if test "x$BUILD_DOCS" = "xyes"
		then
			( cd "$INSTALL_ROOT/doc" && ./build.sh )
		fi
	fi
}

do_install() {
	FIRST=`echo "$INSTALL_ROOT" | cut -c 1`
	if test "x$FIRST" = "x~"
	then
		echo "setup.sh: error: do not use ~ paths"
		echo "please use an absolute path"
		exit 4
	fi

	if test -d "$INSTALL_ROOT"
	then
		echo "setup.sh: warning: directory already exists: $INSTALL_ROOT"
	fi

	# can I find the sources?

	if ! test -f src/synctool/overlay.py
	then
		echo "setup.sh: error: unable to find my sources"
		echo "setup.sh: are you in the top synctool source directory?"
		exit 6
	fi

	if test "x$DRY_RUN" = "xyes"
	then
		echo "installing synctool (dry-run)"
	else
		echo "installing synctool"
	fi

	if test -e "$INSTALL_ROOT/bin/synctool_master.py"
	then
		echo "Detected an previous install of synctool under $INSTALL_ROOT"
		echo "You should move it out of the way or uninstall with:"
		echo "  setup.sh --installdir=$INSTALL_ROOT --uninstall"
		exit 1
	fi

	install_progs
	install_libs
	install_docs

	echo "making $INSTALL_ROOT/scripts"
	makedir 755 "$INSTALL_ROOT/scripts"
	echo "making $INSTALL_ROOT/var"
	makedir 700 "$INSTALL_ROOT/var"
	echo "making $INSTALL_ROOT/var/overlay"
	makedir 755 "$INSTALL_ROOT/var/overlay"
	echo "making $INSTALL_ROOT/var/delete"
	makedir 750 "$INSTALL_ROOT/var/delete"
	echo "making $INSTALL_ROOT/var/purge"
	makedir 755 "$INSTALL_ROOT/var/purge"

	echo "copying -> $INSTALL_ROOT/etc/synctool.conf.example"
	if test "x$DRY_RUN" = "xno"
	then
		makedir 0755 "$INSTALL_ROOT/etc"
		install -m 644 synctool.conf.example "$INSTALL_ROOT/etc"
	fi

	if test "x$INSTALL_ROOT" != "x/var/lib/synctool"
	then
		if test -d "/var/lib/synctool"
		then
			echo
			echo "warning: /var/lib/synctool is obsolete"
			echo "You should migrate /var/lib/synctool/overlay/ and delete/"
			echo "to $INSTALL_ROOT/var/overlay/ and delete/"
			echo "Note that tasks/ has been obsoleted"
		fi
	fi

	if test -f "/var/lib/synctool/synctool.conf"
	then
		echo
		echo "warning: /var/lib/synctool/synctool.conf is obsolete"
		echo "You should migrate to $INSTALL_ROOT/etc/synctool.conf"
	fi

	if test "x$DRY_RUN" = "xno"
	then
		echo
		echo "Please add $INSTALL_ROOT/bin to your PATH"
		echo "and edit $INSTALL_ROOT/etc/synctool.conf to suit your needs"
		echo
	fi
}

remove_progs() {
	echo "removing synctool from $INSTALL_ROOT/bin"
	if test "x$DRY_RUN" = "xno"
	then
		remove_links

		rm -f "$INSTALL_ROOT/bin/$LAUNCHER" "$INSTALL_ROOT/bin/${LAUNCHER}[co]"
	fi
}

remove_client_progs() {
	echo "removing synctool from $INSTALL_ROOT/sbin"
	if test "x$DRY_RUN" = "xno"
	then
		for prog in $PROGS
		do
			rm -f "$INSTALL_ROOT/sbin/$prog" "$INSTALL_ROOT/sbin/${prog}c" "$INSTALL_ROOT/sbin/${prog}o"
		done
	fi
}

remove_libs() {
	echo "removing synctool from $INSTALL_ROOT/lib"
	if test "x$DRY_RUN" = "xno"
	then
		for lib in $PKG_LIBS
		do
			rm -f "$INSTALL_ROOT/lib/synctool/pkg/$lib" "$INSTALL_ROOT/lib/synctool/pkg/${lib}c" "$INSTALL_ROOT/lib/synctool/pkg/${lib}o"
		done
		rmdir "$INSTALL_ROOT/lib/synctool/pkg" 2>/dev/null

		for lib in $MAIN_LIBS
		do
			rm -f "$INSTALL_ROOT/lib/synctool/main/$lib" "$INSTALL_ROOT/lib/synctool/main/${lib}c" "$INSTALL_ROOT/lib/synctool/main/${lib}o"
		done
		rmdir "$INSTALL_ROOT/lib/synctool/main" 2>/dev/null

		for lib in $LIBS
		do
			rm -f "$INSTALL_ROOT/lib/synctool/$lib" "$INSTALL_ROOT/lib/synctool/${lib}c" "$INSTALL_ROOT/lib/synctool/${lib}o"
		done
		rmdir "$INSTALL_ROOT/lib/synctool/lib" 2>/dev/null
		rmdir "$INSTALL_ROOT/lib/synctool" 2>/dev/null
	fi
}

remove_docs() {
	if test -d "$INSTALL_ROOT/doc"
	then
		echo "removing synctool from $INSTALL_ROOT/doc"
		if test "x$DRY_RUN" = "xno"
		then
			for doc in $DOCS
			do
				rm -f "$INSTALL_ROOT/doc/$doc"
			done
		fi
	fi
}

remove_overlay() {
	# do not delete any data
	# just try to remove any empty directories

	if test "x$DRY_RUN" = "xno"
	then
		rmdir "$INSTALL_ROOT/var/overlay/all" 2>/dev/null
		rmdir "$INSTALL_ROOT/var/overlay" 2>/dev/null
		rmdir "$INSTALL_ROOT/var/delete/all" 2>/dev/null
		rmdir "$INSTALL_ROOT/var/delete" 2>/dev/null
		rmdir "$INSTALL_ROOT/var/purge" 2>/dev/null
		rmdir "$INSTALL_ROOT/var" 2>/dev/null
		rmdir "$INSTALL_ROOT/scripts" 2>/dev/null
	fi

	if test -d "$INSTALL_ROOT/var/overlay"
	then
		echo "leaving behind $INSTALL_ROOT/var/overlay/"
	fi
	if test -d "$INSTALL_ROOT/var/delete"
	then
		echo "leaving behind $INSTALL_ROOT/var/delete/"
	fi
	if test -d "$INSTALL_ROOT/var/purge"
	then
		echo "leaving behind $INSTALL_ROOT/var/purge/"
	fi
	if test -d "$INSTALL_ROOT/scripts"
	then
		echo "leaving behind $INSTALL_ROOT/scripts/"
	fi
}

remove_dirs() {
	echo "cleaning up directories"
	if test "x$DRY_RUN" = "xno"
	then
		rm -f "$INSTALL_ROOT/etc/synctool.conf.example"

		# try to remove empty directories

		rmdir "$INSTALL_ROOT/sbin" 2>/dev/null
		rmdir "$INSTALL_ROOT/bin" 2>/dev/null
		rmdir "$INSTALL_ROOT/etc" 2>/dev/null
		rmdir "$INSTALL_ROOT/lib" 2>/dev/null
		rmdir "$INSTALL_ROOT/doc" 2>/dev/null
		rmdir "$INSTALL_ROOT" 2>/dev/null

		rmdir /tmp/synctool 2>/dev/null
	fi

	if test -d "$INSTALL_ROOT"
	then
		echo "leaving behind $INSTALL_ROOT/"
	fi
}

do_uninstall() {
	if test ! -d "$INSTALL_ROOT"
	then
		echo "setup.sh: error: so such directory: $INSTALL_ROOT"
		exit 5
	fi

	remove_progs
	remove_client_progs
	remove_libs
	remove_docs
	remove_overlay
	remove_dirs

	if test -f "$INSTALL_ROOT/etc/synctool.conf"
	then
		echo "leaving behind $INSTALL_ROOT/etc/synctool.conf"
	fi
}

### main part ###

# check that INSTALL_ROOT is set
if test "x$INSTALL_ROOT" = "x"
then
    echo "setup.sh: invalid installdir"
    exit 1
fi

# check that INSTALL_ROOT is an absolute path
SLASH=`echo $INSTALL_ROOT | cut -b1`
if test "x$SLASH" != "x/"
then
    echo "setup.sh: installdir must be an absolute path"
    exit 1
fi

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
