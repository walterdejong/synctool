#! /bin/ksh

#
# Single host rsynctool, aster, suse (PP4) version.
# WJ105
# Last modified tue Jun. 20 2006, HJS
#
# Note that this differs from the teras version, not only in
# repository but also, in the paths of some commands, such as
# rsync, that have a local and a remote version. This is so
# because for the aster version, the server and the client run
# on different platforms. Since the server is currently an
# Irix system, # these differences do not exist for the teras
# version.
#

PROGNAM=${0##*/}
IS_ON=/usr/sara/bin/checkconfig
CAT=/bin/cat
AWK=/usr/bin/awk
RSYNC=/usr/bin/rsync
REMOTE_RSYNC=/usr/bin/rsync
SSH="/usr/bin/ssh -q"
SYNCTOOL=/usr/sara/bin/synctool.sh

CONFIGFILE=${CONFIGFILE:=/var/lib/synctool/suse10/synctool.conf}

REPOS=`$AWK '/^masterdir / { print $2 }' $CONFIGFILE`


errmsg()
{
	echo "${PROGNAM}: $*" >&2
}

usage()
{
$CAT << EOF >&2
usage: $PROGNAM <host> [ ${SYNCTOOL##*/} options ]
       $PROGNAM -? | --help
       The first form of this command must be run on the
       rsynctool server, and will perform a server push of the
       current ${SYNCTOOL##*/} distribution tree to the specified
       remote host, and subsequently trigger a ${SYNCTOOL##*/} run
       there.
       The "-?" , or "--help", option is just for displaying this
       message, plus the usage message of the underlying
       ${SYNCTOOL##*/} command.
       Note that the "host" parameter must be the FIRST argument to
       be specified on the $PROGNAM command line, since subsequent
       options will all be passed down the ${SYCNTOOL##*/} command. 
EOF
}


if [ -z "$REPOS" ]
then
	errmsg no masterdir defined in $CONFIGFILE
	exit 1
fi

if [ -z "$1" ]
then
	errmsg "No host specified"
	usage
	exit 1
fi

if [ "$1" == "-?" -o "$1" == "--help" ]
then
	usage
	echo "" >&2
	echo "== Options that can be passed on to ${SYNCTOOL##*/} ==" >&2
	echo "" >&2
	$SYNCTOOL --help >&2
	exit 0
fi

if ! $IS_ON rsynctool
then
	errmsg "This command must be run on the rsynctool server" 
	exit 1
fi

HOST=$1
shift

if ! $RSYNC -e $SSH --rsync-path=$REMOTE_RSYNC -ar --delete $REPOS/ $HOST:$REPOS/
then
	errmsg "Failed to rsync synctool tree to host $HOST"
	exit 1
fi

if ! $SSH $HOST $SYNCTOOL --conf=$CONFIGFILE $*
then
	errmsg "Failed to run $SYNCTOOL via ssh on host $HOST"
	exit 1
fi

# EOB

