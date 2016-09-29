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
