# norootforbuild
%define debug_package %{nil}
%define __spec_install_port /usr/lib/rpm/brp-compress
%define __os_install_post /usr/lib/rpm/brp-compress
%define __find_requires %{nil}
Autoreq: 0

Name:           synctool
License:        GPL v3 or later
Group:		system/utility
Summary:        synchronized config files
Version:        6.3
Release:        8%{dist}
BuildArch:	noarch
URL:            https://github.com/celane/synctool
Source0:        %{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root
Requires:	/usr/bin/ssh
Requires:	python
BuildRequires:  discount
BuildRequires:  python3-smartypants
BuildRequires:  help2man



%description
Synchronize config files for multiple systems



%prep
%setup

%build
chmod a+x src/*.py
ln -s src/synctool_master.py ./synctool
help2man -n"Cluster configuration management tool" -s8 --manual="System Administration Utilities" -o synctool.8 -N -l ./synctool

ln -s src/dsh.py ./dsh
help2man -n"Cluster configuration copy tool" -s8 --manual="System Administration Utilities" -o dsh.8 -N -l ./dsh

%install

install -d %buildroot/usr/share/doc/%{name}-%{version}-%{release}/contrib
install Changelog README LICENSE synctool.conf.example  %{buildroot}/usr/share/doc/%{name}-%{version}-%{release}/
install -d %buildroot/usr/share/man/man8
install *.8 %buildroot/usr/share/man/man8/
./setup.sh  --installdir=%buildroot/opt/synctool --build-docs --fix
mv %buildroot/opt/synctool/doc %buildroot/usr/share/doc/%{name}-%{version}-%{release}/html
install -d %buildroot/etc/profile.d
install contrib/synctool.profile.sh %buildroot/etc/profile.d/synctool.sh
install -d %buildroot/etc/bash_completion.d
install contrib/synctool.bash_completion %buildroot/etc/bash_completion./synctool
mv contrib %{buildroot}/usr/share/doc/%{name}-%{version}-%{release}/

%clean


%files 
%defattr(-,root,root)
/usr/share/man/man8/
%docdir /usr/share/doc/%{name}-%{version}-%{release}/
/usr/share/doc/%{name}-%{version}-%{release}/
/opt/synctool/
%config /etc/profile.d/synctool.sh
%config /etc/bash_completion.d/synctool



%changelog
* Tue Sep 12 2023 lane@dchooz.org
- build from git repository

* Wed May 26 2021 lane@duphy4.physics.drexel.edu
- improve manpage generation

* Thu Jul 19 2018 lane@duphy4.physics.drexel.edu
- change to work with python2 in rpm build

* Fri Jul 1 2016 lane@duphy4.physics.drexel.edu
- update to 6.2

* Sat Jun 30 2012 lane@duphy4.physics.drexel.edu
- update to 5.2
- remove synctool-client, since no longer needed
- automatic manpage generation from --help

* Wed Dec 22 2010 lane@duphy4.physics.drexel.edu
- copy from prev version
