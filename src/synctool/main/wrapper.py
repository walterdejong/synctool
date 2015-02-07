#
#   synctool.main.wrapper.py    WJ114
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''catch Ctrl-C and "Broken pipe" signal'''

import errno
import sys

# decorator
def catch_signals(func):
    '''run main function
    Ctrl-C and "Broken pipe" signal will gracefully terminate the program
    '''

    def wrap(*args, **kwargs):
        '''wraps a function (catch_signals is a decorator)'''

        try:
            ret = func(*args, **kwargs)
        except IOError as err:
            if err.errno == errno.EPIPE:    # Broken pipe
                pass
            else:
                print err.strerror
                sys.exit(-1)

        except KeyboardInterrupt:   # user pressed Ctrl-C
            sys.exit(127)

        return ret

    return wrap

# EOB
