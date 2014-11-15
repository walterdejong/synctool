3. Using synctool
=================
The main power of synctool is the fact that you can define logical groups,
and you can add these to a filename as a filename extension. This will result
in the file being copied, only if the node belongs to the same group.
The groups a node is in, are defined in the `synctool.conf` file.
In the configuration file, the nodename is associated with one or more groups.
The nodename itself can also be used as a group to indicate that a file
belongs to that node.

Under the synctool root there are these interesting directories:

* `/opt/synctool/var/overlay/`
* `/opt/synctool/var/delete/`
* `/opt/synctool/var/purge/`

This is referred to as 'the repository'.

The `overlay/` tree contains files that have to be copied to the target nodes.
When synctool detects a difference between a file on the system and a file
in the overlay tree, the file will be copied from the overlay tree onto
the node.

The `delete/` tree contains files that always have to be deleted from the
nodes. Only the filename matters, so it is alright if the files in this tree
are only zero bytes in size.

The `purge/` tree contains directories that are copied as-is to the nodes,
and deleting any files on the target node that are unmanaged -- files that
should not be there.

synctool uses `rsync` to copy these trees to the node, and afterwards it
runs the `synctool-client` command on that node. Note that it is perfectly
possible to run `synctool-client` on a node by hand, in which case it will
check its local copy of the repository. The client by itself will not
synchronize with the master repository; synctool works with _server push_
and not client pull.

> Previously, synctool was located under `/var/lib/synctool/`.
> It worked for me (tm), except that the Filesystem Hierarchy Standard (FHS)
> has various things to say about it:
>
> * thou shalt put configuration files under an `etc/` directory;
> * thou shalt not execute programs from the `/var` partition;
> * `/var` may be mounted read-only;
> * programs that want to keep things together, should use `/opt`.
>
> If you have difficulty with getting used to synctool's new root,
> try this:
>
> * symlink `/var/lib/synctool -> /opt/synctool/var`
> * `export overlay=/opt/synctool/var/overlay ; cd $overlay`


3.1 Populating the repository
-----------------------------
In the repository you will store all the important system configuration files
of the cluster nodes. The overlay directory represents the root directory of
the cluster nodes. By assigning an extension to a file in the repository,
you can tell synctool what nodes should get what copy of a file.
Consider this example:

    /opt/synctool/var/overlay/all/
      etc/ntp.conf._all
      etc/ntp.conf._node1
      etc/ntp.conf._wn

Here, worker nodes (nodes tagged with group `wn` in `synctool.conf`) will
get the file `ntp.conf._wn` for `/etc/ntp.conf`. Node `node1` is special
and gets a different file. All other nodes will get `ntp.conf._all`.

There is a special group named `'none'`. Files with the extension `._none`
will be copied to no nodes at all. This can be convenient when you
temporarily wish to 'disable' a file.

synctool responds to the directory directly under `overlay/`; it selects
this subtree as a candidate when the node has a matching group. For example,

    /opt/synctool/var/overlay/wn/
      etc/ntp.conf._all

this file will only be used on worker nodes because it resides in the
overlay directory specific to the group `wn`.

> Tip: Do not make group-specific overlay directories for each and every
> group. Instead, think about what subclusters you have, and arrange your
> repository accordingly. See also chapter 5 on Best Practices.

> In synctool version 5, you would configure 'overlaydir' and synctool would
> still consider all overlay directories no matter what name the subdirectory
> had. In synctool 6, the group is strictly enforced and the subtree is
> synced to only those nodes that are in the group.
> Slave nodes are special; they get a full copy of the repository.

To populate the repository, you can `scp` files from nodes, or you can use
synctool's super convenient upload feature:

    synctool -n node1 --upload /etc/ntp.conf
    synctool -n node1 -u /etc/ntp.conf

synctool will automatically choose an extension for the file to save. If you
disagree and want a different suffix, choose one:

    synctool -n node1 --upload /etc/ntp.conf --suffix wn
    synctool -n node1 -u /etc/ntp.conf -s wn

synctool will suggest the overlay directory where to put the file in
the repository. If you disagree, use:

    synctool -n node1 --upload /etc/ntp.conf --overlay mycluster
    synctool -n node1 -u /etc/ntp.conf -o mycluster

