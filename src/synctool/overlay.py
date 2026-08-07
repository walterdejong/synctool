#
#   synctool.overlay.py    WJ111
#
#   synctool Copyright 2024 Walter de Jong <walter@heiho.net>
#
#   synctool COMES WITH NO WARRANTY. synctool IS FREE SOFTWARE.
#   synctool is distributed under terms described in the GNU General Public
#   License.
#

'''synctool.overlay maps the repository onto the root directory.

    Consider this tree:
     $overlay/all/etc/ntp.conf._n1
     $overlay/all/etc._n1/ntp.conf._all
     $overlay/all/etc._n1/ntp.conf._n1
     $overlay/n1/etc/ntp.conf._all
     $overlay/n1/etc/ntp.conf._n1
     $overlay/n1/etc._n1/ntp.conf._all
     $overlay/n1/etc._n1/ntp.conf._n1

    [Ideally] synctool selects the final entry. It accomplishes this with
    the following procedure:
     1. foreach direntry split the extension; get the 'importance'
     2. sort by importance
     3. first come, first served; first encountered entry is best choice
     4. register destination as 'already handled' (duplicate)
     5. if already handled, skip this entry

    .post scripts are sorted in first so that a dictionary can be built
    before it needs to be consulted. This dictionary only contains .post
    scripts that are in the current directory. Additionally, if the current
    directory itself has a .post script (which is in the parent directory),
    then the .post script is passed in the dict as well.
'''

from __future__ import annotations

import fnmatch
import os
from functools import cmp_to_key
from typing import Callable

import synctool.lib
import synctool.object
import synctool.param
from synctool.lib import prettypath, terse, verbose, warning
from synctool.object import SyncObject

# const enum object types
OV_REG = 0
OV_PRE = 1
OV_POST = 2
OV_TEMPLATE = 3
OV_TEMPLATE_POST = 4
OV_NO_EXT = 5
OV_IGNORE = 6


def _toplevel(overlay: str) -> list[str]:
    '''Returns sorted list of fullpath directories under overlay/'''

    # the tuples are (fullpath, importance)
    # the list of paths gets sorted by importance; key=item[1]

    arr: list[tuple[str, int]] = []

    for entry in os.listdir(overlay):
        fullpath = os.path.join(overlay, entry)
        try:
            importance = synctool.param.MY_GROUPS.index(entry)
        except ValueError:
            verbose('{}/ is not one of my groups, skipping'.format(prettypath(fullpath)))
            continue

        arr.append((fullpath, importance))
        # verbose('%s is mine, importance %d' % (prettypath(fullpath), importance))

    arr.sort(key=lambda x: x[1])

    # return list of only the directory names
    return [x[0] for x in arr]


def _group_all() -> int:
    '''Return the importance level of group 'all' '''

    # it is the final group in MY_GROUPS
    return len(synctool.param.MY_GROUPS) - 1


