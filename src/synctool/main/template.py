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

import os
import sys
import re
import getopt

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

    if mat.group(0) != name:
        return False

    return True


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
        print('%s: error: invalid filename' % PROGNAME)
        sys.exit(-1)

    if filename == '-':
        fio = sys.stdin
    else:
        try:
            fio = open(filename, encoding='utf-8')
        except OSError as err:
            print("%s: failed to open '%s': %s" % (PROGNAME, filename,
                                                   err.strerror))
            sys.exit(-1)

    with fio:
        for line in fio:
            sys.stdout.write(subst(line))


def usage() -> None:
    '''print usage information'''

    print('''%s [-v VAR=VALUE] <input filename>
options:
  -h, --help               Display this information
  -v, --var VAR=VALUE      Set variable VAR to VALUE

synctool-template replaces all occurrences of "@VAR@" in the input text
with "VALUE" and prints the result to stdout. VAR may be given on the
command-line, but may also be an existing environment variable
''' % PROGNAME)


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
        print('%s: %s' % (PROGNAME, reason))
        usage()
        sys.exit(1)

    if not args:
        print('%s: missing input filename' % PROGNAME)
        sys.exit(1)

    if len(args) > 1:
        print('%s: too many arguments' % PROGNAME)
        sys.exit(1)

    for opt, optarg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-v', '--var'):
            try:
                (key, value) = optarg.split('=', 1)
            except ValueError:
                print('%s: syntax error in command-line' % PROGNAME)
                sys.exit(1)

            else:
                if not spellcheck(key):
                    print(('%s: syntax error: variables must be an '
                           'uppercase word' % PROGNAME))
                    sys.exit(1)

                # put it in the environment
                os.environ[key] = value

    if not args:
        print('%s: missing input file' % PROGNAME)
        sys.exit(1)

    if len(args) > 1:
        print('%s: too many arguments' % PROGNAME)
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