By default synctool does a _dry run_. It will not do anything but show
what would happen if this would not be a dry run. Add `-f` or `--fix` to
really upload the file.

Now edit the the uploaded `ntp.conf`, make some changes and run synctool:

    root@masternode:/# synctool
    node1: DRY RUN, not doing any updates
    node1: /etc/ntp.conf updated (file size mismatch)

Again, synctool does a _dry run_. It shows the file is going to be updated
because there is a mismatch in the file size. Should the file size be the
same, synctool will calculate an MD5 checksum to see whether the file was
changed or not.

You may want to review your changes before applying them, or inspect the
difference between the version in the repository with what's currently
installed on a node:

    synctool -n node1 --diff /etc/ntp.conf
    synctool -n node1 -d /etc/ntp.conf

This will present a UNIX 'diff' of the files. Note the destination path in
the syntax of the command.

To apply the change, you could now run synctool with option `--fix`.
But maybe it's better to read on, we are going to have synctool automatically
reload the `ntpd` after updating the `ntp.conf` file.


3.2 Adding actions to updates
-----------------------------
Now I would like the `ntpd` to be automatically reloaded after I change
the `ntp.conf` file. This is done by adding a trigger script, in
synctool-speak known as a ".post" script.

Make a new file `overlay/all/etc/ntp.conf.post` and put only this line in it:

    service ntp reload

Make the `.post` script executable: `chmod +x ntp.conf.post`.

The `.post` script will be run when the file changes:

    root@masternode:/# synctool -f
    node1: /etc/ntp.conf updated (file size mismatch)
    node1: running command $overlay/all/etc/ntp.conf.post

The `.post` script is run after synctool updated the file, and likewise,
you may also create a `.pre` script that runs before the update:

    root@masternode:/# synctool -f
    node1: running command $overlay/all/etc/ntp.conf.pre
    node1: /etc/ntp.conf updated (file size mismatch)
    node1: running command $overlay/all/etc/ntp.conf.post

The `.pre` and `.post` scripts are executed in the directory where the
accompanying file resides; in this case `/etc/`. It is possible to add
a group extension to the script, so that you can have one group of nodes
perform different actions than another.

The scripts are run with `sh -c`. Note that `/bin/sh` is often not the
same as `bash`, so some clever shell scripting tricks may not work. However,
you can fix this by including "`#!/bin/bash`" in the top of the `.post`
script.

In the environment you will find two variables that might be useful:

* `SYNCTOOL_NODE` is set to the node that we're running on
* `SYNCTOOL_ROOT` is set to the directory where synctool lives

So expanding on that, `$SYNCTOOL_ROOT/bin/` is the bindir, and the repository
is found under `$SYNCTOOL_ROOT/var/overlay/`.

A `.post` script for a directory will trigger when any file in that directory
changes. This is particularly useful for daemons that have multiple config
files in a directory, such as `conf.d`, or, for example, `/etc/cron.d`.
A `.pre` script for a directory will only trigger if the directory does not
exist and will be created.


3.3 Other useful options
------------------------
The option `-q` of synctool gives less output:

    root@masternode:/# synctool -q
    node3: /etc/xinetd.d/identd updated (file size mismatch)

If `-q` still gives too much output, because you have many nodes in your
cluster, it is possible to specify `-a` to condense (aggregate) output.
The condensed output groups together output that is the same for many nodes.

One of my favorite commands is `synctool -qa`.
You may also use option `-a` to condense output from `dsh`, for example

    # dsh -a date

    # dsh-ping -a

The option `-f` or `--fix` applies all changes. Always be sure to run
synctool at least once as a dry run! (without `-f`).
Mind that synctool does not lock the repository and does not guard against
concurrent use by multiple sysadmins at once. In practice, this hardly ever
leads to any problems.

