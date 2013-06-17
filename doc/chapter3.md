3. Using synctool
=================
The main power of synctool is the fact that you can define logical groups,
and you can add these to a filename as a filename extension. This will result
in the file being copied, only if the node belongs to the same group.
The groups a node is in, are defined in the `synctool.conf` file.
In the configuration file, the nodename is associated with one or more groups.
The nodename itself can also be used as a group to indicate that a file
belongs to that node.

Under the synctool root there are two very important directories:

* `/opt/synctool/var/overlay/`

* `/opt/synctool/var/delete/`

The `overlay/` tree contains files that have to be copied to the target nodes.
When synctool detects a difference between a file on the system and a file
in the overlay tree, the file will be copied from the overlay tree onto
the node.

The `delete/` tree contains files that always have to be deleted from the
nodes. Only the filename matters, so it is alright if the files in this tree
are only zero bytes in size.

synctool uses `rsync` to copy these trees to the node, and afterwards it
runs the `synctool-client` command on the node. Note that it is perfectly
possible to run `synctool-client` on a node by hand, in which case it will
check its local copy of the repository. It will not synchronize with the
master repository, synctool works with _server push_ and not client pull.

If you do have the luxury of a high performance shared filesystem on your
cluster, you may put synctool on there and use the option `--skip-rsync` to
skip the mirroring of the repository. You may also use `rsync:no` in a node
definition in the config file to tell synctool not to run `rsync`.


3.1 Running synctool
--------------------
Let's have a look at this example:

    root@masternode:/# synctool
    node3: DRY RUN, not doing any updates
    node3: /etc/xinetd.d/identd updated (file size mismatch)

The file is being updated because there is a mismatch in the file size.
Should the file size be the same, synctool will calculate an MD5 checksum to
see whether the file was changed or not.

By default synctool does a _dry run_. It will not do anything but show
what would happen if this would not be a dry run. Use option `-f` or `--fix`
to apply any changes.


3.2 Adding actions to updates
-----------------------------
Now I would like the `xinetd` to be automatically reloaded after I change
the `identd` file. This is done by adding a trigger script, in synctool-speak
known as a ".post" script.

In `overlay/all/etc/xinetd.d/identd.post` put only this line:

    /etc/init.d/xinetd reload

Make the `.post` script executable: `chmod +x identd.post`

The `.post` script will be run when the file changes:

    root@masternode:/# synctool -f
    node3: /etc/xinetd.d/identd updated (file size mismatch)
    node3: running command $overlay/all/etc/xinetd.d/identd.post

The `.post` script is executed in the directory where the accompanying file
is in, in this case `/etc/xinetd.d/`. It is possible to add a group
extension to the `.post` script, so that you can have one group of nodes
perform different actions than another.


3.3 Special groups
------------------
The next example shows that the nodename can be used as a group.
In the example, the `fstab` file is identical throughout the cluster, with
the exception of node5 and node7.

    root@masternode:/opt/synctool/var# ls -F overlay/all/etc
    fstab._all    motd.production._batch  sudoers._all
    fstab._node5  nsswitch.conf._all      sysconfig/
    fstab._node7  nsswitch.conf.old._all  sysctl.conf._all

Group `all` implictly applies to all nodes. Likewise, there is an implicit
group `none` that matches no nodes. Group `none` can be convenient when you
to have a copy of a file around, but do not wish to push it to any nodes yet.


3.4 Useful options
------------------
The option `-q` of synctool gives less output:

    root@masternode:/# synctool -q
    node3: /etc/xinetd.d/identd updated (file size mismatch)

If `-q` still gives too much output, because you have many nodes in your
cluster, it is possible to specify `-a` to condense (aggregate) output.
The condensed output groups together output that is the same for many nodes.

One of my favorite commands is `synctool -qa`.
You may also use this to condense output from `dsh`, for example

    # dsh -a date

    # dsh-ping -a

The option `-f` or `--fix` applies all changes. Always be sure to run
synctool at least once as a dry run! (without `-f`).
Mind that synctool does not lock the repository and does not guard against
concurrent use by multiple sysadmins at once. In practice, this hardly ever
leads to any problems.

