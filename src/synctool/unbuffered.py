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

class Unbuffered(object):
    '''class representing an unbuffered stream'''

    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)

        if len(data) >= 1 and (data[-1] == '\n' or data[-1] == '\r'):
            self.stream.flush()

    def flush(self):
        self.stream.flush()

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.stream.close()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

    def __enter__(self):
        return self.stream

    def __exit__(self, the_type, value, traceback):
        self.stream.close()

# EOB
