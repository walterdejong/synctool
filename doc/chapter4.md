4. All configuration parameters explained
=========================================
This chapter lists and explains all parameters that you can use in
synctool's configuration file.

* `masterdir <directory>`

  **obsolete** This used to be the directory where `overlay/` and `delete/`
  reside. In recent versions, this directory must be under the synctool root.
  The equivalent of `masterdir` would now be `/opt/synctool/var/`.

* `overlaydir <directory>`

  **obsolete** This directory is now hardcoded as `ROOTDIR/var/overlay/`.

* `deletedir <directory>`

  **obsolete** This directory is now hardcoded as `ROOTDIR/var/delete/`.

* `tasksdir <directory>`

  **obsolete** synctool no longer runs tasks. If you still want this
  functionality, please use `dsh` instead. You may use the `scriptdir` to
  store your (task) scripts.

* `scriptdir <directory>`

  **obsolete** This directory is now hardcoded as `ROOTDIR/scripts/`.

* `tempdir <directory>`

  Directory where the synctool master will create temporary files.
  The default is `/tmp/synctool`. There may be only one `tempdir` defined
  and it must be an absolute path.

* `symlink_mode <octal number>`

  **obsolete** synctool now handles symbolic links in the correct way.

* `ssh_control_persist <time|yes|none>`

  This parameter maps directly to the OpenSSH `ControlPersist`.
  It sets the default timeout for multiplexed connections, using `dsh -M`.
  This parameter may be overridden on the command-line with `dsh --persist`.
  The time argument is a string like "1h" or "1h30m". When it is "yes",
  there is no timeout, and it will persist indefinitely until the master
  is stopped or terminated with `dsh -O stop` or `dsh -O exit`.
  Note that OpenSSH supports "`ControlPersist=no`", but synctool does not.
  It can be set to `none` to call `ssh` without `-o ControlPersist` option.
  The default timeout is 1 hour. This parameter only has effect for OpenSSH
  version 5.6 and later.

* `require_extension <yes/no>`

  When set to 'yes', a generic file in the repository must have the extension
  `'.all'`. When set to 'no' an extension is not required and the group
  `all` is automatically implied.
  The default is `yes`.

* `backup_copies <yes/no>`

  When set to 'yes', synctool creates backup copies on the target nodes of
  files that it updates. These backup files will be named `*.saved`.
  The default for this parameter is `yes`.

* `ignore_dotfiles <yes/no>`

  Setting this to 'yes' results in synctool ignoring all files in the
  repository that begin with a dot. This can be convenient like for example
  for `.gitignore`.
  The default is `no`; do not ignore dotfiles.

* `ignore_dotdirs <yes/no>`

  Setting this to 'yes' results in synctool ignoring all directories in the
  repository that begin with a dot. This can be convenient like for example
  for `.svn/` directories.
  The default is `no`; do not ignore dotdirs.

* `ignore <filename or directory name> [..]`

  This parameter enables you to have synctool ignore specific files or
  directories in the repository. Multiple `ignore` definitions are allowed.
  You may put multiple filenames on a line, and you may use wildcards.
  Example:

    ignore .gitignore .git .svn
    ignore .*.swp
    ignore tmp[0-9][0-9][0-9]??

* `ignore_file <file name>`

  **obsolete** Use the `ignore` keyword instead.

* `ignore_files <file name>`

  **obsolete** Use the `ignore` keyword instead.

* `ignore_dir <directory name>`

  **obsolete** Use the `ignore` keyword instead.

* `ignore_files <directory name>`

  **obsolete** Use the `ignore` keyword instead.

* `logfile <filename>`

  **obsolete** Use the `syslogging` keyword instead.

* `syslogging <yes/no>`

  Log any updates to syslog. Nothing is logged for dry runs.
  The default is: `yes`.

* `diff_cmd <diff UNIX command>`

  Give the command and arguments to execute `diff`.
  synctool runs this command when you use the option `--diff` to see the
  differences between the file in the repository and on the target node.

  The exact location and arguments of the `diff` program are operating
  system specific; the PATH environment variable will be searched for the
  command if you do not supply a full path.

  The default is: `diff -u`