To update only a single file rather than all files, use the option
`--single` or `-1` (that's a number one, not the letter _ell_).

If you want to check what file synctool is using for a given destination
file, use option `-ref` or `-r`:

    root@masternode:/# synctool -q -n node1 -r /etc/resolv.conf
    node1: /etc/resolv.conf._somegroup

To inspect differences between the master copy and the client copy of a file,
use option `--diff` or `-d`.

synctool can be run on a subset of nodes, a group, or even on individual
nodes using the options `--group` or `-g`, `--node` or `-n`, `--exclude`
or `-x`, and `--exclude-group` or `-X`. This also works for `dsh` and friends.
For example:

    # synctool -g batch,sched -X rack8

Another example:

    # dsh -n node1,node2,node3 date

or copy a file to these three nodes:

    # dcp -n node1,node2,node3 -d /tmp patchfile-1.0.tar.gz

You may also wish to pull a file from a node into the repository. You can do
this from the masternode like this:

    # synctool -n node1 --upload /path/to/file

It may be desirable to give the file a different group extension than the
default proposed by synctool:

    # synctool -n node1 --upload /path/to/file --suffix=somegroup

After rebooting a cluster, use `dsh-ping` to see if the nodes respond to ping
yet. You may also do this on a group of nodes:

    # dsh-ping -g rack4

The option `-v` gives verbose output. This is another way of displaying
the logic that synctool performs:

    # synctool -v
    node3: checking $overlay/all/etc/tcpd_banner.production._all
    node3: overridden by $overlay/all/etc/tcpd_banner.production._batch
    node3: checking $overlay/all/etc/issue.net.production._all
    node3: checking $overlay/all/etc/syslog.conf._all
    node3: checking $overlay/all/etc/issue.production._all
    node3: checking $overlay/all/etc/modules.conf._all
    node3: checking $overlay/all/etc/hosts.allow.production._interactive
    node3: skipping $overlay/all/etc/hosts.allow.production._interactive,
    it is not one of my groups

The option `--unix` produces UNIX-style output. This shows in standard shell
syntax just what synctool is about to do.

    root@masternode:/# synctool --unix
    node3: # updating file /etc/xinetd.d/identd
    node3: mv /etc/xinetd.d/identd /etc/xinetd.d/identd.saved
    node3: umask 077
    node3: cp /var/lib/synctool/overlay/etc/xinetd.d/identd._all
    /etc/xinetd.d/identd
    node3: chown root.root /etc/xinetd.d/identd
    node3: chmod 0644 /etc/xinetd.d/identd

> synctool does not apply changes by executing shell commands; all
> operations are programmed in Python. The option `--unix` is only a way of
> displaying what synctool does, and may be useful when debugging.

The option `-T` option produces terse output. In terse mode, long paths are
abbreviated in an attempt to fit them on a single line of 80 characters wide.
Terse mode can be made to give colored output through `synctool.conf`.

    root@masternode# synctool -n n1 -T
    n1: DRYRUN not doing any updates
    n1: mkdir /Users/walter/src/.../testroot/etc/cron.daily
    n1: new /Users/walter/src/.../testroot/etc/cron.daily/testfile
    n1: exec //overlay/Users/.../testroot/etc/cron.daily.post

Note that these abbreviated paths can still be copy-and-pasted and used with
other synctool commands like `--single` and `--diff`. synctool will recognize
the abbreviated path and expand it on the fly. In the case of any name clashes
synctool will report this and present a list of possibilities for you to
consider.

The option `--skip-rsync` skips the `rsync` run that copies the repository
from the master server to the client node. You should only specify this
option when your repository resides on a shared filesystem. Sharing the
repository between your master server and client nodes has certain security
implications, so be mindful of what you are doing in such a setup.
If you have a fast shared filesystem between all client nodes, but it is
not shared with the master server, you can specify `rsync:no` in the config
file.


3.5 Logging
-----------
When using option `--fix` to apply changes, synctool can log the performed
actions to a file. Use the `logfile` directive in `synctool.conf` to specify
that you want logging:

    logfile /var/log/synctool.log

synctool will write this logfile on each node seperately, and a concatenated
log on the master node.


3.6 Ignoring them: I'm not touching you
---------------------------------------
By using directives in the `synctool.conf` file, synctool can be told to
ignore certain files, nodes, or groups. These will be excluded, skipped.
For example:

    ignore_dotfiles no
    ignore_dotdirs yes
    ignore .svn
    ignore .gitignore .git
    ignore .*.swp
    ignore_node node1 node2
    ignore_group oldgroup
    ignore_group test


3.7 About symbolic links
------------------------
synctool requires all files in the repository to have an extension (well ...
unless you changed the default configuration), and symbolic links must have
extensions too. Symbolic links in the repository will be _dead_ symlinks but
they will point to the correct destination on the target node.

Consider the following example, where `file` does not exist 'as is' in the
repository:

    $overlay/all/etc/motd._red -> file
    $overlay/all/etc/file._red

In the repository, `motd._red` is a red & dead symlink to `file`. On the
target node, `/etc/motd` is going to be fine.


3.8 Backup copies
-----------------
For any file synctool updates, it keeps a backup copy around on the target
node with the extension `.saved`. If you don't like this, you can tell
synctool to not make any backup copies with:

    backup_copies no

It is however highly recommended that you run with `backup_copies` enabled.
You can manually specify that you want to remove backup copies using:

    synctool --erase-saved
    synctool -e


3.9 Checking for updates
------------------------
synctool can check whether a new version of synctool itself is available by
using the option `--check-update` on the master node. You can check
periodically for updates by using `--check-update` in a crontab entry.
To download the latest version, run `synctool --download` on the master node.
These functions connect to the main website at [www.heiho.net/synctool][1].

[1]: http://www.heiho.net/synctool/


3.10 synctool-pkg, the synctool package manager
-----------------------------------------------
synctool comes with a package manager named `synctool-pkg`.
Rather than being yet another package manager with its own format of packages,
synctool-pkg is a wrapper around existing package management software.
synctool-pkg unifies all the different package managers out there so you can
operate any of them using just one command and the same set of command-line
arguments. This is particularly useful in heterogeneous clusters or when
you are working with multiple platforms or distributions.

synctool-pkg may also be invoked as `dsh-pkg` and works a lot like regular
`dsh`.

synctool-pkg supports a number of different package management systems.
Unless explicitly defined in `synctool.conf`, synctool-pkg will detect the
system's operating system and its package manager. If detection fails, you
may force the package manager on the command-line or in `synctool.conf`:

    package_manager apt-get
    #package_manager yum
    #package_manager zypper
    #package_manager pacman
    #package_manager brew
    #package_manager bsdpkg

synctool-pkg knows about more platforms and package managers, but currently
only the ones listed above are implemented and supported.

> synctool-pkg is pluggable. Adding support for other package management
> systems is rather easy. If your platform and/or favorite package manager
> is not yet supported, feel free to develop your own plug-in for synctool-pkg
> or contact the author of synctool.

The `bsdpkg` module uses `freebsd-update` on FreeBSD and `pkg_add -u` on
other BSDs for upgrading packages.

Following are examples of how to use synctool-pkg.

    synctool-pkg -n node1 --list
    synctool-pkg -n node1 --list wget
    synctool-pkg -g batch --install lynx wget curl
    dsh-pkg -g batch -x node3 --remove somepackage

Sometimes you need to refresh the contents of the local package database.
You can do this with the 'update' command:

    dsh-pkg -qa --update

You may check for software upgrades for the node with `--upgrade`.
This will only show what upgrades are available. To really upgrade a node,
specify `--fix`. It is wise to always test an upgrade on a single node.

    dsh-pkg --upgrade
    dsh-pkg -n testnode --upgrade -f
    dsh-pkg --upgrade -f

Package managers download their packages into an on-disk cache. Sometimes the
disk fills up and you may want to clean out the disk cache:

    dsh-pkg -qa --clean

A specific package manager may be selected from the command-line.

    dsh-pkg -m yum -i somepackage   # force it to use yum

If you want to further examine what synctool-pkg is doing, you may specify
`--verbose` or `--unix` to display more information about what is going on
under the hood.


3.11 Slow updates
-----------------
By default, synctool addresses the nodes in parallel, and they are running
updates concurrently. In some cases, like when doing rolling upgrades,
you will not want to have this parallelism. There are two easy ways around
this.

    dsh --numproc=1 uptime

    dsh --zzz=10 uptime

The first one tells synctool (or in this case, `dsh`) to run only one
process at a time. The second does the same thing, and sleeps for ten seconds
after running the command.

> Suppose you have a 60 node cluster, and run with `--zzz=60`.
> You now have to wait at least one hour for the run to complete.

The options `--numproc` and `--zzz` work for both `synctool` and `dsh`
programs.
