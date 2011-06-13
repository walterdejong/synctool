<h2 id="part_three">3. Using synctool</h2>
<div class="note">
In synctool terminology, a <em>node</em> is a host, a computer in a group
of computers. A group of computers is called a <em>cluster</em>.
</div>
The main power of synctool is the fact that you can define logical groups,
and you can add these to a filename as a filename extension. This will result
in the file being copied, only if the node belongs to the same group.
The groups a node is in, are defined in the
<span class="path">synctool.conf</span> file.
In the configuration file, the nodename is associated with one or more groups.
The nodename itself can also be used as a group to indicate that a file
belongs to that node.
</p>

<p>
<h3 id="#masterdir">The masterdir</h3>
Once you've installed and setup synctool, you will have a
<span class="system">masterdir</span> repository on the master node of your
cluster. This <span class="system">masterdir</span> is configured in the
<span class="path">synctool.conf</span> file, and is by default set to
<span class="path">/var/lib/synctool</span>.
</p>

<p>
synctool is usually run from the master node. It will use
<span class="cmd">rsync</span> to mirror the
<span class="system">masterdir</span> to all the nodes in the cluster.
If you do have the luxury of a high performance shared filesystem on your
cluster, you may put the masterdir on there and use the option
<span class="system">--skip-rsync</span> to skip the mirroring of the
repository.<br />
Note that it is perfectly possible to run <span class="cmd">synctool.py</span>
&lsquo;stand alone&rsquo; on a node, in which case it will check its local
copy of the repository. It will not synchronize with the master repository,
since it all works with <em>server push</em> and not client pull.
</p>

<p>
In the synctool masterdir there are by default five subdirectories, each having
its own function:
<div class="example">
* overlay/ <br />
* delete/ <br />
* scripts/ <br />
* tasks/ <br />
* sbin/
</div>
The <span class="path">overlay/</span> tree contains files that have to be
copied. When synctool detects a difference between a file on the system and a
file in the overlay tree, the file will be copied from the
<span class="path">overlay</span> tree onto the system.
</p>

<p>
The <span class="path">delete/</span> tree contains files that always have to
be deleted from the system. Only the filename matters, so it is alright if the
files in this tree are only <span class="system">0</span> bytes in size.
</p>

<p>
The executables in the <span class="path">scripts/</span> directory are
executables that synctool can run when needed. By means of the
<span class="system">on_update</span> directive in the
<span class="path">synctool.conf</span> file, a designated script may be
executed when a certain file is changed.
For example: when <span class="path">/etc/inetd.conf</span> is updated,
the script <span class="cmd">hupdaemon.sh inetd</span> must be run.
</p>

<p>
The executables in de <span class="path">tasks/</span> directory are run when
synctool is invoked with the <span class="system">-t</span> or
<span class="system">--tasks</span> argument.
This makes it possible to run scripts on hosts, which is very convenient for
doing change management.
</p>

<p>
The <span class="path">sbin/</span> directory contains the synctool programs.
Isn't this an odd place to put binaries? Yes, but these are the
&lsquo;master copies&rsquo; of the synctool software. These are also synced
to every node so that synctool can run there.
</p>

<p>
<h3 id="running_synctool">Running synctool</h3>
For example:
<div class="example">
root@masternode:/# synctool<br />
node3: DRY RUN, not doing any updates<br />
node3: /etc/xinetd.d/identd updated (file size mismatch)<br />
node3: running command /etc/init.d/xinetd reload
</div>
The file is being updated because there is a mismatch in the file size.
Should the file size be the same, synctool will calculate an MD5 checksum to
see whether the file was changed or not.
</p>

<p>
By default synctool does a <em>dry run</em>. It will not do anything but show
what would happen if this would not be a dry run.
Use <span class="system">-f</span> or <span class="system">--fix</span>
to apply any changes.
</p>

<p>
<h3 id="adding_actions_to_updates">Adding actions to updates</h3>
Now I would like the <span class="cmd">xinetd</span> to be automatically
reloaded after I change the <span class="path">identd</span> file.
There are two ways to do this in synctool:
<ol>
<li>Old, classic way; Put in <span class="path">synctool.conf</span>:
<div class="example">
on_update &nbsp; /etc/xinetd.d/identd &nbsp; &nbsp; &nbsp;
/etc/init.d/xinetd reload
</div>
</li>
<li>Modern way, much easier; Put in file
    <span class="path">$masterdir/overlay/etc/xinetd.d/identd.post</span>:
