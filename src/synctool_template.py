#! /usr/bin/env python
#
#   synctool-template    WJ114
#
#   synctool Copyright 2014 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool-template is a helper program for generating templates
   - auto replace "@VAR@" in the input text
   - You can do the same thing with m4 or sed, but this one is nice and easy
'''

import synctool.main.template

if __name__ == '__main__':
    synctool.main.template.main()

# EOB