* `ping_cmd <ping UNIX command>`

  Give the command and arguments to execute `ping`.
  `dsh-ping` uses this command to check what nodes are up and running.

  The exact location and arguments of the `ping` program are operating
  system specific; the PATH environment variable will be searched for the
  command if you do not supply a full path.

  The default is: `ping -q -c 1 -t 1`

* `ssh_cmd <ssh UNIX command>`

  Give the command and arguments to execute `ssh`. synctool and `dsh` use
  this command to execute remote commands on the target nodes.

  The exact location of the `ssh` program is operating system specific;
  the PATH environment variable will be searched for the command if you do
  not supply a full path.

  The default is: `ssh -o ConnectTimeout=10 -x -q`

* `scp_cmd <scp UNIX command>`

  **obsolete** synctool-scp uses `rsync` under the hood nowadays.

* `rsync_cmd <rsync UNIX command>`

  Give the command and arguments to execute `rsync`. synctool uses this
  command to distribute the repository to the target nodes.

  The exact location of the `rsync` program is operating system specific;
  the PATH environment variable will be searched for the command if you do
  not supply a full path.

  The default is: `rsync -ar --delete --delete-excluded -e 'ssh
  -o ConnectTimeout=10 -x -q' -q`

  synctool will automatically add another option `--filter` to this command,
  which it uses to ensure that the correct overlay directories are synced
  to the nodes. So be mindful that you can tweak the parameters of the
  `rsync` command, but you can not replace it with a different copying
  program -- unless it also supports `rsync`'s filtering capabilities.

* `synctool_cmd <synctool UNIX command>`

  Give the command and arguments to execute `synctool-client`. synctool uses
  this command to execute synctool on the target nodes.

  The exact location of the `synctool-client` program is installation
  dependent. However, synctool looks for it under the synctool root.

  The default is: `$SYNCTOOL/bin/synctool-client`

* `pkg_cmd <synctool-client-pkg UNIX command>`

  Give the command and arguments to execute `synctool-client-pkg`.
  dsh-pkg uses this command to do package management on the target nodes.

  The exact location of the `synctool-client-pkg` program is installation
  dependent. However, dsh-pkg looks for it under the synctool root.

  The default is: `$SYNCTOOL/bin/synctool-client-pkg`

* `package_manager <package management system>`

  Specify the package management system that dsh-pkg must use.
  If left out, dsh-pkg will detect what package manager it should use,
  but using this parameter you can force it if detection fails.
  This setting can be overridden from the command-line when invoking
  `dsh-pkg`.

  Valid values for `package_manager` are:

    apt-get
    yum
    zypper
    pacman
    brew
    bsdpkg

* `num_proc <number>`

  This specifies the maximum amount of parallel processes that synctool
  will use. For large clusters, you will want to increase this value, but mind
  that this will increase the load on your master node. Setting this value
  higher than the amount of nodes you have, has no effect.
  The default is `16`.

  For synctool, dsh, dsh-pkg and the like, option `--numproc` can be given
  to override this setting.

* `full_path <yes/no>`

  synctool likes to abbreviate paths to `$overlay/some/dir/file`.
  When you set this option to `no`, synctool will display the true full path
  instead of the abbreviated one.

  The default is `no`.

* `default_nodeset <group-or-node> [..]`

  By default, synctool will run on these nodes or groups. You can use this to
  make synctool by default work on only a subcluster rather than your whole
  hardware installation.

  The default is `all`. You may set it to `none` to make synctool not run
  on a default set of nodes at all. Example:

    default_nodeset test1 test2 testnodes xtest[1-10]

* `master <fqdn>`

  Indicates which node is the master, the management node from where you
  will run synctool to control the cluster. It should be set to the fully
  qualified domain name of the management host. You can get the fqdn with:

    synctool-config --fqdn

* `slave <nodename> [..]`

  Slave nodes get a full copy of the synctool repository. Slaves have no
  other function than that. You can not run synctool from a slave until you
  change it into a master node in the config file.

