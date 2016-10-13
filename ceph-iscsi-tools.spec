Name:		ceph-iscsi-tools
Version:	0.3
Release:	1%{?dist}
Summary:	iostat/top like tools to show disk performance metrics aggregated across a number of iscsi gateways
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
CLI command to aggregate performance stats from a number iscsi gateways
into a single view. Performance metrics are extracted from performance
co-pilot (pmcd) running on each gateway node, and presented to the admin
to given an holistic view of the load across all iscsi gateways in the
configuration. The gateways to contact are determined either through the
-g invocation parameter, the .gwtop.rc file in the admins home directory
or from the rados configuration object (if the config was built with the
ceph-iscsi-ansible tools.

%prep
%setup -q 


%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
%{__python} setup.py install --skip-build --root %{buildroot} --install-scripts %{_bindir}
# mkdir -p %{buildroot}%{_mandir}/man8
# install -m 0644 gstatus.8 %{buildroot}%{_mandir}/man8/
# gzip %{buildroot}%{_mandir}/man8/gstatus.8


%files
# %defattr(-,root,root,-)
%doc README
%doc LICENSE
%doc samples/
%{_bindir}/gwtop
%{python2_sitelib}/*
# %{_mandir}/man8/gstatus.8.gz


%changelog
* Fri Oct 14 2016 Paul Cuzner <pcuzner@redhat.com> 0.3-1
- switched from disk.partition stats to disk.dm stats from pmcd
- simplified the mapping of dm device to rbd name, removing subprocess call
- added custom exception handler to mask backtrace unless in debug

* Tue Oct 11 2016 Paul Cuzner <pcuzner@redhat.com> 0.2-1
- added a sort key enabling the summary stats to be sorted by a given metric
- sort can be in ascending/descending sequence
- internally changed the indexing of the data from rbdX to pool/image

* Thu Sep 29 2016 Paul Cuzner <pcuzner@redhat.com> 0.1-1
- initial rpm packaging


