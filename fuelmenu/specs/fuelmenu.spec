%define name fuelmenu
%{!?version: %define version 8.0.0}
%{!?release: %define release 1}

Name: %{name}
Summary: Console utility for pre-configuration of Fuel server
Version: %{version}
Release: %{release}
License: Apache
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Matthew Mosesohn <mmosesohn@mirantis.com>
BuildRequires:  python-setuptools
Requires: bind-utils
Requires: nailgun-net-check
Requires: ntp
Requires: python-setuptools
Requires: python-netaddr
Requires: python-netifaces
Requires: python-urwid >= 1.1.0
Requires: PyYAML
Requires: python-ordereddict
Requires: screen
Requires: python-six

%description
Summary: Console utility for pre-configuration of Fuel server

%prep
%setup -cq -n %{name}-%{version}

%build
cd %{_builddir}/%{name}-%{version}/fuelmenu && python setup.py build

%install
cd %{_builddir}/%{name}-%{version}/fuelmenu && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/fuelmenu/INSTALLED_FILES
install -d -m 755 %{buildroot}/etc/fuel
install -m 600 %{_builddir}/%{name}-%{version}/fuelmenu/fuelmenu/settings.yaml %{buildroot}/etc/fuel/astute.yaml

%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{_builddir}/%{name}-%{version}/fuelmenu/INSTALLED_FILES
%defattr(-,root,root)
%config(noreplace) /etc/fuel/astute.yaml