* `group <groupname> <subgroup> [..]`

  The `group` keyword defines _compound_ groups. It is a means to group
  several subgroups together into a single group. If the subgroups did not
  exist yet, they are defined automatically as new, empty groups.

    group wn workernode batch
    group test wn
    group g1 batch test wn

  Group names are alphanumeric, but can have an underscore, minus, or plus
  symbol in between. The following are valid group names:

    group group1 group-1 group_1 group+1 192_168_1 10 node1+node2
    group A+B+C A B C

* `node <nodename> <group> [..] [ipaddress:<IP address>]
  [hostname:<fully qualified hostname>] [hostid:<filename>]
  [rsync:<yes/no>]`

  The `node` keyword defines what groups a node is in. Multiple groups may
  be given. The order of the groups is important; the left-most group is most
  important, and the right-most group is least important. What this means is
  that if there are files in repository that have the same base filename,
  but a different group extension, synctool will pick the file that has the
  most important group extension for this node.

  Groups can be defined 'on the fly', there is no need for a group to exist
  before it can be used in a node definition.

  Node names are alphanumeric, but can have an underscore, minus, or plus
  symbol in between. The following are valid node names:

    node node1 node-1 node_1 node+1 10_0_0_2 10 node1+node2

  The `ipaddress` specifier tells synctool how to contact the node. This is
  optional; when omitted, synctool assumes the nodename can be found in DNS.
  Note that synctool nodenames need not be same as DNS names.

  The optional `hostname` specifier tells synctool that a host that has this
  fully qualified hostname, must be this node. In general it is safe to omit
  this. This specifier is normally _not used_ by synctool. It is only used
  when you run `synctool-client` manually in 'stand alone' mode on a node.
  Then there are cases in which synctool-client can fail to figure out
  its own node name. You may put the hostname in the config file to help
  synctool-client out in this situation. If this seems odd to you, then mind
  that synctool-client can not magically know what node it is running on.
  In any case, the property that uniquely identifies a host is its _hostname_.
  Note that you can also pass the option `--nodename` to synctool-client
  to tell it what its name is.

  > synctool-client uses the `socket.getfqdn()` function to determine the
  > fully qualified name of the host. If synctool-client is confused about
  > the hostname or nodename, you should really fix your DNS or `/etc/hosts`
  > file. As said, you can still pass `--nodename` to get around any problems
  > that arise.

  The optional `hostid` specifier can be used in the unusual case where
  the hostname does not uniquely identify a host, so when you have multiple
  hosts that have the same hostname. The filename argument is a file on the
  target node that contains the 'synctool hostname' that will be used to
  uniquely identify the host.

  The optional `rsync:no` specifier may be used to tell synctool not
  to sync the repository to the target node. This is only convenient when
  the node has access to the repository via another way, such as a shared
  filesystem.

    node node1 fs sched rack1 ipaddress:node1-mgmt
    node node2 login    rack1 ipaddress:node2-mgmt \
                                hostname:login.mydomain.com
    node node3 test     rack1 ipaddress:node8-mgmt
    node node4 batch    rack1 ipaddress:node9-mgmt rsync:no
    node node5 wn       rack1 ipaddress:node5-mgmt
    node node6 wn       rack1 ipaddress:node6-mgmt
    node node7 wn       rack1 ipaddress:node7-mgmt
    node node[20-29] wn rack2 ipaddress:node[20]-mgmt
    node node[30-39] wn rack3 ipaddress:192.168.3.[130]

  As shown in this example, a node range may be given to define a number
  of nodes using a single definition line. The (optional) IP address may
  use the sequence notation, that numbers the IP addresses in sequence.

* `ignore_node <nodename> [..]`

  This tells synctool to ignore one or more nodes. You can use this if you
  want to skip this node for a while for some reason, for example because
  it is broken.

* `ignore_group <group> [..]`

  This tells synctool to ignore one or more groups. You can use this to
  temporarily disable the group. This can be particularly useful when doing
  software upgrades.

* `on_update <filename> <shell command>`

  **obsolete** This mechanism is no longer available, because it doesn't
  play nice with multi-platform setups. Please use (the more flexible and
  powerful) `.post` scripts instead.

