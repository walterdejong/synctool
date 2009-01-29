#!/bin/bash

#
# Toplevel rsynctool script, Altix, SuSE version.
# Last modified HJS 20081112:
#	Adapted to handle a new generic feature in the configuration file.
#	An interface specification can now be appended as a field on the
#	host defining record in the configuration file. This feature was
#	added to accomodate complex configurations of multihomed hosts
#	in which the rsynctool master cannot or should NOT use an interface
#	that equals the official hostname (i.e. that what the target host
#	specifies it to be when "hostname" -s is run). The new and optional
#	"interface:" specification is used to direct the rsyncmatser to the
#	proper interface that should be used for all synctool management
#	network traffic.
# 
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
	exit 1
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
		j=`echo $i | \
		$AWK -v chk=$i '$1 == "host" && $2 == chk {
			if ($NF ~ /^interface:/) {
				print substr($NF, 11);
			}
			else {
				print $2;
			}
		}' $CONFIGFILE`	
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
		if [ -z "$HOSTINTERFACELIST" ]
		then
			HOSTINTERFACELIST=$j
		else
			HOSTINTERFACELIST="$HOSTINTERFACELIST $j"
		fi
		if [ "$i" != "$j" ]
		then
			echo "$PROGNAM: Using interface $j for host $i" >&2
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
	HOSTINTERFACELIST=`$AWK -v PROGNAM=$PROGNAM '$1 == "host" && NF >= 2 {
		if ($NF ~ /^interface/) {
			interface = substr($NF, 11);
			print interface;
			print PROGNAM ": Using interface " interface " for host "$2 | "/bin/cat 1>&2";
		}
		else {
			print $2;
		}
	}' $CONFIGFILE`
	if [ $? -ne 0 ]
	then
		errmsg "Error parsing configuration file $CONFIGFILE"
		exit 1
	fi
	if [ -z "$HOSTINTERFACELIST" ]
	then
		errmsg "No valid hosts after consulting $CONFIGFILE"
		exit 1
	fi
fi

# rsynctool-single uses this
export CONFIGFILE

for host in $HOSTLIST $HOSTINTERFACELIST
do
	if [ "$host" == "$LOCALHOST" ]
	then
		errmsg "Do not run $RSYNCTOOL on the rsync server itself ($host)"
		exit 1
	fi
done

for host in $HOSTINTERFACELIST
do
	$RSYNCTOOL $host $* | sed "s/^/${host}: /" &
done
wait

# EOB
