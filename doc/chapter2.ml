<h2 id="part_two">2. Installation</h2>
<div class="note">
In synctool terminology, a <em>node</em> is a host, a computer in a group
of computers. A group of computers is called a <em>cluster</em>.
</div>

<p>
<h3 id="passwordless_ssh">Passwordless SSH</h3>
First of all, synctool requires passwordless SSH from the master node to
each cluster node as root. Exactly how to do this is beyond the scope
of this document (see the SSH documentation or just google around), but
I'd like to say this about it:
<ul>
<li>use SSH keypairs</li>
<li>or use hostbased authentication, also for root</li>
<li>set <span class="path">sshd_config</span>
    <span class="system">PermitRootLogin without-password</span></li>
<li>run <span class="cmd">sshd</span> only the internal network interface to
    secure your system</li>
<li>in general, passwordless SSH from any cluster node to your master node
    should <em>not</em> work or be allowed; or at least, synctool does not
    need this</li>
</ul>
For sites with extra tight security, it is possible to configure ssh to run
only specific (synctool) commands, or maybe you want to change the
ssh_cmd in the configuration so that it runs a different command, that
suits your security needs.
</p>
<p>
When passwordless SSH as root works, proceed to installing the software.
</p>

<p>
<h3 id="make_install">make install</h3>
Edit the provided <span class="cmd">Makefile</span> and adjust
<span class="cmd">PREFIX</span> to point to your desired location where the
software should reside. Some prefer <span class="path">/usr/local</span>,
others prefer <span class="path">/usr/local/synctool</span>, while others
prefer <span class="path">/opt</span>. Pick whatever you think is best.
</p>

<p>
On your master node, run <span class="cmd">make install</span>. This copies
the commands to the selected location and sets up symlinks for:
<div class="example">
synctool &nbsp; &nbsp; &nbsp;&nbsp; -&gt; synctool_master.py<br />
synctool-config -&gt; synctool_config.py<br />
synctool-ping &nbsp; -&gt; synctool_ping.py<br />
dsh-ping &nbsp; &nbsp; &nbsp;&nbsp; -&gt; synctool_ping.py<br />
synctool-ssh &nbsp;&nbsp; -&gt; synctool_ssh.py<br />
dsh &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; -&gt; synctool_ssh.py<br />
synctool-scp &nbsp;&nbsp; -&gt; synctool_scp.py<br />
dcp &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; -&gt; synctool_scp.py<br />
synctool-aggr &nbsp; -&gt; synctool_aggr.py<br />
</div>
It also creates the master repository under
<span class="path">/var/lib/synctool/</span>.
</p>

<p>
<h3 id="config_nodes_groups">synctool configuration: nodes and groups</h3>
Copy the <span class="path">synctool.conf.example</span> to
<span class="path">/var/lib/synctool/synctool.conf</span>
and edit it, adjusting it as needed.
</p>

<p>
<span class="path">synctool.conf</span> describes what your cluster looks like;
what nodes have what roles, and how synctool can contact them.
Think a bit about what role each machine has. There is no need to go into
great depth right now; you can always adjust the configuration later.
<div class="example">
node n1 ipaddress:machine-n01 hostname:machine-n01.domain.org
</div>
The nodename is the &lsquo;synctool name that the node has.&rsquo; It is in
general the short hostname of the host, but in fact it can be anything you
like. The nodename has nothing to do with hostnames or DNS entries.
The optional <span class="system">ipaddress</span> specifier tells synctool how
to contact the node; this can be an IP address or a DNS name of the host you
wish to contact. In clusters, there is often a management network interface
&mdash; configure its IP address here.
</p>
<div class="note">
In older versions of synctool, <span class="system">ipaddress</span> was
called <span class="system">interface</span>.
The <span class="system">interface</span> keyword still works, but is
discouraged because it really is an IP address and not a network interface.
</div>
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
<div class="note">
synctool uses the <span class="system">socket.getfqdn()</span> function to
determine the fully qualified name of the host. If synctool is not finding the
node for the specified hostname, add a line to
<span class="path">/etc/hosts</span>:
 <div class="system">
 <br />
