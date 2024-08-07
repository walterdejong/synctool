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
from types import TracebackType


class Unbuffered:
    '''class representing an unbuffered stream'''

    def __init__(self, stream: IO) -> None:
        '''initialize instance'''

        self.stream = stream

    def write(self, data: str) -> None:
        '''unbuffered write'''

        self.stream.write(data)

        if len(data) >= 1 and (data[-1] == '\n' or data[-1] == '\r'):
            self.stream.flush()

    def flush(self) -> None:
        '''flush output'''

        self.stream.flush()

    def fileno(self) -> int:
        '''Returns file descriptor'''

        return self.stream.fileno()

    def close(self) -> None:
        '''close the stream'''

        self.stream.close()

    def __getattr__(self, attr: str) -> Any:
        '''Returns attribute
        Raises AttributeError if no such attribute
        '''

        return getattr(self.stream, attr)

    def __enter__(self) -> IO:
        '''enter context; for Python 'with' statement'''

        return self.stream

    def __exit__(self, exc_type: BaseException, exc_value: BaseException, traceback: TracebackType) -> None:
        '''leave context; for Python 'with' statement'''

        self.stream.close()

# EOB
