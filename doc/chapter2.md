2. Installation
===============
> In synctool terminology, a _node_ is a host, a computer in a group
> of computers. A group of computers is called a _cluster_.


2.1 Installation dependencies
-----------------------------
synctool depends on a number of (fairly standard) programs:

* [python][1] version 2.x
* [ssh][2]
* [rsync][3]
* `ping`, or you can configure [fping][4] later
* [markdown][5] and [smartypants][6] -- but only if you want to install this
documentation as HTML pages

[1]: http://www.python.org/download/
[2]: http://openssh.org/portable.html
[3]: http://rsync.samba.org/
[4]: http://fping.org/
[5]: http://daringfireball.net/projects/markdown/
[6]: http://daringfireball.net/projects/smartypants/

If you got all that, it's on to the next section.


2.2 Passwordless SSH
--------------------
synctool requires passwordless SSH from the master node to each cluster node
as root. If you need more information on how to set this up, please see the
SSH documentation or just google around. I like to give you these tips:

* use an SSH keypair
* or use hostbased authentication, also for root
* set `PermitRootLogin without-password` in `sshd_config` on the nodes
* use `ssh-keyscan` to create `/etc/ssh/ssh_known_hosts`
* run `sshd` only the internal network interface to secure your system;
  configure `ListenAddress` appropriately
* in general, passwordless SSH from any cluster node to your master node
  should _not_ work or be allowed -- or at least, synctool does not need this

If you want extra security, use a passphrase on the keypair and employ
`ssh-agent`. Use `ssh-add` with a timeout.
For sites with extra tight security, it is possible to configure `ssh` to
run only specific (synctool) commands, or maybe you want to change
the `ssh_cmd` in synctool's configuration so that it runs a different command,
one that does suit your security needs.

When passwordless SSH as root works, proceed to installing the software.


2.3 Installing the software
---------------------------
To install synctool on the master node, run `setup.sh` like so:

    # ./setup.sh --installdir=/opt/synctool

The default location is `/opt/synctool`, which is a good place to put it.
Note that synctool requires an 'installdir' directory of its own. The
installdir is not the same as a prefix; whatever you do, do *not* install
synctool directly under `/usr` or `/usr/local`. Use `/usr/synctool` or
`/usr/local/synctool` instead, or better, stick with the default location.
The rest of the documentation assumes the default `/opt/synctool`.

`setup.sh` creates the following directory structure:

    /opt/synctool/bin/                  synctool commands
    /opt/synctool/sbin/                 'system' programs
    /opt/synctool/etc/                  configuration files
    /opt/synctool/lib/                  libraries, modules
    /opt/synctool/lib/synctool/
    /opt/synctool/lib/synctool/pkg/
    /opt/synctool/doc/                  documentation
    /opt/synctool/scripts/              place to store your scripts
    /opt/synctool/var/                  repository directory
    /opt/synctool/var/overlay/
    /opt/synctool/var/delete/
    /opt/synctool/var/purge/

The `doc/` directory contains a copy of this documentation.
You may build the HTML documentation from the plain text sources
by running `setup.sh` with `--build-docs`.

The following synctool commands will be made available in
`/opt/synctool/bin/`:

    synctool               Main command
    synctool-pkg           Upgrade or install packages
    synctool-ssh           Run remote commands
    synctool-scp           Copy files to nodes
    synctool-ping          Check whether nodes are up
    synctool-config        Inspect the configuration

    dsh-pkg                Short name for synctool-pkg
    dsh                    Short name for synctool-ssh
    dcp                    Short name for synctool-scp
    dsh-ping               Short name for synctool-ping

    synctool-client        Only run on target nodes
    synctool-client-pkg    Only run on target nodes
    synctool-template      Useful command for .post scripts


2.4 synctool configuration: nodes and groups
--------------------------------------------
Copy the `synctool.conf.example` file to `/opt/synctool/etc/synctool.conf`.
Edit `synctool.conf`, adjusting it as needed.

