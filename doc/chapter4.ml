<h2 id="part_four">4. All configuration parameters explained</h2>
This chapter lists and explains all parameters that you can use in
synctool's configuration file.

<dl>
<dt>masterdir &lt;directory&gt;</dt>
<dd>Directory that is the base path to the repository. The default value is
<span class="path">/var/lib/synctool</span>. The order of the statements in
the <span class="path">synctool.conf</span> file is generally not important,
but if you want to use the <span class="system">$masterdir</span> macro in
the config file, you must define <span class="system">masterdir</span> first.
</dd>

<dt>overlaydir &lt;directory&gt;</dt>
<dd><b>obsolete</b><br />
This directory is hardcoded as <span class="system">$masterdir/overlay/</span>.
</dd>

<dt>deletedir &lt;directory&gt;</dt>
<dd><b>obsolete</b><br />
This directory is hardcoded as <span class="system">$masterdir/delete/</span>.
</dd>

<dt>tasksdir &lt;directory&gt;</dt>
<dd><b>obsolete</b><br />
synctool can no longer run tasks. If you still want this functionality,
please use <span class="cmd">dsh</span> instead.
</dd>

<dt>scriptdir &lt;directory&gt;</dt>
<dd><b>obsolete</b><br />
synctool no longer supports <span class="system">scriptdir</span>.
Please use <span class="system">.post</span> scripts instead.
</dd>

<dt>tempdir &lt;directory&gt;</dt>
<dd>Directory where the synctool master will create temporary files.<br />
Default value is <span class="path">/tmp/synctool</span>. There may
be only one <span class="system">tempdir</span> defined and it must be an
absolute path.
</dd>

<dt>symlink_mode &lt;octal number&gt;</dt>
<dd>Specifies the <span class="smallcaps">UNIX</span> file mode for symbolic
links. This value is an octal number.<br />
Default value is
<span class="system">0755</span> and should do for most platforms.
For Linux, set this value to <span class="system">0777</span>.
</dd>

<dt>require_extension &lt;yes/no&gt;</dt>
<dd>When set to &ldquo;yes,&rdquo; a generic file in the
repository must have the extension <span class="system">.all</span>.
When set to &ldquo;no,&rdquo; an extension is not required and the group
<span class="system">all</span> is automatically implied.<br />
Default value is <span class="system">yes</span>.
</dd>

<dt>backup_copies &lt;yes/no&gt;</dt>
<dd>When set to &ldquo;yes,&rdquo; synctool creates backup copies on the
target nodes of files that it updates. These backup files will be named
<span class="path">*.saved</span>.<br />
Default value for this parameter is <span class="system">yes</span>.
</dd>

<dt>ignore_dotfiles &lt;yes/no&gt;</dt>
<dd>Setting this to &ldquo;yes&rdquo; results in synctool ignoring all
files in the repository that begin with a dot. This can be convenient like
for example for <span class="path">.bashrc</span> and
<span class="path">.gitignore</span>.<br />
Default value is <span class="system">no</span>.
</dd>

<dt>ignore_dotdirs &lt;yes/no&gt;</dt>
<dd>Setting this to &ldquo;yes&rdquo; results in synctool ignoring all
directories in the repository that begin with a dot. This can be convenient
like for example for <span class="path">.svn/</span>.<br />
Default value is <span class="system">no</span>.
</dd>

<dt>ignore &lt;filename or directory name&gt; [..]</dt>
<dd>This parameter enables you to have synctool ignore specific files or
directories in the repository.
Multiple <span class="system">ignore</span> definitions are allowed.
You may put multiple filenames on a line, and you may use wildcards.<br />
Example:
<div class="example">
ignore .gitignore .git .svn<br />
ignore .*.swp<br />
ignore tmp[0-9][0-9][0-9]??
</div>
</dd>

<dt>ignore_file &lt;filename&gt;</dt>
<dd><b>obsolete<b><br />
Use the <span class="system">ignore</span> keyword.
</dd>

<dt>ignore_files &lt;filename&gt;</dt>
<dd><b>obsolete<b><br />
Use the <span class="system">ignore</span> keyword.
</dd>