To update only a single file rather than all files, use the option
`--single` or `-1` (that's a number one, not the letter _ell_).
You may give multiple `--single` options to update multiple files at once.

If you want to check what file synctool is using for a given destination
file, use option `-ref` or `-r`:

    root@masternode:/# synctool -q -n node1 -r /etc/resolv.conf
    node1: /etc/resolv.conf._somegroup

synctool can be run on a subset of nodes, a group, or even on individual
nodes using the options `--node` or `-n`, `--group` or `-g`, `--exclude`
or `-x`, and `--exclude-group` or `-X`. This also works for `dsh` and friends,
and you may use the range syntax to select a range of nodes.
For example:

    # synctool -g batch,sched -X rack8

More examples:

    # dsh -n node1,node2,node3 date
    # dsh -n node[1-3] date
    # dsh -n node[01-10] -x node[05-07] hostname
    # dsh -n node[02-10/2,05,07] hostname

Copy a file to three nodes:

    # dsh-cp -n node[1-3] patchfile-1.0.tar.gz /tmp

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
from the master to the client node. You may use this option when you are
absolutely certain that the master and client are already in sync, for example
if you just ran synctool to examine any changes. In general, this option is
unnecessary, but it may be efficient if you are working with slow network
links or a large synctool repository.


3.4 Templates
-------------
For 'dynamic' config files, synctool has a feature called templates.
There are a number of rather standard configuration files that (for example)
require the IP address of a node to be listed. These are not particularly
synctool friendly. You are free to upload each and every unique instance
of the config file in question into the repository, however, if your cluster
is large this does not make your repository look very nice, nor does it
make them any easier to handle. Instead, make a template and couple it with
a `._template.post` script that calls `synctool-template` to generate the
config file on the node.

As an example, I will use a fictional snippet of config file, but this
trick applies to things like `sshd_config` with a specific `ListenAddress`
in it, and network configuration files that have static IPs configured.

    # fiction.conf._template
    MyPort 22
    MyIPAddress @IPADDR@
    SomeOption no
    PrintMotd yes

And the accompanying `fiction.conf._template.post` script:

    #! /bin/sh
    IPADDR=`ifconfig en0 | awk '/inet / { print $2 }'`
    export IPADDR
    /opt/synctool/bin/synctool-template "$1" >"$2"

This example uses `ifconfig` to get the IP address of the node. You may also
use the `ip addr` command, consult DNS or you might be able to use
`synctool-config` to get what you need.

The `synctool-template` command takes as input the template file ("`$1`")
and redirects the output to a newly generated file ("`$2`"). The "`$2`"
on the last line expands to `fiction.conf._nodename`.
Hence, synctool generates a new config file in the repository. It does so
even on dry runs; you can ask synctool to display a diff of `fiction.conf`
even though it is templated.

> Note _not_ to redirect the output of `synctool-template` directly over
> the target file. Doing that is destructive and wrong; it defies synctool's
> dry-run mode and keeps you from being able to review changes, a core
> function of synctool.

Instead of using `synctool-template`, you might use the UNIX `sed` command.
If you have multiple variables to replace, `synctool-template` is more easy.
synctool-template accepts variables either from the command-line or from
the shell environment. Like with regular `.post` scripts, the environment
variables `SYNCTOOL_NODE` and `SYNCTOOL_ROOT` are also present here.
However _unlike_ regular `.post` scripts, template post scripts require a `#!`
hashbang line. This is required for shell arguments (like "`$1`", "`$2`")
to work.

Now, when you want to change the configuration, edit the template file.
synctool will fill in the template and see the difference with the target
file.

Template files and template post scripts can have group extensions to
select different templates for certain groups of nodes.

If you want to automatically reload or restart a service after updating
`fiction.conf`, you'll also have to implement a regular `.post` script for
that: `fiction.conf.post`.


3.5 Purge directories
---------------------
In the previous sections we saw how you can use the `overlay/` and `delete/`
trees to manage your cluster. synctool has a third mechanism of syncing
files, and it works with the `purge/` tree. Purge directories are great for
mirroring entire directory trees to groups of nodes.

Unlike with the `overlay/` tree, files in the `purge/` tree do not have group
extensions. Instead, synctool will copy the entire subtree and it will
_delete_ any files on the target node that do not reside in the source tree.
So, it will make a perfect mirror of the source under `purge/`.

To populate the `purge/` tree, use `--upload` with the `--purge` option:

    # synctool -n n1 --upload /usr/local --purge compute
    # synctool -n n1 -u /usr/local -p compute

In this example, we want to upload the entire `/usr/local` tree from node `n1`
to the repository directory `/opt/synctool/var/purge/compute/`.
Afterwards, all compute nodes will get `/usr/local` synced via the purge
mechanism by running `synctool -f`.

> Purging is a blunt but effective means to synchronise directory trees.
> Mind that it will delete data that is not supposed to be there, so be
> careful with this feature. For added safety, synctool will not allow you
> to purge the root directory of a system.

Under the hood, synctool employs `rsync` to purge files. Hence, you can not
trigger actions through `.post` scripts in the purge directory, but it is
possible to use `synctool --diff`, `--ref`, and even `--single` with files
that reside under `purge/`.

Remember that purging is for making perfect mirrors. It is like sharing a
directory across nodes. Once you start differentiating directory content
between nodes, "purge" will no longer work in a satisfying way; in such a
case, you should really use `overlay/` rather than `purge/`.

`dsh-cp` also has an option `--purge` to quickly mirror directories across
nodes. Use with care.


3.6 The order of operations
---------------------------
The previous sections described a lot of operations that synctool performs
when it runs. This section summarises what we have seen so far.
For a normal synctool run, the order of operations is roughly as follows.

1. synchronise the synctool installdir to each node. This synchronises
the repository as well as the main program and config file.
Any subtrees under `overlay`, `delete`, and `purge` that do not apply for
the target node, are excluded.
2. run synctool-client on the nodes
3. synctool-client mirrors the `purge` directory
4. synctool-client processes the `overlay` directory;
 * generate templates by running `.template.post` scripts
 * compare files
      - check filetype
      - check file size
      - check MD5 checksum
      - check file ownership
      - check file mode
 * make backup copies
 * update files as needed
 * run `.post script` for any updated files
 * run `.post script` (if any) for changed directories
5. synctool-client deletes files listed in the `delete` directory
 * run `.post script` (if any) for deleted files
 * run `.post script` (if any) for changed directories


3.7 dsh-pkg, the synctool package manager
-----------------------------------------
synctool comes with a package manager named `dsh-pkg`.
Rather than being yet another package manager with its own format of packages,
dsh-pkg is a wrapper around existing package management software.
dsh-pkg unifies all the different package managers out there so you can
operate any of them using just one command and the same set of command-line
arguments. This is particularly useful in heterogeneous clusters or when
you are working with multiple platforms or distributions.

dsh-pkg supports a number of different package management systems and will
detect the appropriate package manager for the operating system of the node.
If detection fails, you may force the package manager on the command-line or
in `synctool.conf`:

    package_manager apt-get
    #package_manager yum
    #package_manager zypper
    #package_manager pacman
    #package_manager brew
    #package_manager bsdpkg

dsh-pkg knows about more platforms and package managers, but currently
only the ones listed above are implemented and supported.

> dsh-pkg is pluggable. Adding support for other package management systems
> is rather easy. If your platform and/or favorite package manager is not yet
> supported, feel free to develop your own plug-in for dsh-pkg
> or contact the author of synctool.

The `bsdpkg` module uses `freebsd-update` on FreeBSD and `pkg_add -u` on
other BSDs for upgrading packages.

Following are examples of how to use synctool-pkg.

    dsh-pkg -n node1 --list
    dsh-pkg -n node1 --list wget
    dsh-pkg -g batch --install lynx wget curl
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

If you want to further examine what dsh-pkg is doing, you may specify
`--verbose` or `--unix` to display more information about what is going on
under the hood.


3.8 Ignoring them: I'm not touching you
---------------------------------------
By using directives in the `synctool.conf` file, synctool can be told to
ignore certain files, nodes, or groups. These will be excluded, skipped.
For example:

    ignore_dotfiles no
    ignore_dotdirs yes
    ignore .svn
    ignore .gitignore .git
    ignore .*.swp

synctool will not run on ignored nodes or on nodes that are in a group that
is ignored:

    ignore_node node1 node2
    ignore_group broken


3.9 Backup copies
-----------------
For any file synctool updates, it keeps a backup copy around on the target
node with the extension `.saved`. If you don't like this, you can tell
synctool to not make any backup copies with:

    backup_copies no

It is however highly recommended that you run with `backup_copies` enabled.
You can manually specify that you want to remove backup copies using:

    synctool --erase-saved
    synctool -e

To erase a single `.saved` file, use option `--single` in combination with
`--erase-saved`.

For some (Linux) directories like `/etc/cron.d/` and `/etc/xinet.d/`, it is
not OK to keep `.saved` files around because it influences how the daemons
function. For these directories it is recommended that you implement
a `.post` script that removes the backup copies, like so:

    # $overlay/all/etc/xinetd.d.post
	rm -f *.saved
	service xinetd reload

Alternatively, you may want to move the backup copies to a safe location.


3.10 Logging
------------
When using option `--fix` to apply changes, synctool logs the made changes
to syslog on the master node. It provides a trace of what was changed on the
systems. On large clusters, this may produce a lot of log records. If you
don't want any logging, you can disable it in `synctool.conf`:

    syslogging no

When you do use syslogging, you may want to split off the synctool messages
to a separate file like `/var/log/synctool.log`. Please see your `syslogd`
manual on how to do this. In the `contrib/` directory in the synctool source,
you will find config files for use with `syslog-ng` and `logrotate`.


3.11 About symbolic links
-------------------------
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


3.12 Slow updates
-----------------
By default, synctool addresses the nodes in parallel, and they are running
updates concurrently. In some cases, like when doing rolling upgrades,
you will not want to have this parallelism. There are two easy ways around
this.

    dsh --numproc=1 uptime
    dsh -p 1 uptime

    dsh --zzz=10 uptime
    dsh -z 10 uptime

The first one tells synctool (or in this case, `dsh`) to run only one
process at a time. The second does the same thing, and sleeps for ten seconds
after running the command.

> Suppose you have a 60 node cluster, and run with `--zzz=60`.
> You now have to wait at least one hour for the run to complete.

The options `--numproc` and `--zzz` work for both `synctool` and `dsh`
programs.


3.13 Checking for updates
-------------------------
synctool can check whether a new version of synctool itself is available by
using the option `--check-update` on the master node. You can check
periodically for updates by using `--check-update` in a crontab entry.
To download the latest version, run `synctool --download` on the master node.
These functions connect to the main website at [www.heiho.net/synctool][1].

[1]: http://www.heiho.net/synctool/


3.14 Running tasks with synctool
--------------------------------
synctool's `dsh` command is ideal for running commands on groups of nodes.
On occasion, you will also want to run custom scripts with `dsh`.
These scripts can be placed in `scripts/`, and `dsh` will find them.
When running a command that resides under `scripts/`, `dsh` will sync this
script to the target node prior to running the command on the remote side.
This is done to make sure that always the 'current' version of the script
runs on the target node.

For example, if you have a script `/opt/synctool/scripts/admin_example.sh`
then you might run:

    dsh -n node1 admin_example.sh

No path to the script is required; dsh will find it.

> Previous versions had a `tasks/` directory under the repository and you
> could invoke synctool with the `--tasks` option. This mechanism has been
> obsoleted by `dsh` and the `scripts/` directory.

Note that you can write scripts to do software package installations,
but you may also use the `dsh-pkg` command.


3.15 Multiplexed connections
----------------------------
synctool and dsh can multiplex SSH connections over a 'master' connection.
This feature greatly speeds up synctool and dsh because it allows skipping
the costly SSL handshake.
Multiplexing is started through dsh:

    dsh -M          # start master connections
    dsh -O check    # check master connections
    dsh -O stop     # stop master connections
    dsh -O exit     # terminate master connections

You may also do this for certain groups or nodes, like so:

    dsh -g all -M
    dsh -n node1 -O check

synctool will detect any open control paths and use them if they are present.
The control paths (socket files) to each node are kept under synctool's temp
directory (by default: `/tmp/synctool/sshmux/`).
These control paths are managed by ssh mux processes that are running in the
background. If your cluster is very large, you might find the large number of
ssh mux processes on the management node to be objectionable. These processes
are mostly sleeping so it shouldn't pose a problem.
The control paths may be given a timeout by using the config parameter
`ssh_control_persist`. Note that this parameter is only supported for
OpenSSH 5.6 and later. The timeout may also be specified on the command-line:

    dsh -M --persist 4h

> The `ControlMaster` and `ControlPath` options of ssh first appeared in
> OpenSSH version 3.9. synctool also supports `ControlPersist`, which is
> present in OpenSSH version 5.6 and later.
> See `man ssh_config` for more information on these OpenSSH options.
