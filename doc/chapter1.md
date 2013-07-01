1. What is synctool
===================
synctool is a tool that can help you administer your cluster of computers.
Its primary function is keeping configuration files 'in sync',
i.e.: as they ought to be. Its core business is copying configuration files
to groups (or classes) of computers within a cluster and comparing such
files with a normative copy that you keep in a repository.
The repository, by the way, is not some database system, but an 'overlay'
directory tree in a file system, that looks very much like the directories
of the managed target systems. The only things missing from the repository
are the files and directories that you do not *want* or need synctool to
manage. In the repository, you can manage directories with conventional
UNIX tools -- `cp`, `mv`, `mkdir` -- or any tool you like, and you can edit
files with the editor of preference.

There are other tools in existence that do the same thing as synctool,
and ironically, none of them are as easy to understand and use as synctool.
Perhaps this is so, because other tools try to do the same thing, among
many other things as well. synctool does *not* try to be an all
encompassing system administation tool, and does not have its own little
scripting language to define your system in. It does not strive to automate
all aspects of the system administrator's work. Rather, it focuses on its
core business only and concentrates on doing that very well.
This is very much in line with the traditional UNIX design philosophy --
and with common sense. The powerful set of now common shell tools grew by
adding commands that were designed to do only specific tasks very well and
to be used easily in combination with other tools that specialize in other
tasks.

Because of that design philosophy:

* synctool integrates very easily into existing system adminstration
  practices as an add-on tool, specifically to do configuration file
  management. It does not interfere with other things and does not need
  much either: It is written in the Python language, and it uses the power
  of `rsync` and `ssh` to distribute files.

* It is possible to use synctool in the style that suits you best: Warn you
  whenever things are out of 'sync' or do automated repairs of deviations.
  It is even possible to manage some files with synctool and leave other
  files to other mechanisms -- what is not represented in the synctool
  repository is not managed by it.

* Although synctool has many command-line options, its set of core functions
  is very small and easy to understand. There is not that much you need to
  know to use it, so there is virtually no learning curve to get you started
  with synctool.

In addition, synctool simplifies things by working with the following
concepts:

* Some clusters are more homogeneous than others. To handle differentiation
  within a cluster, a host can be part of one or more logical groups;
* Files are designated to a group by means of filename extension;
* The 'overlay' directory tree contains the files that are 'synced' to the
  target hosts;
* When certain files are updated, you will want to execute a script
  (e.g, to run `'service daemon restart'`).
  synctool has a mechanism for this. You can make synctool more powerful
  by writing plugin scripts that run the commands you want whenever
  a particular file has been updated.

synctool manages configuration files, not processes, and not full system
installations. However, synctool comes with handy tools to run commands
across the cluster and do synchronized updates of software packages.

synctool does not hide UNIX from you.
Making clever use of synctool makes it a very powerful tool.

synctool started in 2003 and has since been in use with great success, doing
real work at big computing sites. Hopefully, it will be of some value to you
as well.
