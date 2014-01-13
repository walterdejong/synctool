#
#   synctool.main.wrapper.py    WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''catch Ctrl-C and "Broken pipe" signal'''

import errno
import sys
import time

# decorator
def catch_signals(func):
    '''run main function
    Ctrl-C and "Broken pipe" signal will gracefully terminate the program'''

    def wrap(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)

            # workaround exception in QueueFeederThread at exit
            # which is a Python bug, really
            time.sleep(0.01)
        except IOError as err:
            if err.errno == errno.EPIPE:    # Broken pipe
                pass
            else:
                print err.strerror
                sys.exit(-1)

        except KeyboardInterrupt:   # user pressed Ctrl-C
            print
            sys.exit(127)

        return ret

    return wrap


# EOB
