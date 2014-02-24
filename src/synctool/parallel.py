#
#   synctool.parallel.py    WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''do things in parallel. This module is very UNIX-only, sorry'''

import os
import sys
import errno

# TD sleep
import time

from synctool.lib import error
import synctool.param

ALL_PIDS = set()


def do(func, work):
    '''run func in parallel'''

    len_work = len(work)
    if len_work <= synctool.param.NUM_PROC:
        num_proc = len_work
        part = 1
    else:
        num_proc = synctool.param.NUM_PROC
        part = len_work / num_proc
        if len_work % num_proc != 0:
            part += 1

    for rank in xrange(num_proc):
        try:
            pid = os.fork()
        except OSError as err:
            error('failed to fork(): %s' % err.strerror)
            return

        if pid == 0:
            # child process
            # run all work items in sequence
            lower = part * rank
            upper = part * (rank + 1)
            if upper > len_work:
                upper = len_work

            for item in work[lower:upper]:
                func(item)
                # this is for option --zzz
                if synctool.param.SLEEP_TIME > 0:
                    time.sleep(synctool.param.SLEEP_TIME)

            sys.exit(0)

        # parent
        ALL_PIDS.add(pid)

    join()


def join():
    '''wait for parallel threads to exit'''

    global ALL_PIDS

    # wait until no more child processes left
    while len(ALL_PIDS) > 0:
        try:
            pid, _ = os.wait()
        except OSError as err:
            if err.errno == errno.ECHILD:
                # no child process
                ALL_PIDS = set()
                break
        else:
            if pid in ALL_PIDS:
                ALL_PIDS.remove(pid)


# unit test
if __name__ == '__main__':
    def hello(item):
        '''print item'''

        print '[%u]: hello' % os.getpid(), item
        time.sleep(0.1245)

    synctool.param.NUM_PROC = 3
    do(hello, range(10))

# EOB