<dt>ignore_dir &lt;filename&gt;</dt>
<dd><b>obsolete<b><br />
Use the <span class="system">ignore</span> keyword.
</dd>

<dt>ignore_dirs &lt;filename&gt;</dt>
<dd><b>obsolete<b><br />
Use the <span class="system">ignore</span> keyword.
</dd>

<dt>logfile &lt;filename&gt;</dt>
<dd>Have synctool log any updates to file. Nothing is logged for dry runs.<br />
By default, no logfile is specified.<br />
Example:
<div class="example">
logfile /var/log/synctool.log
</div>
Mind that synctool does not rotate the logfile by itself.
</dd>

<dt>diff_cmd &lt;diff UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">diff</span>.
&nbsp; synctool runs this command when you use the <span class="system">--diff</span>
option.  The exact location and arguments of the <span class="cmd">diff</span>
command are operating system specific; the PATH environment variable will
be searched for the command if you do not supply a full path.<br />
There is no default, but synctool ships with the following in the
example configuration file:
<div class="example">
diff_cmd diff -u
</div>
</dd>

<dt>ping_cmd &lt;ping UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">ping</span>.
&nbsp; <span class="cmd">dsh-ping</span> uses this command to check what nodes
are responding. The exact location and arguments of the <span class="cmd">ping</span>
command are operating system specific; the PATH environment variable will
be searched for the command if you do not supply a full path.<br />
There is no default, but synctool ships with the following in the example
configuration file:
<div class="example">
ping_cmd ping -q -c 1 -t 1
</div>
</dd>

<dt>ssh_cmd &lt;ssh UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">ssh</span>.
&nbsp; synctool and <span class="cmd">dsh</span> use this command to execute
remote commands on the target nodes.
The exact location of the <span class="cmd">ssh</span> command is operating
system specific; the PATH environment variable will
be searched for the command if you do not supply a full path.<br />
There is no default, and you must configure this parameter correctly for
synctool to work. synctool ships with the following sensible setting in the
example configuration file:
<div class="example">
ssh -o ConnectTimeout=10 -x -q
</div>
</dd>

<dt>scp_cmd &lt;scp UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">scp</span>.
&nbsp; <span class="cmd">dcp</span> uses this command to do a remote copy
of files to the target nodes.
The exact location of the <span class="cmd">scp</span> command is operating
system specific; the PATH environment variable will
be searched for the command if you do not supply a full path.<br />
There is no default, but synctool ships with the following in the example
configuration file:
<div class="example">
scp -o ConnectTimeout=10 -p
</div>
</dd>

<dt>rsync_cmd &lt;rsync UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">rsync</span>.
&nbsp; synctool uses this command to distribute the repository to the target
nodes. The exact location of the <span class="cmd">rsync</span> command is
operating system specific; the PATH environment variable will be searched for
the command if you do not supply a full path.<br />
Unless you keep the repository in a high performance shared filesystem,
you must configure this parameter correctly for synctool to work.<br />
There is no default, but synctool ships with the following in the example
configuration file:
<div class="example">
rsync -ar --numeric-ids --delete --delete-excluded -e 'ssh -o ConnectTimeout=10 -x -q' -q
</div>
</dd>

<dt>synctool_cmd &lt;synctool UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">synctool.py</span>.
&nbsp; This is needed because synctool executes <span class="cmd">synctool.py</span>
on the target nodes.
The exact location of the <span class="cmd">synctool.py</span> command is
installation dependent.<br />
There is no default, and you must configure this parameter correctly for
synctool to work. synctool ships with the following sensible setting in the
example configuration file:
<div class="example">
synctool_cmd $masterdir/sbin/synctool.py
</div>
</dd>

<dt>pkg_cmd &lt;synctool_pkg UNIX command&gt;</dt>
<dd>Give the command and arguments to execute <span class="cmd">synctool_pkg.py</span>.
&nbsp; This is needed because synctool-pkg executes <span class="cmd">synctool_pkg.py</span>
on the target nodes.
The exact location of the <span class="cmd">synctool_pkg.py</span> command is
installation dependent.<br />
There is no default, and you must configure this parameter correctly for
synctool-pkg to work. synctool ships with the following sensible setting in the
example configuration file:
<div class="example">
pkg_cmd $masterdir/sbin/synctool_pkg.py -c $masterdir/synctool.conf
</div>
</dd>

