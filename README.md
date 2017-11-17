#ceph-iscsi-tools
This repo provides some helper tools for ceph/iscsi environments.

##gwtop
This is a top-like tool intended to be installed on each gateway node. It provides an aggregated view of I/O from each  
gateway node, combined with LIO information - matching the host device to a client using the device over iSCSI.  
Performance metrics are sourced from performance co-pilot (pmcd), so this service needs to be running on each gateway  
node.    

The output varies dependent on the pmda providing the metrics.  

For krbd based devices;

```
gwtop  2/2 Gateways   CPU% MIN:  4 MAX:  5    Network Total In:    2M  Out:    3M   10:20:09
Capacity:   8G    Disks:   8   IOPS:  500   Clients:  1   Ceph: HEALTH_OK          OSDs:   3
Pool.Image     Src  Device   Size     r/s     w/s    rMB/s     wMB/s    await  r_await  w_await  Client
iscsi.t1703          rbd0    500M       0       0     0.00      0.00     0.00     0.00     0.00              
iscsi.testme1        rbd5    500M       0       0     0.00      0.00     0.00     0.00     0.00                  
iscsi.testme2        rbd2    500M       0       0     0.00      0.00     0.00     0.00     0.00                     
iscsi.testme3        rbd3    500M       0       0     0.00      0.00     0.00     0.00     0.00              
iscsi.testme5        rbd1    500M       0       0     0.00      0.00     0.00     0.00     0.00              
rbd.myhost_1    T    rbd4      4G     500       0     1.95      0.00     2.37     2.37     0.00  rh460p(CON)         
rbd.test_2           rbd6      1G       0       0     0.00      0.00     0.00     0.00     0.00              
rbd.testme           rbd7    500M       0       0     0.00      0.00     0.00     0.00     0.00              
```

For user backed storage (TCMU devices)  

```
gwtop  2/2 Gateways   CPU% MIN:  4 MAX:  5    Network Total In:    2M  Out:    3M   10:20:00
Capacity:   8G    Disks:   8   IOPS:  503   Clients:  1   Ceph: HEALTH_OK          OSDs:   3
Pool.Image       Src    Size     iops     rMB/s     wMB/s   Client
iscsi.t1703             500M        0      0.00      0.00                       
iscsi.testme1           500M        0      0.00      0.00                       
iscsi.testme2           500M        0      0.00      0.00                       
iscsi.testme3           500M        0      0.00      0.00                       
iscsi.testme5           500M        0      0.00      0.00                       
rbd.myhost_1      T       4G      504      1.95      0.00   rh460p(CON)         
rbd.test_2                1G        0      0.00      0.00                       
rbd.testme              500M        0      0.00      0.00                       
```

gwtop determines the gateway configuration by looking at the following sources (in order)  
- the invocation used the -g host-1,host-2 over-ride  
- the user has a .gwtop.rc file in the root of their home directory  
- the environment was created by the ceph-iscsi-ansible project, and has committed state to the rbd/gateway.conf object  

An example of the 'rc' file is provided in the /usr/share/doc directory.

Invocation provides the following options;
  
```  
[root@ceph-1 ~]# gwtop -h
usage: gwtop [-h] [-b] [-c CONFIG_OBJECT] [-g GATEWAYS]
             [-i {1,2,3,4,5,6,7,8,9}] [-d] [-m {text}] [-p {dm,lio}]
             [-s {image,rbd_name,reads,writes,await,io_source}] [-r] [-v]

Show iSCSI gateway performance metrics

optional arguments:
  -h, --help            show this help message and exit
  -b, --busy-only       show only active devices (iops > 0)
  -c CONFIG_OBJECT, --config-object CONFIG_OBJECT
                        pool and object name holding the gateway config object
                        (pool/object_name)
  -g GATEWAYS, --gateways GATEWAYS
                        comma separated iscsi gateway server names
  -i {1,2,3,4,5,6,7,8,9}, --interval {1,2,3,4,5,6,7,8,9}
                        monitoring interval (secs)
  -d, --debug           run with additional debug
  -m {text}, --mode {text}
                        output mode
  -p {dm,lio}, --provider {dm,lio}
                        pcp provider type lio or dm
  -s {image,rbd_name,reads,writes,await,io_source}, --sortkey {image,rbd_name,reads,writes,await,io_source}
                        sort key sequence
  -r, --reverse         use reverse sort when displaying the stats
  -v, --version         show program's version number and exit
```  


#rbdperf  
The rbdperf tool uses the admin_socket interface for librbd to gain an insight into the latency and performance of application I/O at the libbd layer.
  
##Dependencies  
Before you can use the tool the local ceph.conf file needs a ```[client]``` section that enables the admin_socket interface.  
```bash
[client]
admin socket = /var/run/ceph/$name.$pid.$cctid.asok
```  

##Installation  
Just copy the rbdperf.py file to your bin directory of choice :)

##How it works  
With the admin_socket enabled, each LUN access by a librbd client willl generate an admin socket interface. rbdperf simple polls the socket to extract IO stats.  
However, some sockets don't provide librbd stats, so when the tool starts up it finds all the sockets, and looks for a librbd section. rbdperf keeps the reference
to the sockets that contain librbd information, and drops any that don't.  
  
The sockets are polled and the results presented to the user. An interval of 5 secs seems to be the most accurate representation of load (at least
on my test rig!).

##Running rbdperf  
```bash
[root@rh7-gw2 ~]# python rbdperf.py -h 
usage: rbdperf [-h] [-i INTERVAL] [-r RBD_IMAGE]

Show librbd performance metrics

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        refresh interval (default = 1)
  -r RBD_IMAGE, --rbd-image RBD_IMAGE
                        Show specific image - pool-image_name format
[root@rh7-gw2 ~]# python rbdperf.py 
No librbd section found in socket /var/run/ceph/client.admin.971.140364899948976.asok...dropping
No librbd section found in socket /var/run/ceph/client.admin.971.26803984.asok...dropping
No librbd section found in socket /var/run/ceph/client.admin.970.35892144.asok...dropping
waiting...
Pool-Image Name                 r_iops   w_iops     r_lat    w_lat   r_tput    w_tput
rbd-disk_1                         715        0      3.29     0.00    5.59M        0K
rbd-disk_2                           0        0      0.00     0.00       0K        0K
rbd-disk_3                           0        0      0.00     0.00       0K        0K
rbd-disk_4                           0        0      0.00     0.00       0K        0K
rbd-mydemo                           0        0      0.00     0.00       0K        0K
rbd-test                             0        0      0.00     0.00       0K        0K
rbd-test1                            0        0      0.00     0.00       0K        0K
rbd-test13                           0        0      0.00     0.00       0K        0K
rbd-test2                            0        0      0.00     0.00       0K        0K
^C[root@rh7-gw2 ~]# python rbdperf.py -r rbd-disk_1
No librbd section found in socket /var/run/ceph/client.admin.971.140364899948976.asok...dropping
No librbd section found in socket /var/run/ceph/client.admin.971.26803984.asok...dropping
No librbd section found in socket /var/run/ceph/client.admin.970.35892144.asok...dropping
waiting...
Pool-Image Name                 r_iops   w_iops     r_lat    w_lat   r_tput    w_tput
rbd-disk_1                         718        0      3.18     0.00    5.61M        3K
rbd-disk_1                         708        0      3.32     0.00    5.54M        0K
rbd-disk_1                         700        0      3.19     0.00    5.47M        0K
rbd-disk_1                         709        0      3.19     0.00    5.55M        0K

```

