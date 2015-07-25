6. Migrating to synctool 6
==========================
This chapter may be of importance if you already are using an older version
of synctool, and wish to upgrade to synctool 6. Everything you need to know
is really in the previous chapters, so some sound advice: read the manual!
Other than that, this chapter gives some pointers on how to lift your
installation up to level 6.

First of all, this is a big upgrade so be sure you have some time on your
hands. It is recommended that your current synctool setup is 'clean', does
not produce any errors, and that your cluster is 'in sync' (ie. there are
no pending changes). It is also recommended that you first read through this
chapter (and/or the entire manual) before taking any action.

This chapter assumes your old synctool repository is `/var/lib/synctool/`.
The programs are under `/opt/synctool/`.


6.1 Installing synctool 6
=========================
Log on to the master node. The first step is to move the old synctool dir
out of the way:

    mv /opt/synctool /opt/synctool.old

Install synctool 6 as described in [chapter 2](chapter2.html).
This boils down to:

    ./setup.sh -f

This installs the programs under `/opt/synctool/` and creates a new, empty
repository under `/opt/synctool/var/`. Let's leave it empty for now, first
go configure synctool 6.


6.2 Configuring synctool 6
==========================
The old config file is `/var/lib/synctool/synctool.conf`. The new config
file will be `/opt/synctool/etc/synctool.conf`, but you can't just copy it
in place and expect it to work. The reason is that some config parameters
have changed; some were dropped and new ones have been added.
The best thing to do is to take `/opt/synctool/etc/synctool.conf.example`
and adapt it.

    cd /opt/synctool/etc
    cp synctool.conf.example synctool.conf
    editor_of_choice synctool.conf

Fill in all the parameters the way you want them. synctool uses sensible
defaults for most parameters; these are commented in the example config.
You must set the `master_node`.

Delete the obvious example groups and nodes; copy over the group and node
definitions from your old `synctool.conf` in the `/var/lib/synctool/`
directory.
As shown in the example config, if your nodes are neatly numbered, the node
config lines can be greatly shortened by using the new node range syntax.

Comment the `ignore_node` and `ignore_group` lines or set them like they
were in the old `synctool.conf`.

The rest of the config file are reasonable defaults. Leave them be or change
them to match the old `synctool.conf`.

If you had any `on_update` lines in the old config, these must be converted
to `.post` scripts; `.post` scripts are the only way to trigger actions on
updates in synctool 6.

You are now set to try out the new config with `synctool-config` and/or `dsh`.

For more information on configuring synctool, see [chapter 2](chapter2.html)
and [chapter 4](chapter4.html).


6.3 Updating the repository
===========================
If the configuration is working, it is safe to run `synctool`. This will
install synctool 6 on the entire cluster. But wait ... the repository is
still empty ...? Indeed, and thus synctool won't make any changes to the
nodes -- other than automatically upgrading synctool itself.

The repository works a little different in synctool 6. In synctool 5 you
had the option of configuring multiple overlay dirs. This was nothing more
than logical grouping of files, synctool would sync all overlay dirs onto
each node. In synctool 6, the overlay dir is divided by group, and nodes
only get copy of a relevant subtree.
Learn more about it in [chapter 3](chapter3.html).

In general, you should be able to do this:

* If you had only a single overlay dir, copy the old overlay directory
  `/var/lib/synctool/overlay/` to `/opt/synctool/var/overlay/all/`
  (or `common/` -- see best practices in [chapter 5](chapter5.html)).

* If you had multiple overlay dirs, copy them over to
  `/opt/synctool/var/overlay/` and realize that synctool will now use them
  in a different way. Go through the list of files in the grouped overlay
  dirs and examine files tagged with extension `._all`. They should probably
  be moved elsewhere. In fact, you should pay attention to files tagged with
  an extension other than the name of the `overlay/group/` directory.

This is the quick and dirty way. It is more safe however to carefully go
through the old repository and copy them to the correct place in the new
repository.

Run synctool on a single node, see what it does. Fix any errors and iterate.
When all is well, run synctool over groups of nodes and eventually the entire
cluster.

Go over the same process for the `delete/` tree.

The `tasks/` tree no longer exists. If you have any scripts under `tasks/`,
you may move them to `/opt/synctool/scripts/` (without group extension).
They can now be run using `dsh`. See [chapter 3](chapter3.html) for more
information.

synctool should now largely already work.


6.4 Updating templates
======================
In older versions of synctool you could generate config files by pulling
a trick with a template file and a `.post` script. This trick is now
built into synctool, and it uses a `._template` file and an accompanying
`._template.post` script. A big advantage of this new templating system is
that you can do a proper dry run, and use `synctool --diff` to examine any
changes made to the config file that is installed and active on the node;
this was previously not possible with templated files.

To adapt to the new template system, seek out any template files you have,
and rename them to have extension `._template`. Rename the matching `.post`
script to `._template.post`. Next, edit the `._template.post` script, and
change it to call `synctool-template`:

    /opt/synctool/bin/synctool-template "$1" >"$2"

You should probably also set a variable to make it work.
See [chapter 3](chapter3.html) for more information on how to operate
templates.

You can use `dsh rm` or the `delete/` tree to clean up any old `.template`
files that are still floating around in your system.


6.5 Wrapping up
===============
The migration to synctool 6 is now finished. After a week or so, you should
feel confident enough to delete the old repository `/var/lib/synctool/`.
synctool 6 does not use it. The quickest way to dispose of it is:

    # delete old repos from cluster nodes
    dsh -g all rm -rf /var/lib/synctool
    # delete old repos from master node
    rm -rf /var/lib/synctool

There is more to synctool 6 than this; you might want to make use of the
new 'purge' feature, or use the new options for uploading files, or use
`dsh-pkg` to upgrade software packages, or configure slave nodes, or go
multi-cluster with synctool, or configure syslogging, or try out multiplexed
connections, or ...
Read all about it in this manual.
