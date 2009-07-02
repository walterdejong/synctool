#! /bin/sh
#
#	bootstrap-synctool-client.sh
#
#	Sets up a client for synctooling
#

SRCDIR=/var/lib/synctool/suse10/overlay/usr/sara/bin
DESTDIR=/usr/sara/bin

TMPDIR=/tmp/bootstrap-synctool.$$


if [ $# -le 0 ]
then
	echo "usage: $PROG <host> [..]"
	echo "This initializes synctool on the host"
	exit 1
fi

if [ $UID -ne 0 ]
then
	echo "must be root"
	exit 1
fi

mkdir $TMPDIR

cp $SRCDIR/synctool.sh._sara $TMPDIR/synctool.sh
cp $SRCDIR/synctool.py._sara $TMPDIR/synctool.py
cp $SRCDIR/md5sum.py._sara $TMPDIR/md5sum.py

for HOST in $*
do
# set root authorized_keys file
	ssh -q $HOST /bin/mkdir -m 0700 /root/.ssh
	scp -q /root/.ssh/id_rsa.pub $HOST:/root/.ssh/authorized_keys

# copy synctool executables
	ssh -q $HOST /bin/mkdir -m 0755 -p $DESTDIR
	scp -q $TMPDIR/* $HOST:$DESTDIR

# make dist tree dir
	ssh -q $HOST /bin/mkdir -m 0755 -p $SRCDIR
done

rm $TMPDIR/synctool.sh $TMPDIR/synctool.py $TMPDIR/md5sum.py
rmdir $TMPDIR

# EOB