<dt>package_manager &lt;package management system&gt;</dt>
<dd>Specify the package management system that synctool-pkg must use.
If left out, synctool-pkg will detect what package manager it should use, but
using this parameter you can force it if detection fails. This setting can be
overridden from the command-line when invoking
<span class="cmd">synctool-pkg</span>.<br />
Valid values for <span class="system">package_manager</span> are:
<span class="system">apt-get</span>, <span class="system">yum</span>,
<span class="system">zypper</span>, <span class="system">pacman</span>,
<span class="system">brew</span>, and <span class="system">bsdpkg</span>.
</dd>

<dt>num_proc &lt;number&gt;</dt>
<dd>This specifies the maximum amount of parallel processes that synctool
will use. For large clusters, you will want to increase this value, but mind
that this will increase the load on your master node. Setting this value
higher than the amount of nodes you have, has no effect.<br />
The default hardcoded value is <span class="system">16</span>.
</dd>

<dt>full_path &lt;yes/no&gt;</dt>
<dd>synctool likes to abbreviate paths to
<span class="path">$masterdir/overlay/some/dir/file</span>.
When you set this option to &ldquo;no, &rdquo; synctool will display the true
full path instead of the abbreviated one.<br />
Default value is <span class="system">no</span>.
</dd>

<dt>default_nodeset &lt;group-or-node&gt; [..]</dt>
<dd>
By default, synctool will run on these nodes or groups. You can use this to
make synctool by default work on only a subcluster rather than your whole
installation.<br />
The default value is <span class="system">all</span>. You may set it to
<span class="system">none</span> to make synctool not run on a default set of
nodes at all.
<br />
Example:
<div class="example">
default_nodeset test1 test2
</div>
</dd>

<dt>group &lt;groupname&gt; &lt;subgroup&gt; [..]</dt>
<dd>
The <span class="system">group</span> keyword defines <em>compound</em>
groups. It is a means to group several subgroups together into a single group.
If the subgroups did not exist yet, they are defined automatically as new,
empty groups.<br />
Example:
<div class="example">
group wn workernode batch<br />
group test wn<br />
group g1 batch test wn
</div>
Group names are alphanumeric, but can have an underscore, minus, or plus
symbol in between. The following are valid group names:
<div class="example">
group group1 group-1 group_1 group+1 192_168_1 10 node1+node2
</div>
</dd>

<dt>node &lt;nodename&gt; &lt;group&gt; [..] [ipaddress:&lt;IP address&gt;]
  [hostname:&lt;fully qualified hostname&gt;] [hostid:&lt;filename&gt;]</dt>
<dd>The <span class="system">node</span> keyword defines what groups a node
is in. Multiple groups may be given. The order of the groups is important;
the left-most group is most important, and the right-most group is least
important. What this means is that if there are files in repository that have
the same base filename, but a different group extension, synctool will pick
the file that has the most important group extension for this node.<br />
Groups can be defined &lsquo;on the fly,&rsquo; there is no need for a group
to exist before it can be used in a node definition.<br />
The <span class="system">ipaddress</span> specifier tells synctool how to
contact the node. This is optional; when omitted, synctool assumes the
nodename can be found in DNS. Note that synctool nodenames need not be same
as DNS names.<br />
The optional <span class="system">hostname</span> specifier tells synctool that
a host that has this fully qualified hostname, must be this node. In general
it is safe to omit this, but there are cases (particularly multi-homed systems)
where synctool can not figure out what node it is running on.
This may happen when the <span class="system">ipaddress</span> does not
directly map to the nodename, or when the hostname is different from the
nodename. synctool can not magically know what node it is running on when
this is the case. The property that uniquely identifies a host is its hostname.
You can instruct synctool that this node is the host with the corresponding
hostname.<br />
The optional <span class="system">hostid</span> specifier can be used in the
unusual case where the hostname does not uniquely identify a host, so when
you have multiple hosts that have the same hostname. The filename argument
is a file on the target node that contains the &ldquo;synctool hostname&rdquo;
that will be used to uniquely identify the host.<br />
<div class="note">
synctool uses the <span class="system">socket.getfqdn()</span> function to
determine the fully qualified name of the host. If synctool is not finding the
node for the specified hostname, you should really fix your DNS or
<span class="path">/etc/hosts</span> file.
</div>
Example:
<div class="example">
node node0 master<br />
<br />
node node1 fs sched rack1 ipaddress:node1-mgmt<br />
node node2 login &nbsp; &nbsp;rack1 ipaddress:node2-mgmt
  hostname:login.mydomain.com<br />