<div class="example">
/etc/init.d/xinetd reload
</div>
Use <span class="cmd">chmod</span> to make the 
<span class="system">.post</span> script executable as you would do with any
other shell script. The <span class="system">.post</span> script will be run
when the file changes:
<div class="example">
root@masternode:/# synctool -f<br />
node3: /etc/xinetd.d/identd updated (file size mismatch)<br />
node3: running command $masterdir/overlay/etc/xinetd.d/identd.post<br />
</div>
</li>
</ol>
The <span class="system">.post</span> script is executed in the directory
where the accompanying file is in, in this case
<span class="path">/etc/xinetd.d</span>. It is possible to add a group
extension to the <span class="system">.post</span> script, so that you can
have one group of nodes perform different actions than another.
</p>

<p>
The example for <span class="path">/etc/xinetd.d</span> is interesting because
you can also put an <span class="system">on_update</span> trigger or
<span class="system">.post</span> script on the directory itself.
Whenever a file in the directory gets modified, that trigger will be called.
So, we can simplify the situation for <span class="path">/etc/xinetd.d</span>
to:
<div class="example">
on_update &nbsp; /etc/xinetd.d &nbsp; &nbsp; &nbsp; /etc/init.d/xinetd reload
</div>
or <span class="path">$masterdir/overlay/etc/xinetd.d.post</span>:
<div class="example">
/etc/init.d/xinetd reload
</div>
</p>

<p>
<h3 id="special_groups">Special groups</h3>
The next example shows that the nodename can be used as a group.
In the example, the <span class="path">fstab</span> file is identical
throughout the cluster, with the exception of node5 and node7.
<div class="example">
root@masternode:/# ls -F /var/lib/synctool/overlay/etc<br />
fstab._all &nbsp; &nbsp; motd.production._batch &nbsp; sudoers._all<br />
fstab._node5 &nbsp; nsswitch.conf._all &nbsp; &nbsp; &nbsp; sysconfig/<br />
fstab._node7 &nbsp; nsswitch.conf.old._all &nbsp; sysctl.conf._all
</div>
Group <span class="system">all</span> implictly applies to all nodes.
Likewise, there is an implicit group <span class="system">none</span> that
applies to no nodes. Group <span class="system">none</span> can be
convenient when you to have a copy of a file around, but do not wish to push
it to any nodes yet.
</p>

<p>
<h3 id="useful_options">Useful options</h3>
The <span class="system">-q</span> option of synctool gives less output:
<div class="example">
root@masternode:/# synctool -q<br />
node3: /etc/xinetd.d/identd updated (file size mismatch)
</div>
If <span class="system">-q</span> still gives too much output, because you
have many nodes in your cluster, it is possible to specify
<span class="system">-a</span> to condense (aggregate) output. The condensed
output groups together output that is the same for many nodes.<br />
<span class="cmd">synctool -qa</span> is one of my favorite commands.
synctool does this by piping the output through the
<span class="cmd">synctool-aggr</span> command. You may also use this to
condense output from <span class="cmd">dsh</span>, for example
<div class="example">
# dsh date | synctool-aggr
</div>
or just
<div class="example">
# dsh -a date<br />
<br />
# dsh-ping -a
</div>
The <span class="system">-f</span> or <span class="system">--fix</span> option
applies all changes. Always be sure to run synctool
at least once as a dry run! (without <span class="system">-f</span>).
Mind that synctool does not lock the repository and does not guard against
concurrent use by multiple sysadmins at once. In practice, this hardly ever
leads to any problems.
</p>

