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
