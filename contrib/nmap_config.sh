#! /bin/sh

if [ -z "$1" -o "$1" = "--help" -o "$1" = "-?" ]
then
	echo "usage: ${0##*/} <network address/bits> [--numeric]"
	echo "this uses nmap to scan for nodes on the management network"
	echo "the network address is easily obtained with 'ip route show'"
	exit 0
fi

#NETWORK=192.168.1.0/24
NETWORK=$1

if [ "$2" = "--numeric" -o "$2" = "-n" ]
then
	nmap -sP $NETWORK 2>/dev/null | awk '/^Host / { split($2, arr, "."); node=arr[1]; sub(/\(/, "", $3); sub(/\)/, "", $3); print "node " node " all interface:" $3 ; }'
else
	nmap -sP $NETWORK 2>/dev/null | awk '/^Host / { split($2, arr, "."); node=arr[1]; print "node " node " all interface:" $2 ; }'
fi

# EOB

