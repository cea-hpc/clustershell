%define name clustershell
%define release 1%{dist}

Summary: ClusterShell Python framework
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: GPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-buildroot
Prefix: %{_prefix}
BuildArchitectures: noarch
Vendor: Stephane Thiell <stephane.thiell@cea.fr>
Url: http://clustershell.sourceforge.net/

%description
ClusterShell is an event-based python library to execute commands on local
or distant cluster nodes in parallel depending on the selected engine and
worker mechanisms.

%prep
%setup

%build
python setup.py build

%install
python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mkdir -p $RPM_BUILD_ROOT/%{_sysconfdir}/clustershell

# man pages
mkdir -p $RPM_BUILD_ROOT/%{_mandir}/{man1,man5}
gzip -c doc/man/man1/clush.1 >$RPM_BUILD_ROOT/%{_mandir}/man1/clush.1.gz
gzip -c doc/man/man1/nodeset.1 >$RPM_BUILD_ROOT/%{_mandir}/man1/nodeset.1.gz
gzip -c doc/man/man5/clush.conf.5 >$RPM_BUILD_ROOT/%{_mandir}/man5/clush.conf.5.gz

# vim addons
cp conf/clush.conf $RPM_BUILD_ROOT/%{_sysconfdir}/clustershell
mkdir -p $RPM_BUILD_ROOT/usr/share/vim/vim%{vim_version}/ftdetect
cp doc/extras/vim/ftdetect/clush.vim $RPM_BUILD_ROOT/usr/share/vim/vim%{vim_version}/ftdetect
mkdir -p $RPM_BUILD_ROOT/usr/share/vim/vim%{vim_version}/syntax
cp doc/extras/vim/syntax/clush.vim $RPM_BUILD_ROOT/usr/share/vim/vim%{vim_version}/syntax

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
/usr/share/vim/vim%{vim_version}/syntax/clush.vim
/usr/share/vim/vim%{vim_version}/ftdetect/clush.vim
%doc LICENSE README
%doc %{_mandir}/man1/clush.1.gz
%doc %{_mandir}/man1/nodeset.1.gz
%doc %{_mandir}/man5/clush.conf.5.gz

%config %{_sysconfdir}/clustershell/clush.conf
