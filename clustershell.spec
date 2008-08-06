%define name clustershell
%define version 0.9
%define release 2

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
Requires: pdsh
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

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)


