#
#   synctool.parallel.py    WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''do things in parallel. This module is very UNIX-only, sorry'''

# This module offers the same as Python's multiprocessing
# but there are some issues with multiprocessing, so ...

import os
import sys
import errno
import time

from typing import List, Set, Callable, Any

from synctool.lib import error
from synctool.main.wrapper import catch_signals
import synctool.param

ALL_PIDS: Set[int] = set()


def do(func: Callable[[Any], None], work: List[Any]) -> None:
    '''run func in parallel'''

    # pylint: disable=invalid-name

    if synctool.param.SLEEP_TIME != 0:
        synctool.param.NUM_PROC = 1

    # 'part' becomes amount of work for each rank to do
    len_work = len(work)
    if len_work <= synctool.param.NUM_PROC:
        num_proc = len_work
        part = 1
    else:
        num_proc = synctool.param.NUM_PROC
        part = len_work // num_proc
        if len_work % num_proc != 0:
            part += 1

    # spawn pool of workers
    for rank in range(num_proc):
        try:
            pid = os.fork()
        except OSError as err:
            error('failed to fork(): %s' % err.strerror)
            return

        if pid == 0:
            # child process
            worker(rank, func, work, part)
            sys.exit(0)

        # parent process
        ALL_PIDS.add(pid)

    # wait for all workers to exit
    join()


@catch_signals
def worker(rank: int, func: Callable[[Any], None], work: List[Any], part: int) -> int:
    '''run func to do part of work for parallel rank'''

    # determine which chunk of work to do
    lower = part * rank
    upper = part * (rank + 1)
    len_work = len(work)
    upper = min(upper, len_work)

    # run all work items in sequence
    for item in work[lower:upper]:
        func(item)
        # this is for option --zzz
        if synctool.param.SLEEP_TIME > 0:
            time.sleep(synctool.param.SLEEP_TIME)
    return 0


def join() -> None:
    '''wait for parallel threads to exit'''

    global ALL_PIDS                                         # pylint: disable=global-statement

    # wait until no more child processes left
    while ALL_PIDS:
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
    @catch_signals
    def main() -> int:
        '''main func'''

        def hello(item: int) -> None:
            '''print item'''

            print('[%u]: hello' % os.getpid(), item)
            time.sleep(0.1245)

        synctool.param.NUM_PROC = 3
        do(hello, list(range(10)))
        return 0

    # synctool.param.SLEEP_TIME = 2
    main()

# EOB
