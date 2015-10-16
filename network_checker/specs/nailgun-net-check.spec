%define name nailgun-net-check
%{!?version: %define version 8.0.0}
%{!?release: %define release 1}

Name: %{name}
Summary:   Network checking package for CentOS6.x
Version:   %{version}
Release:   %{release}
License:   GPLv2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
URL:       http://github.com/Mirantis
Requires:  vconfig
Requires:  scapy
Requires:  python-argparse
Requires:  python-pypcap
Requires:  python-cliff-tablib
Requires:  python-stevedore
Requires:  python-daemonize
Requires:  python-yaml
Requires:  tcpdump
Requires:  python-requests
Requires:  python-netifaces

%prep
%setup -cq -n %{name}-%{version}

%build
cd %{_builddir}/%{name}-%{version}/network_checker && python setup.py build

%install
cd %{_builddir}/%{name}-%{version}/network_checker && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/network_checker/INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%description
This is a network tool that helps to verify networks connectivity
between hosts in network.

%files -f %{_builddir}/%{name}-%{version}/network_checker/INSTALLED_FILES
%defattr(-,root,root)
