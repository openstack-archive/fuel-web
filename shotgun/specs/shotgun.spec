%define name shotgun
%{!?version: %define version 8.0.0}
%{!?release: %define release 1}

Name: %{name}
Summary: Shotgun package
Version: %{version}
Release: %{release}
URL:     http://mirantis.com
License: Apache
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Requires:    postgresql
Requires:    python-fabric >= 1.10.0
Requires:    python-argparse
Requires:    tar
Requires:    gzip
Requires:    bzip2
Requires:    openssh-clients
Requires:    xz

%description
Shotgun package.

%prep
%setup -cq -n %{name}-%{version}

%build
cd %{_builddir}/%{name}-%{version}/shotgun && python setup.py build

%install
cd %{_builddir}/%{name}-%{version}/shotgun && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/shotgun/INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f  %{_builddir}/%{name}-%{version}/shotgun/INSTALLED_FILES
%defattr(-,root,root)
