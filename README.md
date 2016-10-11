#ceph-iscsi-tools
This repo provides some helper tools for ceph/iscsi environments.

##gwtop
This is a top-like tool intended to be installed on each gateway node. It provides an aggregated view of I/O from each  
gateway node, combined with LIO information - matching the host device to a client using the device over iSCSI.  
Performance metrics are sourced from performance co-pilot (pmcd), so this service needs to be running on each gateway  
node.    

The output below shows the kind of output gwtop generates.  

```
gwtop   2 Gateways   CPU% MIN:  0 MAX:  0    Network Total In:    3K  Out:    4K   12:05:34  
Capacity:  125G    IOPS:     0   Clients:  2  
Device   Pool/Image        Size     r/s     w/s    rMB/s     wMB/s    await  r_await  w_await  Client  
 rbd0   rbd/ansible1        30G       0       0     0.00      0.00     0.00     0.00     0.00  rh7-iscsi-client  
 rbd1   rbd/ansible2        15G       0       0     0.00      0.00     0.00     0.00     0.00  rh7-iscsi-client  
 rbd2   rbd/ansible3        30G       0       0     0.00      0.00     0.00     0.00     0.00  w2k12r2    
 rbd3   rbd/ansible4        50G       0       0     0.00      0.00     0.00     0.00     0.00             
```

The gateway configuration is determined gwtop looking at the following sources (in order)  
- the invocation used the -g host-1,host-2 over-ride  
- the user has a .gwtop.rc file in the root of their home directory  
- the environment was created by the ceph-iscsi-ansible project, and has committed state to the rbd/gateway.conf object  

An example of the 'rc' file is provided in the /usr/share/doc directory.

Invocation provides the following options;
  
```  
[root@ceph-1 lvm]# gwtop -h  
usage: igwtop [-h] [-c CONFIG_OBJECT] [-g GATEWAYS] [-i {1,2,3,4,5,6,7,8,9}]  
              [-d] [-m {text}] [-s {image,rbd_name,reads,writes,await}] [-r]  
              [-v]  

Show iSCSI gateway performance metrics  
  
optional arguments:  
  -h, --help            show this help message and exit  
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
  -s {image,rbd_name,reads,writes,await}, --sortkey {image,rbd_name,reads,writes,await}  
                        sort key sequence  
  -r, --reverse         use reverse sort when displaying the stats  
  -v, --version         show program's version number and exit  

```  