def _split_extension(filename: str, src_dir: str) -> tuple[SyncObject | None, int]:
    '''filename in the overlay tree, without leading path
    src_dir is passed for the purpose of printing error messages
    Returns tuple: SyncObject, importance
    '''

    # pylint: disable=too-many-branches, too-many-return-statements

    (name, ext) = os.path.splitext(filename)
    if not ext:
        return SyncObject(filename, name, OV_NO_EXT), _group_all()

    if ext == '.pre':
        # it's a generic .pre script
        return SyncObject(filename, name, OV_PRE), _group_all()

    if ext == '.post':
        (name2, ext) = os.path.splitext(name)
        if ext == '._template':
            # it's a generic template generator
            return SyncObject(filename, name, OV_TEMPLATE_POST), _group_all()

        # it's a generic .post script
        return SyncObject(filename, name, OV_POST), _group_all()

    if ext[:2] != '._':
        return SyncObject(filename, filename, OV_NO_EXT), _group_all()

    ext = ext[2:]
    if not ext:
        return SyncObject(filename, filename, OV_NO_EXT), _group_all()

    if ext == 'template':
        return SyncObject(filename, name, OV_TEMPLATE), _group_all()

    try:
        importance = synctool.param.MY_GROUPS.index(ext)
    except ValueError:
        if ext not in synctool.param.ALL_GROUPS:
            src_path = os.path.join(src_dir, filename)
            if synctool.param.TERSE:
                terse(synctool.lib.TERSE_ERROR, f'invalid group on {src_path}')
            else:
                warning('unknown group on {}, skipped'.format(prettypath(src_path)))
            return None, -1

        # it is not one of my groups
        verbose('skipping {}, it is not one of my groups'.format(prettypath(os.path.join(src_dir, filename))))
        return None, -1

    (name2, ext) = os.path.splitext(name)

    if ext == '.pre':
        # register group-specific .pre script
        return SyncObject(filename, name2, OV_PRE), importance

    if ext == '.post':
        _, ext = os.path.splitext(name2)
        if ext == '._template':
            # it's a group-specific template generator
            return (SyncObject(filename, name2, OV_TEMPLATE_POST), importance)

        # register group-specific .post script
        return SyncObject(filename, name2, OV_POST), importance

    if ext == '._template':
        return SyncObject(filename, name2, OV_TEMPLATE), importance

    return SyncObject(filename, name), importance


def _sort_by_importance_post_first(item1: tuple[SyncObject, int], item2: tuple[SyncObject, int]) -> int:
    '''sort by importance, but always put .post scripts first'''

    # pylint: disable=too-many-return-statements

    # after the .post scripts come ._template.post scripts
    # then come regular files
    # This order is important

    obj1, importance1 = item1
    obj2, importance2 = item2

    # if types are the same, just sort by importance
    if obj1.ov_type == obj2.ov_type:
        if importance1 < importance2:
            return -1
        return int(importance1 == importance2)

    if obj1.ov_type == OV_PRE:
        return -1
    if obj2.ov_type == OV_PRE:
        return 1

    if obj1.ov_type == OV_POST:
        return -1
    if obj2.ov_type == OV_POST:
        return 1

    if obj1.ov_type == OV_TEMPLATE_POST:
        return -1
    if obj2.ov_type == OV_TEMPLATE_POST:
        return 1

    if obj1.ov_type == OV_TEMPLATE:
        return -1
    if obj2.ov_type == OV_TEMPLATE:
        return 1

    # get the REG vs NO_EXT/IGNORE types here
    return 0


