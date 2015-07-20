%define name nailgun
%{!?version: %define version 7.0.0}
%{!?release: %define release 1}

Summary: Nailgun package
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: Apache
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
Prefix: %{_prefix}
BuildRequires:  python-setuptools
BuildRequires:  git
BuildRequires: npm
BuildRequires: nodejs
BuildArch: noarch
Requires:    python-alembic >= 0.6.2
Requires:    python-amqplib >= 1.0.2
Requires:    python-anyjson >= 0.3.3
Requires:    python-argparse >= 1.2.1
Requires:    python-babel >= 1.3
Requires:    python-crypto >= 2.6.1
Requires:    python-decorator >= 3.4.0
Requires:    python-fysom >= 1.0.11
Requires:    python-iso8601 >= 0.1.9
Requires:    python-jinja2 >= 2.7
Requires:    python-jsonschema >= 2.3.0
Requires:    python-keystoneclient >= 0.11
Requires:    python-keystonemiddleware >= 1.2.0
Requires:    python-kombu >= 1:3.0.16
Requires:    python-mako >= 0.9.1
Requires:    python-markupsafe >= 0.18
Requires:    python-netaddr >= 0.7.10
Requires:    python-netifaces >= 0.8
Requires:    python-oslo-config >= 1:1.2.1
Requires:    python-oslo-serialization >= 1.0.0
Requires:    python-paste >= 1.7.5.1
Requires:    python-ply >= 3.4
Requires:    python-psycopg2 >= 2.5.1
Requires:    python-requests >= 1.2.3
Requires:    python-simplejson >= 3.3.0
Requires:    python-six >= 1.5.2
Requires:    python-sqlalchemy >= 0.7.9
Requires:    python-stevedore >= 0.14
Requires:    python-urllib3 >= 1.7
Requires:    python-webpy >= 0.37
Requires:    python-wsgilog >= 0.3
Requires:    python-wsgiref >= 0.1.2
Requires:    PyYAML >= 3.10
Requires:    python-novaclient >= 2.17.0
Requires:    python-networkx-core >= 1.8.0
Requires:    python-cinderclient >= 1.0.7
Requires:    pydot-ng >= 1.0.0
Requires:    python-ordereddict >= 1.1
# Workaroud for babel bug
Requires:    pytz

BuildRequires: nodejs-bower
BuildRequires: nodejs-casperjs
BuildRequires: nodejs-esprima-fb
BuildRequires: nodejs-event-stream
BuildRequires: nodejs-glob
BuildRequires: nodejs-gulp
BuildRequires: nodejs-gulp-autoprefixer
BuildRequires: nodejs-gulp-bower
BuildRequires: nodejs-gulp-filter
BuildRequires: nodejs-gulp-intermediate
BuildRequires: nodejs-gulp-jison
BuildRequires: nodejs-gulp-jscs
BuildRequires: nodejs-gulp-jshint
BuildRequires: nodejs-gulp-less
BuildRequires: nodejs-gulp-lintspaces
BuildRequires: nodejs-gulp-react
BuildRequires: nodejs-gulp-replace
BuildRequires: nodejs-gulp-shell
BuildRequires: nodejs-gulp-util
BuildRequires: nodejs-intern
BuildRequires: nodejs-jshint-stylish
BuildRequires: nodejs-lodash-node
BuildRequires: nodejs-main-bower-files
BuildRequires: nodejs-minimist
BuildRequires: nodejs-phantomjs
BuildRequires: nodejs-requirejs
BuildRequires: nodejs-rimraf
BuildRequires: nodejs-run-sequence
BuildRequires: nodejs-selenium-standalone
BuildRequires: nodejs-uglify-js
BuildRequires: nodejs-libjs-jquery
BuildRequires: nodejs-libjs-js-cookie
BuildRequires: nodejs-libjs-classnames
BuildRequires: nodejs-libjs-react
BuildRequires: nodejs-libjs-requirejs
BuildRequires: nodejs-libjs-requirejs-plugins
BuildRequires: nodejs-libjs-requirejs-text
BuildRequires: nodejs-libjs-require-css
BuildRequires: nodejs-libjs-jsx-requirejs-plugin
BuildRequires: nodejs-libjs-routefilter
BuildRequires: nodejs-libjs-lodash
BuildRequires: nodejs-libjs-autoNumeric
BuildRequires: nodejs-libjs-backbone
BuildRequires: nodejs-libjs-backbone.stickit
BuildRequires: nodejs-libjs-i18next
BuildRequires: nodejs-libjs-less
BuildRequires: nodejs-libjs-bootstrap
BuildRequires: nodejs-libjs-open-sans-fontface
BuildRequires: nodejs-libjs-react-dnd
BuildRequires: nodejs-libjs-es5-shim
BuildRequires: nodejs-libjs-sinon
BuildRequires: nodejs-libjs-underscore

%description
Nailgun package

%prep
%setup -cq -n %{name}-%{version}

cp -R /usr/lib/node_modules/ %{_builddir}/%{name}-%{version}/nailgun/node_modules/
cp -R /usr/lib/bower_components/ %{_builddir}/%{name}-%{version}/nailgun/bower_components/

