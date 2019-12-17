Name:		ceph-iscsi-tools
Version:	2.1
Release:	1%{?dist}
Summary:	Tools to interact with the ceph's iscsi gateway nodes
Group:		Applications/System
License:	GPLv3

URL:		https://github.com/ceph/ceph-iscsi-tools
Source0:	https://github.com/ceph/%{name}/archive/%{version}/%{name}-%{version}.tar.gz
BuildArch:	noarch

%if 0%{?rhel} < 8
BuildRequires: python2-devel
BuildRequires: python-setuptools

Requires: pcp >= 3.11
Requires: python-pcp >= 3.11
Requires: python-rtslib >= 2.1
Requires: python-rados >= 10.2.2
Requires: ceph-iscsi >= 3.0
Requires: pcp-pmda-lio >= 1.0
%else
BuildRequires: python3-devel
BuildRequires: python3-setuptools

Requires: pcp >= 4.3
Requires: python3-pcp >= 4.3
Requires: python3-rtslib >= 2.1.fb68
Requires: python3-rados >= 10.2.2
Requires: ceph-iscsi >= 3.0
Requires: pcp-pmda-lio >= 4.3
%endif

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
%{_mandir}/man8/gwtop.8.gz
%if 0%{?rhel} < 8
%{python2_sitelib}/*
%else
%{python3_sitelib}/*
%endif

%changelog
* Tue Aug 15 2017 Jason Dillaman <dillaman@redhat.com> 2.1-1
- gwtop: added device filter parameter to show specific devices
- add -t and -l options to gwtop
- gwtop: add iops as a sort field for the output
- BACKLOG: Add backlog file to track user stores for additional functionality
- gwtop: Updated the logger name to match the scriptname

* Tue Dec 20 2016 Paul Cuzner <pcuzner@redhat.com> 2.0-1
- added provider runtime option (dm or lio) to determine the metrics
- PCP collector restructured to support LIO and LINUX pmda providers
- Added collector for LIO stats (pcp-pmda-lio)
- Added -p switch on invocation to use the lio statistics
- output formatting now an attribute of the relevant pcp collector class
- added disk count to summary line
- added reset of terminal if an exception occurs during textmode run
- added -b switch to restrict display to only busy LUNs
- catch thread exceptions within the generic exception_handler function
- default pcp collector is chosen based on the current LUNs defined to LIO
- fix rounding issue on LIO iops stats display
- fix cpu usage calculation (rounding errors seen in 24c configurations)
- man page updates
- validate sort key request against the pcp provider type


* Thu Dec 08 2016 Paul Cuzner <pcuzner@redhat.com> 1.1-5
- fix issue with missing disk perf stats due to mismatch in disk names
- fix client count
- use dns name for the client name if the client is connected

* Fri Oct 28 2016 Paul Cuzner <pcuzner@redhat.com> 1.1-1
- size the output line to the maximum rbd image name
- added the settings module from ceph_iscsi_config to enable non-default ceph names
- add support for lun names of the format pool.image in lio

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