def _walk_subtree(src_dir: str, dest_dir: str, duplicates: set[str],
                  callback: Callable[[SyncObject, dict[str, str], dict[str, str]], tuple[bool, bool]]) -> tuple[bool, bool]:
    '''walk subtree under overlay/group/
    duplicates is a set that keeps us from selecting any duplicate matches
    Returns pair of booleans: ok, dir was updated
    '''

    # pylint: disable=too-many-locals,too-many-statements,too-many-branches

    arr = []
    for entry in os.listdir(src_dir):
        if entry in synctool.param.IGNORE_FILES:
            verbose('ignoring {}'.format(prettypath(os.path.join(src_dir, entry))))
            continue

        # check any ignored files with wildcards
        # before any group extension is examined
        wildcard_match = False
        for wildcard_entry in synctool.param.IGNORE_FILES_WITH_WILDCARDS:
            if fnmatch.fnmatchcase(entry, wildcard_entry):
                wildcard_match = True
                verbose('ignoring {} (pattern match)'.format(prettypath(os.path.join(src_dir, entry))))
                break

        if wildcard_match:
            continue

        obj, importance = _split_extension(entry, src_dir)
        if obj is None:
            continue

        arr.append((obj, importance))

    # sort with .pre and .post scripts first
    # this ensures that post_dict will have the required script when needed

    arr.sort(key=cmp_to_key(_sort_by_importance_post_first))

    pre_dict: dict[str, str] = {}
    post_dict: dict[str, str] = {}
    dir_changed = False

    for obj, _importance in arr:
        obj.make(src_dir, dest_dir)

        if obj.ov_type == OV_PRE:
            # register the .pre script and continue
            if obj.dest_path in pre_dict:
                continue

            pre_dict[obj.dest_path] = obj.src_path
            continue

        if obj.ov_type == OV_POST:
            # register the .post script and continue
            if obj.dest_path in post_dict:
                continue

            post_dict[obj.dest_path] = obj.src_path
            continue

        if obj.ov_type == OV_TEMPLATE_POST:
            # register the template generator and continue
            # put the dest for the template in the overlay (source) dir
            obj.dest_path = os.path.join(os.path.dirname(obj.src_path),
                                         os.path.basename(obj.dest_path))
            if obj.dest_path in post_dict:
                continue

            post_dict[obj.dest_path] = obj.src_path
            continue

        if obj.src_stat.is_dir():
            if synctool.param.IGNORE_DOTDIRS:
                name = os.path.basename(obj.src_path)
                if name[0] == '.':
                    verbose(f'ignoring dotdir {obj.print_src()}')
                    continue

            updated = False
            if obj.dest_path not in duplicates:
                # this is the most important source for this dir
                duplicates.add(obj.dest_path)

                # run callback on the directory itself
                # this will create or fix directory entry if needed
                # a .pre script may be run
                # a .post script should not be run
                okay, updated = callback(obj, pre_dict, {})
                if not okay:
                    # quick exit
                    return False, dir_changed

            # recurse down into the directory
            # with empty pre_dict and post_dict parameters
            okay, updated2 = _walk_subtree(obj.src_path, obj.dest_path,
                                           duplicates, callback)
            if not okay:
                # quick exit
                return False, dir_changed

            # we still need to run the .post script on the dir (if any)
            if updated or updated2:
                obj.run_script(post_dict)

            # finished checking directory
            continue

        if synctool.param.IGNORE_DOTFILES:
            name = os.path.basename(obj.src_path)
            if name[0] == '.':
                verbose(f'ignoring dotfile {obj.print_src()}')
                continue

        if synctool.param.REQUIRE_EXTENSION and obj.ov_type == OV_NO_EXT:
            if synctool.param.TERSE:
                terse(synctool.lib.TERSE_ERROR, f'no group on {obj.src_path}')
            else:
                warning(f'no group extension on {obj.print_src()}, skipped')
            continue

        if obj.dest_path in duplicates:
            # there already was a more important source for this destination
            continue

        duplicates.add(obj.dest_path)

        okay, updated = callback(obj, pre_dict, post_dict)
        if not okay:
            # quick exit
            return False, dir_changed

        if obj.ov_type == OV_IGNORE:
            # OV_IGNORE may be set by templates that didn't finish
            continue

        if obj.ov_type == OV_TEMPLATE:
            # a new file was generated
            # call callback on the generated file
            obj.ov_type = OV_REG
            obj.make(src_dir, dest_dir)

            okay, updated = callback(obj, pre_dict, post_dict)
            if not okay:
                # quick exit
                return False, dir_changed

        if updated:
            dir_changed = True

    return True, dir_changed


def visit(overlay: str, callback: Callable[[SyncObject, dict[str, str], dict[str, str]], tuple[bool, bool]]) -> None:
    '''visit all entries in the overlay tree
    overlay is either synctool.param.OVERLAY_DIR or synctool.param.DELETE_DIR
    callback will called with arguments: (SyncObject, pre_dict, post_dict)
    callback must return a two booleans: ok, updated
    '''

    duplicates: set[str] = set()

    for direct in _toplevel(overlay):
        okay, _ = _walk_subtree(direct, os.sep, duplicates, callback)
        if not okay:
            # quick exit
            break

# EOB