127.0.1.1 &nbsp; myhost.mydomain.com &nbsp; myhost
 </div>
</div>
<p>
It is good practice to label your master node as &lsquo;master&rsquo; or
&lsquo;install&rsquo;.
<div class="example">
node n1 master ipaddress:machine-n01
</div>
Now <span class="system">n1</span> responds to the groups
<span class="system">n1</span> and <span class="system">master</span>.
</p>

<p>
Some people don't like managing the master node itself with synctool.
While it <em>is</em> possible and perfectly alright to do this, some like to
exclude the master node by default:
<div class="example">
ignore_node n1
</div>
You have to list each and every host.
In the <span class="path">contrib/</span> directory, there is a script that
uses <span class="cmd">nmap ping</span> with which you can scan your management
network and quickly turn it into a synctool configuration. This makes life
a bit easier.
</p>

<p>
Nodes can be in as many different groups as you like. You can split
long lines of node definitions by ending them with a backslash:
<div class="example">
node n101 workernode debian plasma mathworks solar \ <br />
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; fsmounted backup ipaddress:if0-n101
</div>
<div class="note">
Mind that in practice, synctool repositories are generally easiest
maintainable with as few groups as possible. Make sure to use
logical names for logical groups, and use a top-down group structure.
Make things easy on yourself.
</div>
</p>

<p>
If you have many nodes that all share the same long list of groups,
the groups may be abbreviated by defining a <em>compound</em> group. This
compound group must be defined before defining the nodes:
<div class="example">
group wn workernode debian plasma mathworks solar \ <br />
&nbsp; &nbsp; &nbsp; &nbsp; &nbsp;fsmounted backup<br />
<br />
node 101 wn ipaddress:if0-n101
</div>
<h3 id="testing_with_dsh">Testing with dsh</h3>
After filling in a couple of nodes in <span class="path">synctool.conf</span>,
try the command <span class="cmd">dsh-ping</span> to see if the nodes are
&lsquo;up&rsquo;. If they are, try <span class="cmd">dsh hostname</span>,
<span class="cmd">dsh uptime</span>, or <span class="cmd">dsh date</span>.
If you correctly set up passwordless SSH, <span class="cmd">dsh</span> should
run the commands on every node without problems or needed manual intervention.
It is important that this works, before proceeding.
<div class="note">
Some (mostly IBM) systems already have a <span class="cmd">dsh</span> command.
In synctool, <span class="cmd">dsh</span> is a symbolic link to
<span class="cmd">synctool-ssh</span>. The same goes for
<span class="cmd">dcp</span>, which is a symlink to
<span class="cmd">synctool-scp</span>.
</div>
</p>

<p>
<h3 id="your_first_synctool_run">Your first synctool run</h3>
Now that you have a rough setup on the master node, try running
synctool to a single node:
<div class="example">
synctool -n anodename
</div>
If you get <span class="system">command not found</span>, add
<span class="path">/opt/synctool/sbin</span> to your
<span class="system">PATH</span> environment variable.
By default, the full path to the command is:
<div class="example">
/opt/synctool/sbin/synctool -n anodename
</div>
There should be some output message saying <span class="system">DRY RUN</span>.
This means that synctool is now working. You can try running synctool across
all nodes:
<div class="example">
synctool
</div>
Check that every node responds. If it doesn't, go back to the step where
we tested the setup using <span class="cmd">dsh</span>.
When synctool to every node works, the basic setup is done and
you can start filling your repository with useful files.
</p>

<p>
<h3 id="client_install">Client installation</h3>
As you may have noticed, we never installed any client software on the nodes.
There is no client installation step; the master node automatically
updates synctool on the client nodes. The binaries needed for this are
located under <span class="path">/var/lib/synctool/sbin/</span>, and this
directory gets synced to the nodes with <span class="cmd">rsync</span>.
</p>
