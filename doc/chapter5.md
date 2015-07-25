5. Best practices
=================
This chapter contains tips, tricks and examples of how to make good use of
synctool.


5.1 Use logical group names
---------------------------
synctool allows you to use nodenames as extension on files in the repository.
This is nice because it allows you to easily differentiate for a single node.
However, it is much better practice to put that node in a certain group, and
let it be the only member of that group. Now label the file as belonging to
that group, and you're done.

Bad:

    overlay/all/etc/hosts.allow._all
    overlay/all/etc/hosts.allow._node1
    overlay/all/etc/motd._all
    overlay/all/etc/motd._node1

Good:

    overlay/mycluster/etc/hosts.allow._all
    overlay/mycluster/etc/hosts.allow._login
    overlay/mycluster/etc/motd._all
    overlay/mycluster/etc/motd._login

The advantage is that you will be able to shift the service to another node
simply by changing the synctool configuration, rather than having to rename
all files in the repository.


5.2 Future planning: Be mindful of group 'all'
----------------------------------------------
synctool has this great group 'all' that applies to all nodes. One day,
however, you decide to add a new machine to your cluster that has a pretty
different role than any other. (Not) suprisingly, synctool will want to apply
all files tagged as `all` to the new node -- but in this case, it's exactly
_not_ what you want.

The problem is that `all` is too generic, and the solution is to rename
`overlay/all/` to something else, such as `overlay/common/`, or better yet,
`overlay/subcluster1/`. This moves `all` out of the way and you can integrate
your new node in a better way.

The lesson here is that `overlay/all/` is a nice catch-all directory, but
it's maybe best left unused. It's perfectly OK for files to be tagged as
`._all`, but they really should be placed in a group-specific overlay
directory.


5.3 Use group extensions on directories sparingly
-------------------------------------------------
synctool allows you to add a group extension to a directory, like so:

    $overlay/all/etc._mygroup/

This is a powerful feature. However, it can make a mess of your repository
as well. If you catch yourself having to use `find` all the time to pinpoint
the location of a file in the repository, chances are that you making things
harder on yourself than ought to be.

Maybe it is better structured as:

    $overlay/mygroup/etc/

but maybe it is better structured as:

    $overlay/all/etc/somefile._all
    $overlay/all/etc/somefile._mygroup

The main message is "keep it simple". Try not to use too many group
directories, because it makes things complicated.


5.4 Do not manage the master node
---------------------------------
It is recommended that you do not manage the master node with synctool.
The reason is that it makes things more complicated when you choose to put
the configuration of your master node under control of synctool.

Why is this? It is mainly because synctool by default works on 'all' nodes,
and for some reason it is unnatural when 'all' includes the master node too.
Imagine calling `dsh reboot` to reboot all nodes, and pulling down the master
with you (in the middle of the process, so you may not even succeed at
rebooting all nodes).

It often means doing double work; the config files of the master node tend
to differ from the ones on your nodes. It is good practice though to label
the master node as _master_, and to simply ignore it:

    node n01 master
    ignore_group master

It's also OK to leave the master node out of the configuration altogether.
(Here, 'master' is a group, not to be confused with the `master` keyword that
defines the master node. Are you still with me?)

If you still want to manage the master with synctool, do as you must. Just be
sure to call `dsh -X master reboot` when you want to reboot your cluster.


5.5 Managing multiple clusters with one synctool
------------------------------------------------
It is really easy to manage just one cluster with one synctool. This means
that your repository will contain files that apply only to that cluster.
In reality, you may have only one management host for managing multiple
clusters, or you may have several subclusters in a single cluster.

Managing such a setup with synctool used to be hard & hackish, but since
version 6 it is only a matter of using groups in the right way.

Add all clusters to the synctool repository as you would with adding more
nodes. Create a group for each (sub)cluster. For each clustergroup, add a
directory `overlay/cluster/`, so you can handle them independently whenever
you wish to. Your repository will look like this:

    $overlay/all/
    $overlay/cluster1/
    $overlay/cluster2/
    $overlay/cluster3/

If you tend to reinstall systems a lot with different operating systems,
it may be a good idea to create per OS groups. This also helps when upgrading
to new OS releases.

    $overlay/wheezy/
    $overlay/centos64/
    $overlay/sles11sp2/

Note that files under these directories can still be marked `._all`, synctool
will select the correct file as long as you tag the node with the right group.

Decide for yourself what files should go under what directory, and what
layout works best for you.


5.6 Use a tiered setup for large clusters
-----------------------------------------
If you have a large cluster consisting of hundreds or thousands (or maybe
more) nodes, you will run into a scaling issue at the master node.
synctool doesn't care how many nodes you manage with it, but doing a
synctool run to a large number of nodes will take considerable time. You can
increase the `num_proc` parameter to have synctool do more work in parallel,
but this will put more load on your master node. To manage such a large
cluster with synctool, a different approach is needed.

The solution is to make a tiered setup. In such a setup, the master node syncs
to other master nodes (for example, the first node in a rack), which in turn
sync to subsets of nodes. Script it along these lines:

    #! /bin/bash

    for rack in $RACKS
    do
        # give rackmasters a full copy of the repos
        rsync -a --delete /opt/synctool/ ${rack}-n1:/opt/synctool/

        # run synctool on rackmaster
        dsh -n ${rack}-n1 --no-nodename \
          /opt/synctool/bin/synctool -g $rack "$@"
    done &
    wait

So, the master node syncs to 'rack masters', and the rack masters in turn
run synctool on their subset of nodes. In the config, the nodes are
grouped by rack. The option `--no-nodename` is used with `dsh` to make the
output come out right.
You also still need to manage the rack masters -- with synctool, from the
master node.

A slightly different solution is to make use of slave nodes; the master
syncs full copies only to slaves; next, the slaves manage the nodes.
This requires having multiple config files (eg, one per rack) and scripting
it so that it uses the correct config file for each rack.

    synctool -c slaves.conf "$@"
    for rack in $RACKS
    do
        dsh -n ${rack}-n1  --no-nodename \
          synctool -c confs/${rack}.conf "$@"
    done

This tip is mentioned here mostly for completeness; I recommend running with
a setup like this only if you are truly experiencing problems due to the
scale of your cluster. There are security implications to consider when
giving nodes a full copy of the repository. It depends on your situation
whether it is acceptable to run like this.


5.7 Manage hosts behind a gateway
---------------------------------
As synctool relies on ssh authentication you can easily manage hosts that are
not directly available. Imagine this setup:

    synctool-master-node
        |
    Internet
        |
    gateway.your.domain
        |
        + privatenode1
        + privatenode2

You need to set up your ssh connection as follows in /root/.ssh/config

    Host *.intra.your.domain
        ProxyCommand ssh gateway.your.domain -W %h:22

Add your hosts in synctool.conf:

    node privatenode1 group1 group2 ipaddress:privatenode1.intra.your.domain
    node privatenode2 group1 group2 ipaddress:privatenode2.intra.your.domain

Of course this requires also a proper DNS setup for your intra zone
at `gateway.your.domain`
