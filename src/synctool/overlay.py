#
#   synctool.overlay.py    WJ111
#
#   synctool Copyright 2015 Walter de Jong <walter@heiho.net>
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

import os
import fnmatch

import synctool.lib
from synctool.lib import verbose, warning, terse, prettypath
import synctool.object
from synctool.object import SyncObject
import synctool.param

# const enum object types
OV_REG = 0
OV_PRE = 1
OV_POST = 2
OV_TEMPLATE = 3
OV_TEMPLATE_POST = 4
OV_NO_EXT = 5
OV_IGNORE = 6


def _sort_by_importance(item1, item2):
    '''item is a tuple (x, importance)'''

    return cmp(item1[1], item2[1])


def _toplevel(overlay):
    '''Returns sorted list of fullpath directories under overlay/'''

    arr = []
    for entry in os.listdir(overlay):
        fullpath = os.path.join(overlay, entry)
        try:
            importance = synctool.param.MY_GROUPS.index(entry)
        except ValueError:
            verbose('%s/ is not one of my groups, skipping' %
                    prettypath(fullpath))
            continue

        arr.append((fullpath, importance))

    arr.sort(_sort_by_importance)

    # return list of only the directory names
    return [x[0] for x in arr]


def _group_all():
    '''Return the importance level of group 'all' '''

    # it is the final group in MY_GROUPS
    return len(synctool.param.MY_GROUPS) - 1


def _split_extension(filename, src_dir):
    '''filename in the overlay tree, without leading path
    src_dir is passed for the purpose of printing error messages
    Returns tuple: SyncObject, importance
    '''

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
        if not ext in synctool.param.ALL_GROUPS:
            src_path = os.path.join(src_dir, filename)
            if synctool.param.TERSE:
                terse(synctool.lib.TERSE_ERROR, 'invalid group on %s' %
                                                src_path)
            else:
                warning('unknown group on %s, skipped' % prettypath(src_path))
            return None, -1

        # it is not one of my groups
        verbose('skipping %s, it is not one of my groups' %
                prettypath(os.path.join(src_dir, filename)))
        return None, -1

    (name2, ext) = os.path.splitext(name)

    if ext == '.pre':
        # register group-specific .pre script
        return SyncObject(filename, name2, OV_PRE), importance

    elif ext == '.post':
        _, ext = os.path.splitext(name2)
        if ext == '._template':
            # it's a group-specific template generator
            return (SyncObject(filename, name2, OV_TEMPLATE_POST), importance)

        # register group-specific .post script
        return SyncObject(filename, name2, OV_POST), importance

    elif ext == '._template':
        return SyncObject(filename, name2, OV_TEMPLATE), importance

    return SyncObject(filename, name), importance


def _sort_by_importance_post_first(item1, item2):
    '''sort by importance, but always put .post scripts first'''

    # after the .post scripts come ._template.post scripts
    # then come regular files
    # This order is important

    obj1, importance1 = item1
    obj2, importance2 = item2

    if obj1.ov_type == OV_PRE:
        if obj2.ov_type == OV_PRE:
            return cmp(importance1, importance2)

        return -1

    if obj2.ov_type == OV_PRE:
        return 1

    if obj1.ov_type == OV_POST:
        if obj2.ov_type == OV_POST:
            return cmp(importance1, importance2)

        return -1

    if obj2.ov_type == OV_POST:
        return 1

    if obj1.ov_type == OV_TEMPLATE_POST:
        if obj2.ov_type == OV_TEMPLATE_POST:
            return cmp(importance1, importance2)

        return -1

    if obj2.ov_type == OV_TEMPLATE_POST:
        return 1

    if obj1.ov_type == OV_TEMPLATE:
        if obj2.ov_type == OV_TEMPLATE:
            return cmp(importance1, importance2)

        return -1

    if obj2.ov_type == OV_TEMPLATE:
        return 1

    return cmp(importance1, importance2)


def _walk_subtree(src_dir, dest_dir, duplicates, callback):
    '''walk subtree under overlay/group/
    duplicates is a set that keeps us from selecting any duplicate matches
    Returns pair of booleans: ok, dir was updated
    '''

#    verbose('_walk_subtree(%s)' % src_dir)

    arr = []
    for entry in os.listdir(src_dir):
        if entry in synctool.param.IGNORE_FILES:
            verbose('ignoring %s' % prettypath(os.path.join(src_dir, entry)))
            continue

        # check any ignored files with wildcards
        # before any group extension is examined
        wildcard_match = False
        for wildcard_entry in synctool.param.IGNORE_FILES_WITH_WILDCARDS:
            if fnmatch.fnmatchcase(entry, wildcard_entry):
                wildcard_match = True
                verbose('ignoring %s (pattern match)' %
                        prettypath(os.path.join(src_dir, entry)))
                break

        if wildcard_match:
            continue

        obj, importance = _split_extension(entry, src_dir)
        if not obj:
            continue

        arr.append((obj, importance))

    # sort with .pre and .post scripts first
    # this ensures that post_dict will have the required script when needed
    arr.sort(_sort_by_importance_post_first)

    pre_dict = {}
    post_dict = {}
    dir_changed = False

    for obj, importance in arr:
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
                    verbose('ignoring dotdir %s' % obj.print_src())
                    continue

            updated = False
            if not obj.dest_path in duplicates:
                # this is the most important source for this dir
                duplicates.add(obj.dest_path)

                # run callback on the directory itself
                # this will create or fix directory entry if needed
                # a .pre script may be run
                # a .post script should not be run
                ok, updated = callback(obj, pre_dict, {})
                if not ok:
                    # quick exit
                    return False, dir_changed

            # recurse down into the directory
            # with empty pre_dict and post_dict parameters
            ok, updated2 = _walk_subtree(obj.src_path, obj.dest_path,
                                         duplicates, callback)
            if not ok:
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
                verbose('ignoring dotfile %s' % obj.print_src())
                continue

        if synctool.param.REQUIRE_EXTENSION and obj.ov_type == OV_NO_EXT:
            if synctool.param.TERSE:
                terse(synctool.lib.TERSE_ERROR, 'no group on %s' %
                                                obj.src_path)
            else:
                warning('no group extension on %s, skipped' % obj.print_src())
            continue

        if obj.dest_path in duplicates:
            # there already was a more important source for this destination
            continue

        duplicates.add(obj.dest_path)

        ok, updated = callback(obj, pre_dict, post_dict)
        if not ok:
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

            ok, updated = callback(obj, pre_dict, post_dict)
            if not ok:
                # quick exit
                return False, dir_changed

        dir_changed |= updated

    return True, dir_changed


def visit(overlay, callback):
    '''visit all entries in the overlay tree
    overlay is either synctool.param.OVERLAY_DIR or synctool.param.DELETE_DIR
    callback will called with arguments: (SyncObject, pre_dict, post_dict)
    callback must return a two booleans: ok, updated
    '''

    duplicates = set()

    for d in _toplevel(overlay):
        ok, _ = _walk_subtree(d, os.sep, duplicates, callback)
        if not ok:
            # quick exit
            break

# EOB