%build
cd %{_builddir}/%{name}-%{version}/nailgun && %{_builddir}/%{name}-%{version}/nailgun/node_modules/gulp/bin/gulp.js build --static-dir=compressed_static
[ -n %{_builddir} ] && rm -rf %{_builddir}/%{name}-%{version}/nailgun/static
mv %{_builddir}/%{name}-%{version}/nailgun/compressed_static %{_builddir}/%{name}-%{version}/nailgun/static
cd %{_builddir}/%{name}-%{version}/nailgun && python setup.py build
cd %{_builddir}/%{name}-%{version}/network_checker && python setup.py build
cd %{_builddir}/%{name}-%{version}/shotgun && python setup.py build
cd %{_builddir}/%{name}-%{version}/fuelmenu && python setup.py build
cd %{_builddir}/%{name}-%{version}/fuel_upgrade_system/fuel_package_updates && python setup.py build

%install
cd %{_builddir}/%{name}-%{version}/nailgun && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/nailgun/INSTALLED_FILES
cd %{_builddir}/%{name}-%{version}/network_checker && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/network_checker/INSTALLED_FILES
cd %{_builddir}/%{name}-%{version}/shotgun && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/shotgun/INSTALLED_FILES
cd %{_builddir}/%{name}-%{version}/fuelmenu && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/fuelmenu/INSTALLED_FILES
cd %{_builddir}/%{name}-%{version}/fuel_upgrade_system/fuel_package_updates && python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=%{_builddir}/%{name}-%{version}/fuel_upgrade_system/fuel_package_updates/INSTALLED_FILES
mkdir -p %{buildroot}/opt/nailgun/bin
mkdir -p %{buildroot}/etc/cron.d
mkdir -p %{buildroot}/etc/fuel
install -d -m 755 %{buildroot}/etc/fuel
install -m 600 %{_builddir}/%{name}-%{version}/fuelmenu/fuelmenu/settings.yaml %{buildroot}/etc/fuel/astute.yaml
install -m 755 %{_builddir}/%{name}-%{version}/bin/fencing-agent.rb %{buildroot}/opt/nailgun/bin/fencing-agent.rb
install -m 644 %{_builddir}/%{name}-%{version}/bin/fencing-agent.cron %{buildroot}/etc/cron.d/fencing-agent
install -p -D -m 755 %{_builddir}/%{name}-%{version}/bin/download-debian-installer %{buildroot}%{_bindir}/download-debian-installer


%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{_builddir}/%{name}-%{version}/nailgun/INSTALLED_FILES
%defattr(0755,root,root)

%package -n nailgun-net-check

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


%description -n nailgun-net-check
This is a network tool that helps to verify networks connectivity
between hosts in network.

%files -n nailgun-net-check -f %{_builddir}/%{name}-%{version}/network_checker/INSTALLED_FILES
%defattr(-,root,root)

%package -n shotgun

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

%description -n shotgun
Shotgun package.

%files -n shotgun -f  %{_builddir}/%{name}-%{version}/shotgun/INSTALLED_FILES
%defattr(-,root,root)

%package -n fuelmenu

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

%description -n fuelmenu
Summary: Console utility for pre-configuration of Fuel server

%files -n fuelmenu -f %{_builddir}/%{name}-%{version}/fuelmenu/INSTALLED_FILES
%defattr(-,root,root)
%config(noreplace) /etc/fuel/astute.yaml


%package -n fencing-agent
Summary:   Fencing agent
Version:   %{version}
Release:   %{release}
License:   GPLv2
BuildRoot: %{_tmppath}/%{name}-%{version}
URL:       http://mirantis.com
Requires:  rubygem-ohai

%description -n fencing-agent
Fuel fencing agent

%files -n fencing-agent
/opt/nailgun/bin/fencing-agent.rb
/etc/cron.d/fencing-agent
%defattr(-,root,root)


%package -n fuel-package-updates

Summary: Fuel package update downloader
Version: %{version}
Release: %{release}
License: Apache
Group: Development/Libraries
Prefix: %{_prefix}
BuildArch: noarch
Requires:  python-keystoneclient >= 0.11
Requires:  python-keystonemiddleware >= 1.2.0
Requires:  python-ordereddict >= 1.1

%description -n fuel-package-updates
Command line utility to download apt/yum repositories for Fuel

%files -n fuel-package-updates  -f %{_builddir}/%{name}-%{version}/fuel_upgrade_system/fuel_package_updates/INSTALLED_FILES
%defattr(0755,root,root)

%package -n fuel-provisioning-scripts

Summary: Fuel provisioning scripts
Version: %{version}
Release: %{release}
URL:     http://mirantis.com
License: Apache
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Requires:    wget

%description -n fuel-provisioning-scripts
Fuel provisioning scripts package.
This is a part of Fuel All-in-one Controle plane
for Openstack. For more info go to http://wiki.openstack.org/Fuel

%files -n fuel-provisioning-scripts
%defattr(-,root,root)
%{_bindir}/download-debian-installer