node node3 wn &nbsp; &nbsp; &nbsp; rack1 ipaddress:node3-mgmt<br />
node node4 wn &nbsp; &nbsp; &nbsp; rack1 ipaddress:node4-mgmt<br />
node node5 wn &nbsp; &nbsp; &nbsp; rack1 ipaddress:node5-mgmt<br />
node node6 wn &nbsp; &nbsp; &nbsp; rack1 ipaddress:node6-mgmt<br />
node node7 wn &nbsp; &nbsp; &nbsp; rack1 ipaddress:node7-mgmt<br />
node node8 test &nbsp; &nbsp; rack1 ipaddress:node8-mgmt<br />
node node9 batch &nbsp; &nbsp;rack1 ipaddress:node9-mgmt
</div>
Node names are alphanumeric, but can have an underscore, minus, or plus
symbol in between. The following are valid node names:
<div class="example">
node node1 node-1 node_1 node+1 10_0_0_2 10 node1+node2
</div>
</dd>

<dt>ignore_node &lt;nodename&gt; [..]</dt>
<dd>This tells synctool to ignore one or more nodes. You can use this if you
want to skip this node for a while for some reason, for example because it
is broken.<br />
</dd>

<dt>ignore_group &lt;group&gt; [..]</dt>
<dd>This tells synctool to ignore one or more groups. You can use this to
temporarily disable the group. This can be particularly useful when doing
software upgrades.
</dd>

<dt>on_update &lt;filename&gt; &lt;shell command&gt;</dt>
<dd><b>obsolete<b><br />
This mechanism is no longer available, because it doesn't play nice with
multi-platform setups. Please use (the more flexible and powerful)
<span class="system">.post</span> scripts instead.
</dd>

<dt>always_run &lt;shell command&gt;</dt>
<dd><b>obsolete<b><br />
This mechanism is no longer available. If you still want this functionality,
wrap the <span class="system">synctool_cmd</span> command with a shell script.
</dd>

<dt>include &lt;local synctool config file&gt;</dt>
<dd>This keyword includes a synctool configuration file that is located on
the target node. You can use this to give certain nodes a slightly different
synctool configuration than others. This can be important, especially in
heterogeneous clusters.<br />
Example:
<div class="example">
include /etc/synctool_local.conf
</div>
</dd>

<dt>terse &lt;yes/no&gt;</dt>
<dd>In terse mode, synctool shows a very brief output with paths abbreviated
to <span class="path">//overlay/dir/.../file</span>.
Default value is <span class="system">no</span>.
</dd>

<dt>colorize &lt;yes/no&gt;</dt>
<dd>In terse mode, synctool output can be made to show colors. Mind that this
parameter only works when <span class="system">terse</span> is set to
<span class="system">yes</span>.<br />
Default value is <span class="system">yes</span>.
</dd>

<dt>colorize_full_line &lt;yes/no&gt;</dt>
<dd>In terse mode, synctool output can be made to show colors. This option
colors the full output line rather than just the leading keyword.
Mind that this parameter only works when both <span class="system">terse</span>
and <span class="system">colorize</span> are enabled.<br />
Default value is <span class="system">no</span>.
</dd>

<dt>colorize_bright &lt;yes/no&gt;</dt>
<dd>In terse mode, synctool output can be made to show colors. This option
enables the bright/bold attribute for colors.
Mind that this parameter only works when both <span class="system">terse</span>
and <span class="system">colorize</span> are enabled.<br />
Default value is <span class="system">yes</span>.
</dd>

