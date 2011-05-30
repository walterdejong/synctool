<h2 id="part_five">5. Best practices</h2>
<p>
This chapter contains tips, tricks and examples of how to make good use of
synctool.
</p>

<p>
<h3 id="use_logical_group_names">Use logical group names</h3>
synctool allows you to use nodenames as extension on files in the repository.
This is nice because it allows you to easily differentiate for a single node.
However, it is much better practice to put that node in a certain group, and
let it be the only member of that group. Now label the file as belonging to
that group, and your done.<br />
Bad:
<pre class="example">
overlay/etc/hosts.allow._all
overlay/etc/hosts.allow._node1
overlay/etc/motd._all
overlay/etc/motd._node1
</pre>
Good:
<pre class="example">
overlay/etc/hosts.allow._all
overlay/etc/hosts.allow._login
overlay/etc/motd._all
overlay/etc/motd._login
</pre>
The advantage is that you will be able to shift the service to another node
simply by changing the synctool configuration, rather than having to rename
all files in the repository.
</p>

<p>
<h3 id="do_not_manage_the_master">Do not manage the master node</h3>
This may seem a bit of an odd recommendation, but I recommend that you do not
manage the master node with synctool. It just makes things more complicated
when you choose to put the configuration of your master node under control
of synctool. Why is this? It is mainly because synctool by default works on
&ldquo;all&rdquo; nodes, and for some reason it is unnatural when
&ldquo;all&rdquo; includes the master node as well. Imagine calling
<span class="cmd">dsh reboot</span> to reboot all nodes, and pulling down the
master with you (in the middle of the process, so you may not even succeed at
rebooting all nodes).<br />
It also often means doing double work; the config files of the master node
tend to differ from the ones on your nodes.<br />
It is good practice though to label the master node as <em>master</em>,
and to simply ignore it:
<pre class="example">
node n01 master
ignore_group master
</pre>
If you still want to manage the master with synctool, do as you must. Just be
sure to call <span class="cmd">dsh -X master reboot</span> when you want to
reboot your cluster.
</p>

<p>
<h3 id="use_extension_on_dirs_sparingly">Use group extensions on directories
  sparingly</h3>
The ability to add a group extension to a directory is a powerful feature.
As you may know, with great power comes great responsibility. This feature will
make a big mess of your repository when used incorrectly. If you catch yourself
having to use <span class="cmd">find</span> all the time to pinpoint the
location of a file in the repository, chances are that you making things
harder on yourself than ought to be.<br />
There are situations where adding a group extension to a directory makes
perfect sense. For example, when having an <span class="path">/usr/local</span>
tree that only exists on a small group of nodes. Personally, I like to move 
such trees out of the main <span style="system">overlay</span> tree and park
them under a different <span class="system">overlaydir</span> just to get them
out of sight and clean up the repository a little.
Note that <span class="system">overlaydir</span> works on all nodes so you will
still have the group extension on the directory,
but <span class="system">overlaydir</span> is just another way of organizing
your repository.
</p>

<p>
<h3 id="write_templates">Write templates for &lsquo;dynamic&rsquo; config
  files</h3>
There are a number of rather standard configuration files that require the
IP address of a node to be listed. These are not particularly &lsquo;synctool
friendly.&rsquo; You are free to upload each and every unique instance of the
config file in question into the repository, however, if your cluster is large
this is does not make your repository look very nice, nor does it make them
any easier to handle. Instead, make a template and couple it with a
<span class="system">.post</span> script to generate the config file on the
node. As an example, I will use a fictional snippet of config file, but this
trick applies to things like an <span class="system">sshd_config</span> with
a specific <span class="system">ListenAddress</span> in it, and network
configuration files that have static IPs configured.<br />
<pre class="example">
# config_file_template._all

MyPort 22
MyIPAddress @IPADDR@
SomeOption no
PrintMotd yes
</pre>
And the accompanying <span class="system">.post</span> script:
<pre class="example">
IPADDR=&#96;ifconfig en0 | awk '/inet / { print $2 }'&#96;
sed "s/@IPADDR@/$IPADDR/" config_file_template >fiction.conf
service fiction reload
</pre>
This example uses <span class="cmd">ifconfig</span> to get the IP address of
the node. You may also consult DNS or you might be able to use
<span class="cmd">synctool-config</span> to get what you need.<br />
Now, when you want to change the configuration, edit the template file instead.
synctool will see the change in the template, and update the template on the
node. The change in the template will trigger the
<span class="system">.post</span> script to be run, thus generating
the new config file on the node.
It may sound complicated, but once you have this in place it will be very easy
to change the config file as you like by using the template.
</p>

<p>
<h3 id="multiple_clusters">Managing multiple clusters with one synctool</h3>
It is usually best to manage just one cluster with one synctool. This means
that your repository will contain files that apply only to that cluster.
In reality, you may have only one management host for managing multiple
clusters. You can deal with this in synctool in multiple ways, just pick one
you like best.
<ol>
<li style="padding-top: 0.5em;">Add all clusters to the synctool repository as
 you would with adding more nodes. For convenience, create a group for each
 cluster, so you can handle them independently whenever you wish to.
</li>

<li style="padding-top: 0.5em;">As above, create a group for each cluster.
 Restructure the <span class="system">overlay</span> dir by using multiple
 <span class="system">overlaydir</span> declarations in
 <span class="path">synctool.conf</span>. Your repository will look something
 like this:
<pre class="example">
$masterdir/overlay/common/
$masterdir/overlay/cluster1/
$masterdir/overlay/cluster2/
$masterdir/overlay/cluster3/
</pre>
 Note that synctool internally treats multiple
 <span class="system">overlay</span> directories as if they were one flat
 directory, so you will still need to put the correct group extensions on the
 files, but at least your tree will be neatly organized. Maintaining this
 structure can be hard, but it can also be just what you needed if you feel
 that the first solution was messy.
</li>

<li style="padding-top: 0.5em;">For each cluster, setup its own
 <span class="system">masterdir</span>, with its own
 <span class="path">synctool.conf</span> file and its own repository.
 Wrap the synctool command with a script that points to the relevant synctool
 tree:
<pre class="example">
/opt/synctool/sbin/synctool -c /var/lib/synctool/cluster1/synctool.conf
</pre>
 A big advantage of this approach is that it is clear where each file
 should go. Another big advantage is that each cluster can have its own set of
 groups. In the previous solutions, all groups are shared among the clusters.
 A disadvantage is that files that should be the same over all clusters are
 spread over multiple repositories.
</li>

</ol>
</p>

<p>
<h3 id="tiered_setup">Use a tiered setup for large clusters</h3>

</p>
