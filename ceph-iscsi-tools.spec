Name:		ceph-iscsi-tools
Version:	1.0
Release:	1%{?dist}
Summary:	Tools to interact with the ceph's iscsi gateway nodes
Group:		Applications/System
License:	GPLv3

URL:		https://github.com/pcuzner/ceph-iscsi-tools
Source0:	https://github.com/pcuzner/%{name}/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires: python2-devel
BuildRequires: python-setuptools

Requires: pcp
Requires: python-pcp
Requires: python-rtslib
Requires: python-rados

%description
This package provides tools to help the admin interact with
the iscsi gateway nodes.

'gwtop' is a CLI command to aggregate performance stats from
a number iscsi gateways into a single view. Performance
metrics are extracted from performance co-pilot (pmcd)
running on each gateway node, and aggregated into a single
view.

%prep
%setup -q 

%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
%{__python} setup.py install --skip-build --root %{buildroot} --install-scripts %{_bindir}
mkdir -p %{buildroot}%{_mandir}/man8
install -m 0644 gwtop.8 %{buildroot}%{_mandir}/man8/
gzip %{buildroot}%{_mandir}/man8/gwtop.8

%files
%doc README
%doc LICENSE
%doc samples/
%{_bindir}/gwtop
%{python2_sitelib}/*
%{_mandir}/man8/gwtop.8.gz

%changelog
* Mon Oct 17 2016 Paul Cuzner <pcuzner@redhat.com> 1.0-1
- switched data source from pmcd's disk.partition to disk.dm
- simplified the lookup of dm device to rbd name, subprocess call removed
- added custom exception handler to mask backtrace unless in debug
- added i/o source flag showing whether the i/o to an rbd is local or not
- updated invocation to allow sort by io source (t or O ... this or other)
- added sample defaults file
- added high level ceph output to the display (health and # osd's)
- added man page

* Tue Oct 11 2016 Paul Cuzner <pcuzner@redhat.com> 0.2-1
- added a sort key enabling the summary stats to be sorted by a given metric
- sort can be in ascending/descending sequence
- internally changed the indexing of the data from rbdX to pool/image

* Thu Sep 29 2016 Paul Cuzner <pcuzner@redhat.com> 0.1-1
- initial rpm packaging


