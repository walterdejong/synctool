2. Installation
===============
> In synctool terminology, a _node_ is a host, a computer in a group
> of computers. A group of computers is called a _cluster_.

Passwordless SSH
----------------
First of all, synctool requires passwordless SSH from the master node to
each cluster node as root. Exactly how to do this is beyond the scope
of this document (see the SSH documentation or just google around), but
I'd like to say this about it:

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

Installing the software
-----------------------
To install synctool on the master node, run `setup.sh` like so:

        # ./setup.sh --installroot=/opt/synctool

The default location is `/opt/synctool`, a good place to put it.
Note that synctool requires an 'installroot' directory of its own. The
installroot is not the same as a prefix; whatever you do, do *not* install
synctool directly under `/usr` or `/usr/local`. Use `/usr/synctool` or
`/usr/local/synctool` instead.
The rest of the documentation assumes the default `/opt/synctool`.

`setup.sh` creates the following directory structure:

        /opt/synctool/bin/
        /opt/synctool/sbin/
        /opt/synctool/etc/
        /opt/synctool/lib/
        /opt/synctool/lib/synctool/
        /opt/synctool/lib/synctool/pkg/
        /opt/synctool/scripts/
        /opt/synctool/var/
        /opt/synctool/var/overlay/
        /opt/synctool/var/delete/

The following synctool commands will be made available in
`/opt/synctool/bin/`:

        synctool                Main command
        synctool-pkg            Upgrade or install packages
        synctool-ssh            Run remote commands
        synctool-scp            Copy files to nodes
        synctool-ping           Check whether nodes are up
        synctool-config         Inspect the configuration

        dsh-pkg                 Short name for synctool-pkg
        dsh                     Short name for synctool-ssh
        dcp                     Short name for synctool-scp
        dsh-ping                Short name for synctool-ping

        synctool-client         Only run on target nodes
        synctool-client-pkg     Only run on target nodes
        synctool-template       Useful command for .post scripts


synctool configuration: nodes and groups
----------------------------------------
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

Some people like managing the master node itself with synctool.
While it _is_ possible to do this, it's often better to exclude the master
node:

        node n1 master     hostname:n1.mycluster.org
        ignore_node n1

You may also leave the master node out of the configuration altogether.


Testing with dsh
----------------
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


Your first synctool run
-----------------------
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


Client installation
-------------------
As you may have noticed, we never installed any client software on the nodes.
There is no client installation step; the master node automatically
updates synctool on the client nodes. The binaries needed for this are
located under `/opt/synctool/sbin/`, and this directory gets synced to the
nodes with `rsync` every time you run `synctool`.