<dt>colorize_bold &lt;yes/no&gt;</dt>
<dd>Same as <span class="system">colorize_bright</span>.</dt>

<div class="note">
Following are keywords to customize colors. Valid color codes are:
<span class="system">default</span>, <span class="system">bold</span>,
<span class="system">white</span>, <span class="system">black</span>,
<span class="system">darkgray</span>, <span class="system">red</span>,
<span class="system">green</span>, <span class="system">yellow</span>,
<span class="system">blue</span>, <span class="system">magenta</span>,
and <span class="system">cyan</span>.
</div>

<dt>color_info &lt;color&gt;</dt>
<dd>Specify the color for informational messages in terse mode.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_warn &lt;color&gt;</dt>
<dd>Specify the color for warnings in terse mode.<br />
Default value is <span class="system">magenta</span>.
</dd>

<dt>color_error &lt;color&gt;</dt>
<dd>Specify the color for error messages in terse mode.<br />
Default value is <span class="system">red</span>.
</dd>

<dt>color_fail &lt;color&gt;</dt>
<dd>Specify the color for failure messages in terse mode.<br />
Default value is <span class="system">red</span>.
</dd>

<dt>color_sync &lt;color&gt;</dt>
<dd>Specify the color for <em>sync</em> messages in terse mode. These occur
when synctool synchronizes file data.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_link &lt;color&gt;</dt>
<dd>Specify the color for <em>link</em> messages in terse mode. These occur
when synctool creates or repairs a symbolic link.<br />
Default value is <span class="system">cyan</span>.
</dd>

<dt>color_mkdir &lt;color&gt;</dt>
<dd>Specify the color for <em>mkdir</em> messages in terse mode. These occur
when synctool creates a driectory.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_rm &lt;color&gt;</dt>
<dd>Specify the color for <em>rm</em> messages in terse mode. These occur when
synctool deletes a file.<br />
Default value is <span class="system">yellow</span>.
</dd>

<dt>color_chown &lt;color&gt;</dt>
<dd>Specify the color for <em>chown</em> messages in terse mode. These occur
when synctool changes the ownership of a file or directory.<br />
Default value is <span class="system">cyan</span>.
</dd>

<dt>color_chmod &lt;color&gt;</dt>
<dd>Specify the color for <em>chmod</em> messages in terse mode. These occur
when synctool changes the access mode of a file or directory.<br />
Default value is <span class="system">cyan</span>.
</dd>

<dt>color_exec &lt;color&gt;</dt>
<dd>Specify the color for <em>exec</em> messages in terse mode. These occur
when synctool executes a <span class="system">.post</span> script or
<span class="system">on_update</span> command.<br />
Default value is <span class="system">green</span>.
</dd>

<dt>color_upload &lt;color&gt;</dt>
<dd>Specify the color for <em>upload</em> messages in terse mode. These occur
when use synctool to upload a file.<br />
Default value is <span class="system">magenta</span>.
</dd>

<dt>color_new &lt;color&gt;</dt>
<dd>Specify the color for <em>new</em> messages in terse mode. These occur when
a sync operation requires synctool to create a new file.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_type &lt;color&gt;</dt>
<dd>Specify the color for <em>type</em> messages in terse mode. These occur
when the file type of the entry in the repository does not match the file type
of the target file.<br />
Default value is <span class="system">magenta</span>.
</dd>

<dt>color_dryrun &lt;color&gt;</dt>
<dd>Specify the color for the &lsquo;DRYRUN&rsquo; message in terse mode.
It occurs when synctool performs a dry run.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_fixing &lt;color&gt;</dt>
<dd>Specify the color for the &lsquo;FIXING&rsquo; message in terse mode.
It occurs when synctool is run with the <span class="system">--fix</span>
option.<br />
Default value is <span class="system">default</span>.
</dd>

<dt>color_ok &lt;color&gt;</dt>
<dd>Specify the color for the &lsquo;OK&rsquo; message in terse mode.
It occurs when files are up to date.<br />
Default value is <span class="system">default</span>.
</dd>

</dl>
