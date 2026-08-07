#
#   synctool.main.template.py   WJ113
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool-template is a helper program for generating templates
- auto replace "@VAR@" in the input text
- You can do the same thing with m4 or sed, but this one is nice and easy
'''

import getopt
import os
import re
import sys

from synctool.main.wrapper import catch_signals

# hardcoded name because otherwise we get "synctool_template.py"
PROGNAME = 'synctool-template'

SPELLCHECK = re.compile(r'[A-Z_][A-Z0-9_]*')


def spellcheck(name: str) -> bool:
    '''Check for valid spelling of name
    Returns True if OK, False if not OK
    '''

    mat = SPELLCHECK.match(name)
    if not mat:
        return False

    return mat.group(0) == name


PATTERN = re.compile(r'\@([A-Z_][A-Z0-9_]*)\@')


def subst(line: str) -> str:
    '''replace all occurrences of "@VAR@" with the value,
    where VAR is any environment variable
    Returns the resulting line of text
    '''

    for var in PATTERN.findall(line):
        if var in os.environ:
            line = line.replace('@' + var + '@', os.environ[var])

    return line


def template(filename: str) -> None:
    '''generate the output from template file'''

    if not filename:
        print(f'{PROGNAME}: error: invalid filename')
        sys.exit(-1)

    if filename == '-':
        # note: we do not use the 'with' statement here
        # because that would close stdin afterwards
        for line in sys.stdin:
            sys.stdout.write(subst(line))
    else:
        try:
            with open(filename, encoding='utf-8') as fio:
                for line in fio:
                    sys.stdout.write(subst(line))
        except OSError as err:
            print(f"{PROGNAME}: failed to open '{filename}': {err.strerror}")
            sys.exit(-1)


def usage() -> None:
    '''print usage information'''

    print(f'''{PROGNAME} [-v VAR=VALUE] <input filename>
options:
  -h, --help               Display this information
  -v, --var VAR=VALUE      Set variable VAR to VALUE

synctool-template replaces all occurrences of "@VAR@" in the input text
with "VALUE" and prints the result to stdout. VAR may be given on the
command-line, but may also be an existing environment variable
''')


def get_options() -> str:
    '''parse command-line options
    Returns filename argument
    '''

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hv:', ['help', 'var='])
    except getopt.GetoptError as reason:
        print(f'{PROGNAME}: {reason}')
        usage()
        sys.exit(1)

    if not args:
        print(f'{PROGNAME}: missing input filename')
        sys.exit(1)

    if len(args) > 1:
        print(f'{PROGNAME}: too many arguments')
        sys.exit(1)

    for opt, optarg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-v', '--var'):
            try:
                (key, value) = optarg.split('=', 1)
            except ValueError:
                print(f'{PROGNAME}: syntax error in command-line')
                sys.exit(1)

            else:
                if not spellcheck(key):
                    print(f'{PROGNAME}: syntax error: variables must be an uppercase word')
                    sys.exit(1)

                # put it in the environment
                os.environ[key] = value

    if not args:
        print(f'{PROGNAME}: missing input file')
        sys.exit(1)

    if len(args) > 1:
        print(f'{PROGNAME}: too many arguments')
        sys.exit(1)

    # return the input filename
    return args[0]


@catch_signals
def main() -> int:
    '''do it'''

    infile = get_options()
    template(infile)
    return 0

# EOB
