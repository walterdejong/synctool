#!/bin/ksh

#
# Toplevel rsynctool script, aster, suse, version
# Last modified Tue Jun. 20 2006, HJS:
#	SUSE Linux version, adapted from "aster" version
#	The SUSE version has its own distribution, with
#	its own root and config file. So now we have
#	"teras", "aster", "suse".

PROGNAM=${0##*/}
AWK=/bin/awk
SED=/bin/sed
CAT=/bin/cat
HOSTNAME=/bin/hostname
IS_ON=/usr/sara/bin/checkconfig
SYNCTOOL=/usr/sara/bin/synctool.sh
RSYNCTOOL=/usr/sara/bin/rsynctool-single-suse.sh
CONFIGFILE=/var/lib/synctool/suse10/synctool.conf

errmsg()
{
	echo "${PROGNAM}: $*" >&2
}

usage()
{
$CAT << EOF >&2
usage: $PROGNAM [ -h | --host hostlist ] [ ${SYNCTOOL##*/} options ]
       $PROGNAM -? | --help
       The first form of the command must be run on the rsynctool server
       and, for remote hosts, will perform a server push of the current
       ${SYNCTOOL##*/} distribution tree. Subsequently, ${SYNCTOOL##*/}
       is triggered to run with the new tree.
       With the "-h" or "--host" option a comma separated list of
       hosts to run on can be specified. If this option is ommitted,
       ${SYNCTOOL##*/} is run on ALL hosts defined in the configuration
       file ($CONFIGFILE).
       Note that the "-h" or "--host" option with its hostlist argument
       must be the FIRST one to be specified on the  ${PROGNAM} command line,
       otherwise they will be passed down as arguments to the underlying
       ${SYNCTOOL##*/} command.
       The "-?", or "--help", option is just for displaying this
       message, plus the usage message of the underlying ${SYNCTOOL##*/}
       command.
EOF
}

if [ "$1" = "-?" -o "$1" = "--help" ]
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
	errmsg "This command must be run on the rsynctool server only"
	usage
	exit 1
fi

LOCALHOST=`$HOSTNAME -s`
if [ $? -ne 0 ]
then
	errmsg "Failed to determine (short) local host name"
	exit
fi

if [ ! -r $CONFIGFILE ]
then
	errmsg "Cannot read configuration file $CONFIGFILE"
	exit 1
fi

if [ "$1" = "-h" -o "$1" = "--host" ]
then
	if [ -z "$2" ]
	then
		errmsg "option \"$1\" needs an argument"
		usage
		exit 1
	fi

	#
	# Explicit hosts must be in a comma separated list
	# (no spaces allowed) Following the --host switch.
	#  Each host specified is checked for occurrence
	# in the configuration file.
	# 
	HOSTLIST=`echo $2 | $AWK '{ gsub(",", " "); print; }'`
	## DEBUG ## echo $HOSTLIST

	for i in $HOSTLIST
	do
		## DEBUG ## echo $i
		j=`echo $i | $AWK -v chk=$i '$1 == "host" && $2 == chk { print $2; }' $CONFIGFILE`	
		if [ $? -ne 0 ]
		then
			errmsg "Error parsing configuration file $CONFIGFILE"
			exit 1
		fi
		## DEBUG ## echo $j
		if [ -z "$j" ]
		then
			errmsg "Host \"$i\" not found in configuration file $CONFIGFILE"
			exit 1
		fi	
	done 
	shift 2
fi

if [ -z "$HOSTLIST" ]
then
	#
	# No explicit hosts specified, implies all hosts defined in the config file.
	# So, extract all.
	#
	HOSTLIST=`$AWK '$1 == "host" && NF >= 2 { print $2; }' $CONFIGFILE`
	if [ $? -ne 0 ]
	then
		errmsg "Error parsing configuration file $CONFIGFILE"
		exit 1
	fi
	if [ -z "$HOSTLIST" ]
	then
		errmsg "No valid hosts after consulting $CONFIGFILE"
		exit 1
	fi
fi

# rsynctool-single uses this
export CONFIGFILE

for host in $HOSTLIST
do
	if [ "$host" == "$LOCALHOST" ]
	then
		echo "Please do not run on the server $host"
		exit 1

		#
		# At present this cannot happen in the aster version, since in
		# the above code all hosts are checked against the aster synctool
		# configuration and  the local server host is not a valid host
		# since, being an  Irix (teras) system rather than an Altix (aster),
		# it does not occur in that file.
		#
		$SYNCTOOL $* | $SED "s/^/$host: /" &
	else
		$RSYNCTOOL $host $* | $SED "s/^/$host: /" &
	fi
done
wait

# EOB