<p>
To update only a single file rather than all files, use the option
<span class="system">--single</span> or <span class="system">-1</span>
(that's a number one, not the letter <em>ell</em>).
</p>

<p>
If you want to check what file synctool is using for a given destination
file, use the <span class="system">-r</span> or
<span class="system">--ref</span> option:
<div class="example">
root@masternode:/# synctool -q -n node1 -r /etc/resolv.conf<br />
node1: /etc/resolv.conf._somegroup
</div>
To inspect differences between the master copy and the client copy of a file,
use <span class="system">--diff</span> or <span class="system">-d</span>.
</p>

<p>
synctool can be run on a subset of nodes, a group, or even on individual
nodes using the options <span class="system">--group</span> or
<span class="system">-g</span>, <span class="system">--node</span>
or <span class="system">-n</span>, <span class="system">--exclude</span>
or <span class="system">-x</span>, and <span class="system">--exclude-group</span>
or <span class="system">-X</span>. This also works for
<span class="cmd">dsh</span> and <span class="cmd">dcp</span>, as well as
<span class="cmd">dsh-ping</span>. For example:
<div class="example">
# synctool -g batch,sched -X rack8
</div>
Another example:
<div class="example">
# dsh -n node1,node2,node3 date
</div>
or copy a file to these three nodes:
<div class="example">
# dcp -n node1,node2,node3 -d /tmp patchfile-1.0.tar.gz
</div>
You may also wish to pull a file from a node into the repository. You can do
this from the masternode like this:
<div class="example">
# synctool -n node1 --upload /path/to/file
</div>
It may be desirable to give the file a different group extension than the
default proposed by synctool:
<div class="example">
# synctool -n node1 --upload /path/to/file --suffix=somegroup
</div>
After rebooting a cluster, use dsh-ping to see if the nodes respond to ping
yet. You may also do this on a group of nodes:
<div class="example">
# dsh-ping -g rack4
</div>
The <span class="system">-t</span> or <span class="system">--tasks</span>
option runs the de executables that are in <span class="path">tasks/</span>
(if you also supply <span class="system">-f</span>..!)
These executables can also have group names as filename extension.
They can be shell scripts or any other kind of executables.
This option is particularly useful for making system changes
that cannot be done easily by replacing a configuration file, like for
example installing new software packages. Mind to always include a check to
see whether the system change has already been made, or else it will always
keep installing the same software when it was already there. Doing system
changes through the tasks mechanism is recommended for two reasons:
<ul>
<li>It is easy to see what changes are being done; all tasks are in
    <span class="system">tasks/</span></li>
<li>Whenever a node is down, it can do the updates later to get back in sync
    </li>
</ul>
By default, <span class="system">--tasks</span> is not being run.
You have to explicitly specify this argument to run tasks.
</p>

<p>
The <span class="system">-v</span> option gives verbose output.
This is another way of displaying the logic that synctool performs:
<div class="example">
# synctool -v<br />
node3: checking $masterdir/overlay/etc/tcpd_banner.production._all<br />
node3: overridden by $masterdir/overlay/etc/tcpd_banner.production._batch<br />
node3: checking $masterdir/overlay/etc/issue.net.production._all<br />
node3: checking $masterdir/overlay/etc/syslog.conf._all<br />
node3: checking $masterdir/overlay/etc/issue.production._all<br />
node3: checking $masterdir/overlay/etc/modules.conf._all<br />
node3: checking
$masterdir/overlay/etc/hosts.allow.production._interactive<br />
node3: skipping
$masterdir/overlay/etc/hosts.allow.production._interactive,<br />
it is not one of my groups
</div>
The <span class="system">--unix</span> option produces
<span class="smallcaps">UNIX</span>-style output.
This shows in standard shell syntax just what synctool is about to do.
<div class="example">
root@masternode:/# synctool --unix<br />
node3: # updating file /etc/xinetd.d/identd<br />
node3: mv /etc/xinetd.d/identd /etc/xinetd.d/identd.saved<br />
node3: umask 077<br />
node3: cp /var/lib/synctool/overlay/etc/xinetd.d/identd._all
/etc/xinetd.d/identd<br />
node3: chown root.root /etc/xinetd.d/identd<br />
node3: chmod 0644 /etc/xinetd.d/identd<br />
node3:<br />
node3: # run command /bin/rm /etc/xinetd.d/*.saved ;
/etc/init.d/xinetd reload<br />
node3: /bin/rm /etc/xinetd.d/*.saved ; /etc/init.d/xinetd reload<br />
</div>
<div class="note">
synctool does not apply changes by executing shell commands; all
operations are programmed in Python. The <span class="system">--unix</span>
option is only a way of displaying what synctool does, and may be useful
when debugging.
</div>
The <span class="system">--skip-rsync</span> option skips the
<span class="cmd">rsync</span> run that copies the repository from the master
server to the client node. You should only specify this
option when your repository resides on a shared filesystem. Sharing the
repository between your master server and client nodes has certain security
implications, so be mindful of what you are doing in such a setup.
If you have a fast shared filesystem between all client nodes, but it is
not shared with the master server, you may want to write a wrapper script
around synctool that first runs <span class="cmd">rsync</span> to a
single node to update the shared repository, and then run synctool with
the <span class="system">--skip-rsync</span> option.
</p>

<p>
<h3 id="logging">Logging</h3>
When using <span class="system">--fix</span> to apply changes, synctool can
log the performed actions in a log file.
Use the <span class="system">logfile</span> directive in
<span class="path">synctool.conf</span> to specify that you want logging:
<div class="example">
logfile /var/log/synctool.log
</div>
synctool will write this logfile on each node seperately, and a concatenated
log on the master node.
</p>

<p>
<h3 id="ignoring">Ignoring them: I'm not touching you</h3>
By using directives in the <span class="path">synctool.conf</span> file,
synctool can be told to ignore certain files, nodes, or groups.
These will be excluded, skipped. For example:
<div class="example">
ignore_dotfiles no<br />
ignore_dotdirs yes<br />
ignore .svn<br />
ignore .gitignore .git<br />
ignore *.swp<br />
ignore_node node1 node2<br />
ignore_group oldgroup<br />
ignore_group test
</div>
</p>

<p>
<h3 id="about_symlinks">About symbolic links</h3>
On the Linux operating system, symbolic links always have mode 0777
(shown in the directory as mode <span class="system">lrwxrwxrwx</span>).
This is awkward, because this mode seems to imply that owners, group members,
and others have write access to the symbolic link &mdash;
which is not the case. This results in synctool complaining about the mode
of the symbolic link:
<div class="example">
/path/subdir/symlink should have mode 0755 (symlink), but has 0777
</div>
As a workaround, synctool forces the mode of the symbolic link to what
you set it to in <span class="system">synctool.conf</span>.
The hardcoded default value is 0755. Linux users should configure the
value 0777 in <span class="system">synctool.conf</span>:
<div class="example">
# Linux<br />
symlink_mode 0777
</div>
<div class="example">
# sensible mode for most other UNIX systems<br />
symlink_mode 0755
</div>
<div class="note">
<em>unix.com</em> says about this:
<p>
&ldquo;The permission settings on a symbolic link are a little special
[as well]. They are completely ignored. Many versions of
<span class="smallcaps">Unix</span> have no way to change them.&rdquo;
</p>
</div>
As synctool requires all files in the repository to have an extension,
symbolic links must have extensions too. Symbolic links in the repository
will be <em>dead</em> symlinks but they will point to the correct destination
on the target node.
Consider the following example, where <span class="system">file</span> does
not exist &lsquo;as is&rsquo; in the repository:
<div class="example">
$masterdir/overlay/etc/motd._red -&gt; file<br />
$masterdir/overlay/etc/file._red
</div>
<h3 id="backup_copies">Backup copies</h3>
For any file synctool updates, it keeps a backup copy around on the target
node with the extension <span class="system">.saved</span>. If you don't
like this, you can tell synctool to not make any backup copies with:
<div class="example">
backup_copies no
</div>
It is however highly recommended that you run with
<span class="system">backup_copies</span> enabled.
You can manually specify that you want to remove all backup copies using
<span class="cmd">synctool -e</span> or
<span class="cmd">synctool --erase-saved</span>.
</p>

<p>
<h3 id="local_config">Node-specific local configuration adjustments</h3>
The settings in <span class="path">synctool.conf</span> can be overridden
locally by including a second config file that is present on the node.
</p>

<p>
<span class="system">synctool.conf</span>:
<div class="example">
include /etc/synctool_local.conf
</div>
The local config file may contain the same directives as the master config
file, but apply only to the node on which the file resides. The local config
file may be managed from the master repository, enabling you to have subtle
differences in the synctool configuration for certain nodes. For example,
this can be used to change the <span class="system">symlink_mode</span>
in heterogeneous clusters.
Beware that the local config file is read upon startup and may be synced
afterwards, if the file was changed.<br />
Mind that including node specific configs increases the complexity of your
overall synctool configuration, so in general it is recommended that you
stick to using the master <span class="path">synctool.conf</span> only,
and not including any local configs at all.
</p>

<p>
The <span class="system">include</span> keyword can also be used to
clean up your config a little, for example:
<div class="example">
include /var/lib/synctool/nodes.conf<br />
include /var/lib/synctool/colors.conf<br />
include /var/lib/synctool/on_update.conf
</div>
In this example all the nodes get the same config, because the masterdir
<span class="path">/var/lib/synctool/</span> is synced to all nodes.
</p>

<p>
<h3 id="checking_for_updates">Checking for updates</h3>
synctool can check whether a new version of synctool itself is available by
using the <span class="system">--check-update</span> option on the master node.
You can check periodically for updates by using
<span class="system">--check-update</span> in a crontab entry.
To download the latest version, run <span class="cmd">synctool --download</span>
on the master node. These functions connect to the main website at
<a href="http://www.heiho.net/synctool/">http://www.heiho.net/synctool</a>.
</p>

<p>
<h3 id="using_synctool_pkg">synctool-pkg, the synctool package manager</h3>
synctool comes with a package manager named <span class="cmd">synctool-pkg</span>.
Rather than being yet another package manager with its own format of packages,
synctool-pkg is a wrapper around existing package management software.
synctool-pkg unifies all the different package managers out there so you can
operate any of them using just one command and the same set of command-line
arguments. This is particularly useful in heterogeneous clusters or when
you are working with multiple platforms or distributions.<br />
synctool-pkg may also be invoked as <span class="cmd">dsh-pkg</span>
and works a lot like regular <span class="cmd">dsh</span>.
</p>

<p>
synctool-pkg supports a number of different package management systems.
Unless explicitly defined in <span class="path">synctool.conf</span>,
synctool-pkg will detect the system's operating system and its package manager.
If detection fails, you may force the package manager in
<span class="path">synctool.conf</span>:
<div class="example">
package_manager apt-get<br />
#package_manager yum<br />
#package_manager zypper<br />
#package_manager pacman<br />
#package_manager brew
</div>
synctool-pkg knows about more platforms and package managers, but currently
only the ones listed above are implemented and supported.
<div class="note">
synctool-pkg is pluggable. Adding support for other package management systems
is rather easy. If your platform and/or favorite package manager is not yet
supported, feel free to develop your own plug-in for synctool-pkg or contact
the author of synctool.
</div>
</p>

<p>
Following are examples of how to use synctool-pkg.
<div class="example">
synctool-pkg -n node1 --list<br />
synctool-pkg -n node1 --list wget<br />
synctool-pkg -g batch --install lynx wget curl<br />
dsh-pkg -g batch -x node3 --remove somepackage
</div>
Sometimes you need to refresh the contents of the local package database.
You can do this with the &lsquo;update&rsquo; command:
<div class="example">
dsh-pkg -qa --update
</div>
You may check for software upgrades for the node with
<span class="system">--upgrade</span>. This will only show what upgrades are
available. To really upgrade a node, specify <span class="system">--fix</span>.
It is wise to always test an upgrade on a single node.
<div class="example">
dsh-pkg --upgrade<br />
dsh-pkg -n testnode --upgrade -f<br />
dsh-pkg --upgrade -f
</div>
Package managers download their packages into an on-disk cache. Sometimes the
disk fills up and you may want to clean out the disk cache:
<div class="example">
dsh-pkg -qa --clean
</div>
A specific package manager may be selected from the command-line. This is
primarily meant as a future extension so BSD users can temporarily switch to
the <span class="system">ports</span> system.
<div class="example">
dsh-pkg -m yum -i somepackage &nbsp; &nbsp; # force it to use yum
</div>
If you want to further examine what synctool-pkg is doing, you may specify
<span class="system">--verbose</span> or <span class="system">--unix</span>
to display more information about what is going on under the hood.
</p>