The file `synctool.conf` describes what your cluster looks like;
what nodes have what roles, and how synctool can contact them.
Think a bit about what role each machine has. There is no need to go into
great depth right now; you can always adjust the configuration later.

    node n1  group1 group2  ipaddress:machine-n01

The nodename is the 'synctool name that the node has.' It is in general the
short hostname of the host, but in fact it can be anything you like.
The nodename has nothing to do with hostnames or DNS entries.
The `ipaddress` specifier tells synctool how to contact the node; this can be
an IP address or a DNS name of the host you wish to contact. In clusters,
there is often a management network interface -- configure its IP address
here.

Directly following the node name, you can list groups. synctool uses the
term 'group', but you can also think of them as node properties. You can make
up as many different properties as you like. You can split long lines by
ending them with a backslash:

    node n101 workernode plasma mathworks solar \
          fsmounted backup debian  ipaddress:if0-n101

> Mind that in practice, synctool repositories are generally easiest
> maintainable with as few groups as possible. Make sure to use
> logical names for logical groups, and use a top-down group structure.
> Make things easy on yourself.

If you have many nodes that all share the same long list of groups, the
groups may be abbreviated by defining a _compound_ group. This compound
group must be defined before defining the nodes:

    group wn workernode plasma mathworks solar \
         fsmounted backup

    node n101  wn  debian  ipaddress:if0-n101

You have to add a node definition for each and every node in your cluster.
If your cluster is large, you may want to script the generation of a node
definition list. In the `contrib/` directory, there is a script that
uses `nmap ping` with which you can scan your management network and quickly
turn it into a synctool configuration. This makes life a bit easier.

Next, you have to tell synctool which node is the master management node.
This is done by taking the output of the UNIX `hostname` command:

    master n1.mycluster.org

Note that `hostname` is often only the short hostname, which is fine. In this
particular example, `hostname` produced a longer name.

If you want to manage the master node itself with synctool, you should also
define it as a node. It is a matter of taste, but it is maybe better _not_
to do so. If you choose not to manage the master node, it may be omitted
from the configuration. Otherwise, you may also explicitly exclude it:

    node n1 master           hostname:n1.mycluster.org
    ignore_node n1

You may also define slave nodes. Slaves are cold standby's that get full
copies of the synctool repository. A slave may be used as a failback
in case your management workstation breaks down. Since there can be only
one master node in a synctool cluster, slaves must be enabled 'by hand'
by editing the config file and changing the master definition.

> Previous versions of synctool had a `masterdir` setting.
> It no longer exists; the overlay directory now must reside under
> the synctool root, under `/opt/synctool/var/`.


2.5 Testing with dsh
--------------------
After filling in a couple of nodes in `synctool.conf`, try the command
`dsh-ping` to see if the nodes are 'up'. If they are, try running the
commands `dsh hostname`, `dsh uptime`, or `dsh date`.
If you correctly set up passwordless SSH, `dsh` should run the commands on
every node without problems or needed manual intervention. It is important
that this works before proceeding.

> Some (mostly IBM) systems already have a `dsh` command.
> Be mindful to start the correct `dsh` command. synctool's `dsh`
> is another name for `synctool-ssh`.

Tip: Add `/opt/synctool/bin` to your `PATH`.


2.6 Your first synctool run
---------------------------
Now that you have a rough setup on the master node, try running `synctool`
to a single node:

    synctool -n nodename

There should be some output message saying **DRY RUN**.
This means that synctool is now working. You can try running synctool across
all nodes:

    synctool

Check that every node responds. If it doesn't, go back to the step where
we tested the setup using `dsh`.
When synctool to every node works, the basic setup is done and you can start
filling your repository with useful files.


2.7 Client installation
-----------------------
As you may have noticed, we never installed any client software on the nodes.
There is no client installation step; the master node automatically
updates synctool on the client nodes. The binaries needed for this are
located under `/opt/synctool/sbin/`, and this directory gets synced to the
nodes with `rsync` every time you run `synctool`.