* `always_run <shell command>`

  **obsolete** This mechanism is no longer available. If you still want
  this functionality, wrap the `synctool_cmd` command with a very short
  shell script.

  Another way could be abusing the template generation mechanism in order
  to always run a certain script.

* `include <(local) synctool config file>`

  This keyword includes a synctool configuration file (that is possibly
  located on the target node). You can use this to give certain nodes a
  slightly different synctool configuration than others. This can be
  important, especially in setups where you are running a multitude of
  operating systems.

    include /etc/synctool_local.conf

  Another good use of this option is to clean up your configuration:

    include /opt/synctool/etc/nodes.conf
    include /opt/synctool/etc/colors.conf

* `terse <yes/no>`

  In terse mode, synctool shows a very brief output with paths abbreviated
  to `//overlay/dir/.../file`.
  The default is `no`.

* `colorize <yes/no>`

  In terse mode, synctool output can be made to show colors. Mind that this
  parameter only works when `terse` is set to `yes`.
  The default is `yes`.

* `colorize_full_line <yes/no>`

  In terse mode, synctool output can be made to show colors. This option
  colors the full output line rather than just the leading keyword.
  Mind that this parameter only works when both `terse` and `colorize`
  are enabled.
  The default is `no`.

* `colorize_bright <yes/no>`

  In terse mode, synctool output can be made to show colors. This option
  enables the bright/bold attribute for colors.
  Mind that this parameter only works when both `terse` and `colorize`
  are enabled.
  The default is `yes`.

* `colorize_bold <yes/no>`

  Same as `colorize_bright`.

Following are keywords to customize colors. Valid color codes are:

    white       red       blue       default
    black       green     magenta    bold
    darkgray    yellow    cyan

* `color_info <color>`

  Specify the color for informational messages in terse mode.
  The default is `default`.

* `color_warn <color>`

  Specify the color for warnings in terse mode.
  The default is `magenta`.

* `color_error <color>`

  Specify the color for error messages in terse mode.
  The default is `red`.

* `color_fail <color>`

  Specify the color for failure messages in terse mode.
  The default is `red`.

* `color_sync <color>`

  Specify the color for _sync_ messages in terse mode. These occur
  when synctool synchronizes file data.
  The default is `default`.

* `color_link <color>`

  Specify the color for _link_ messages in terse mode. These occur
  when synctool creates or repairs a symbolic link.
  The default is `cyan`.

* `color_mkdir <color>`

  Specify the color for _mkdir_ messages in terse mode. These occur
  when synctool creates a driectory.
  The default is `default`.

* `color_rm <color>`

  Specify the color for _rm_ messages in terse mode. These occur when
  synctool deletes a file.
  The default is `yellow`.

* `color_chown <color>`

  Specify the color for _chown_ messages in terse mode. These occur
  when synctool changes the ownership of a file or directory.
  The default is `cyan`.

* `color_chmod <color>`

  Specify the color for _chmod_ messages in terse mode. These occur
  when synctool changes the access mode of a file or directory.
  The default is `cyan`.

* `color_exec <color>`

  Specify the color for _exec_ messages in terse mode. These occur
  when synctool executes a `.post` script.
  The default is `green`.

* `color_upload <color>`

  Specify the color for _upload_ messages in terse mode. These occur
  when you use synctool to upload a file.
  The default is `magenta`.

* `color_new <color>`

  Specify the color for _new_ messages in terse mode. These occur when
  a sync operation requires synctool to create a new file.
  The default is `default`.

* `color_type <color>`

  Specify the color for _type_ messages in terse mode. These occur when
  the file type of the entry in the repository does not match the file type
  of the target file.
  The default is `magenta`.

* `color_dryrun <color>`

  Specify the color for the 'DRYRUN' message in terse mode.
  It occurs when synctool performs a dry run.
  The default is `default`.


* `color_fixing <color>`

  Specify the color for the 'FIXING' message in terse mode.
  It occurs when synctool is run with the `--fix` option.
  The default is `default`.

* `color_ok <color>`

  Specify the color for the 'OK' message in terse mode.
  It occurs when files are up to date.
  The default is `default`.
