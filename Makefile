#! /usr/bin/make
#
#	synctool Makefile	WJ109
#

PREFIX=/opt/synctool-4.0
SBINDIR=$(PREFIX)/sbin

INSTALL=/usr/bin/install
MKDIR=/bin/mkdir

MASTERDIR=/var/lib/synctool

SCRIPTS=synctool.py synctool_config.py synctool_ssh.py synctool_master.py synctool_aggr.py
LIBS=synctool_lib.py

CLIENT_SCRIPTS=synctool.py synctool_config.py


all:
	@echo "synctool Makefile"
	@echo
	@echo "First edit the Makefile and adjust the PREFIX"
	@echo "Install PREFIX is currently set to:" $(PREFIX)
	@echo
	@echo "type 'make install' to install synctool on the server"
	@echo "type 'make client_install' to install synctool on a client"
	@echo

install:
	@echo installing synctool server commands to $(SBINDIR)
	@mkdir -m 755 -p $(SBINDIR)
	@install -m 755 $(SCRIPTS) $(SBINDIR)
	@install -m 644 $(LIBS) $(SBINDIR)
	@( cd $(SBINDIR) && ln -sf synctool_master.py synctool )
	@( cd $(SBINDIR) && ln -sf synctool_master.py synctool-master )
	@( cd $(SBINDIR) && ln -sf synctool_config.py synctool-config )
	@( cd $(SBINDIR) && ln -sf synctool_ssh.py synctool-ssh )
	@( cd $(SBINDIR) && ln -sf synctool_ssh.py dsh )
	@( cd $(SBINDIR) && ln -sf synctool_aggr.py synctool-aggr )
	@( cd $(SBINDIR) && ln -sf synctool_aggr.py aggr )
	@echo masterdir is $(MASTERDIR)
	@mkdir -m 700 -p $(MASTERDIR)
	@mkdir -m 755 -p $(MASTERDIR)/overlay $(MASTERDIR)/delete $(MASTERDIR)/scripts $(MASTERDIR)/tasks

client_install:
	@echo installing synctool client commands to $(SBINDIR)
	@mkdir -m 755 -p $(SBINDIR)
	@install -m 755 $(CLIENT_SCRIPTS) $(SBINDIR)
	@install -m 644 $(LIBS) $(SBINDIR)
	@( cd $(SBINDIR) && ln -sf synctool.py synctool )
	@( cd $(SBINDIR) && ln -sf synctool_config.py synctool-config )
	@echo masterdir is $(MASTERDIR)
	@mkdir -m 700 -p $(MASTERDIR)
	@mkdir -m 755 -p $(MASTERDIR)/overlay $(MASTERDIR)/delete $(MASTERDIR)/scripts $(MASTERDIR)/tasks

# EOB
