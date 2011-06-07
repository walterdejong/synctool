#! /bin/sh
#
#	bootstrap-synctool-client.sh
#
#	Sets up a client for synctooling
#

VERSION=4.3

if [ $# -le 0 ]
then
	echo "usage: ${0##*/} <host> [..]"
	echo "This initializes synctool on the host"
	exit 1
fi

UID=`id -u`

if [ $UID -ne 0 ]
then
	echo "must be root"
	exit 1
fi

if [ ! -f synctool-${VERSION}.tar.gz ]
then
	echo "can't find synctool-${VERSION}.tar.gz"
	echo "it should be present in the current working directory"
	exit 1
fi

for host in `synctool-config -lf`
do
	echo "copying tarball to ${host}:/tmp/"
	scp synctool-${VERSION}.tar.gz ${host}:/tmp/
	echo "running make client_install on $host"
	ssh -q ${host} "( cd /tmp && tar xf /tmp/synctool-${VERSION}.tar.gz && cd /tmp/synctool-${VERSION}/src && make client_install )"
done

# EOB
