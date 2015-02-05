#
#   synctool.main.template.py   WJ113
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
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
PATTERN = re.compile(r'\@([A-Z_][A-Z0-9_]*)\@')


def spellcheck(name):
    '''Check for valid spelling of name
    Returns True if OK, False if not OK
    '''

    m = SPELLCHECK.match(name)
    if not m:
        return False

    if m.group(0) != name:
        return False

    return True


def subst(line):
    '''replace all occurrences of "@VAR@" with the value,
    where VAR is any environment variable
    Returns the resulting line of text
    '''

    for var in PATTERN.findall(line):
        if var in os.environ:
            line = line.replace('@' + var + '@', os.environ[var])

    return line


def template(filename):
    '''generate the output from template file'''

    if not filename:
        print '%s: error: invalid filename' % PROGNAME
        sys.exit(-1)

    if filename == '-':
        f = sys.stdin
    else:
        try:
            f = open(filename)
        except IOError as err:
            print "%s: failed to open '%s': %s" % (PROGNAME, filename,
                                                   err.strerror)
            sys.exit(-1)

    with f:
        for line in f:
            sys.stdout.write(subst(line))


def usage():
    '''print usage information'''

    print '''%s [-v VAR=VALUE] <input filename>
options:
  -h, --help               Display this information
  -v, --var VAR=VALUE      Set variable VAR to VALUE

synctool-template replaces all occurrences of "@VAR@" in the input text
with "VALUE" and prints the result to stdout. VAR may be given on the
command-line, but may also be an existing environment variable
''' % PROGNAME


def get_options():
    '''parse command-line options'''

    if len(sys.argv) <= 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hv:', ['help', 'var='])
    except getopt.GetoptError as reason:
        print '%s: %s' % (PROGNAME, reason)
        usage()
        sys.exit(1)

    if not args:
        print '%s: missing input filename' % PROGNAME
        sys.exit(1)

    if len(args) > 1:
        print '%s: too many arguments' % PROGNAME
        sys.exit(1)

    for opt, optarg in opts:
        if opt in ('-h', '--help', '-?'):
            usage()
            sys.exit(1)

        if opt in ('-v', '--var'):
            try:
                (key, value) = optarg.split('=', 1)
            except ValueError:
                print '%s: syntax error in command-line' % PROGNAME
                sys.exit(1)

            else:
                if not spellcheck(key):
                    print ('%s: syntax error: variables must be an '
                           'uppercase word' % PROGNAME)
                    sys.exit(1)

                # put it in the environment
                os.environ[key] = value

    if not args:
        print '%s: missing input file' % PROGNAME
        sys.exit(1)

    if len(args) > 1:
        print '%s: too many arguments' % PROGNAME
        sys.exit(1)

    # return the input filename
    return args[0]


@catch_signals
def main():
    '''do it'''

    INPUT_FILE = get_options()
    template(INPUT_FILE)

# EOB
