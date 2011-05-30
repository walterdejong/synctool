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
