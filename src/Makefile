#! /usr/bin/make
#
#	synctool Makefile	WJ109
#

PREFIX=/opt/synctool
SBINDIR=$(PREFIX)/sbin

INSTALL=/usr/bin/install
MKDIR=/bin/mkdir

MASTERDIR=/var/lib/synctool
MASTERBIN=$(MASTERDIR)/sbin

SCRIPTS=synctool.py synctool_config.py synctool_ssh.py synctool_scp.py synctool_master.py synctool_aggr.py
LIBS=synctool_lib.py synctool_core.py synctool_update.py synctool_unbuffered.py

all:
	@echo "synctool Makefile"
	@echo
	@echo "First edit the Makefile and adjust the PREFIX"
	@echo "Install PREFIX is currently set to:" $(PREFIX)
	@echo
	@echo "type 'make install' to install synctool on the server"
	@echo

install:
	@echo masterdir is $(MASTERDIR)
	@mkdir -m 700 -p $(MASTERDIR)
	@mkdir -m 755 -p $(MASTERDIR)/overlay $(MASTERDIR)/delete $(MASTERDIR)/scripts $(MASTERDIR)/tasks
	@echo installing synctool server commands to $(MASTERBIN)
	@mkdir -m 755 -p $(MASTERBIN)
	@install -m 755 $(SCRIPTS) $(MASTERBIN)
	@install -m 644 $(LIBS) $(MASTERBIN)
	@( cd $(MASTERBIN) && ln -sf synctool_master.py synctool )
	@( cd $(MASTERBIN) && ln -sf synctool_master.py synctool-master )
	@( cd $(MASTERBIN) && ln -sf synctool_config.py synctool-config )
	@( cd $(MASTERBIN) && ln -sf synctool_ssh.py synctool-ssh )
	@( cd $(MASTERBIN) && ln -sf synctool_ssh.py dsh )
	@( cd $(MASTERBIN) && ln -sf synctool_scp.py synctool-scp )
	@( cd $(MASTERBIN) && ln -sf synctool_scp.py dcp )
	@( cd $(MASTERBIN) && ln -sf synctool_aggr.py synctool-aggr )
	@( cd $(MASTERBIN) && ln -sf synctool_aggr.py aggr )
	@echo linking synctool server commands to $(SBINDIR)/
	@mkdir -m 755 -p $(SBINDIR)
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_master.py synctool )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_master.py synctool-master )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_config.py synctool-config )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_ssh.py synctool-ssh )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_ssh.py dsh )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_scp.py synctool-scp )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_scp.py dcp )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_aggr.py synctool-aggr )
	@( cd $(SBINDIR) && ln -sf $(MASTERBIN)/synctool_aggr.py aggr )

# EOB
