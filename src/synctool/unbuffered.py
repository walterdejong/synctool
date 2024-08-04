#
#   synctool.unbuffered.py    WJ110
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#
#    - unbuffered output, needed for synctool_master
#

'''make stdio unbuffered'''

from typing import IO, Any


class Unbuffered:
    '''class representing an unbuffered stream'''

    def __init__(self, stream):
        # type: (IO) -> None
        '''initialize instance'''

        self.stream = stream

    def write(self, data):
        # type: (str) -> None
        '''unbuffered write'''

        self.stream.write(data)

        if len(data) >= 1 and (data[-1] == '\n' or data[-1] == '\r'):
            self.stream.flush()

    def flush(self):
        # type: () -> None
        '''flush output'''

        self.stream.flush()

    def fileno(self):
        # type: () -> int
        '''Returns file descriptor'''

        return self.stream.fileno()

    def close(self):
        # type: () -> None
        '''close the stream'''

        self.stream.close()

    def __getattr__(self, attr):
        # type: (str) -> Any
        '''Returns attribute
        Raises AttributeError if no such attribute
        '''

        return getattr(self.stream, attr)

    def __enter__(self):
        # type: () -> IO
        '''enter context; for Python 'with' statement'''

        return self.stream

    def __exit__(self, the_type, value, traceback):
        # type: (...) -> None
        '''leave context; for Python 'with' statement'''

        self.stream.close()

# EOB
