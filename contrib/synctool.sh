#! /bin/sh

if [ `/bin/id -u` -ne 0 ]
then
        echo "synctool.sh: You have to be root"
        exit 1
fi

LOGDIR=/var/log

/usr/sara/bin/synctool.py -l "${LOGDIR}/synctool.log" $*

