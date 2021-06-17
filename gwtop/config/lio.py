#!/usr/bin/env python

# import random
import subprocess
import json
import rados

from rtslib_fb import root

from ceph_iscsi_config.utils import get_pool_name
import ceph_iscsi_config.settings as settings


def add_rbd_maps(devices):
    """
    Add image name and pool for the rbd to the device dict
    :param devices: dict contained an item for each device
    :return: updates the passed in devices dict
    """

    rbd_str = subprocess.check_output('rbd showmapped --format=json',
                                      shell=True)
    rbd_dict = json.loads(rbd_str)      # make a dict

    for key in rbd_dict:
        dev_id = rbd_dict[key]['device'].split('/')[-1]
        # it's possible that there is a difference between LIO and rbd
        # showmapped we first check that the dev_id from LIO is in the dict
        # before updating it
        if dev_id in devices:
            devices[dev_id]['pool-image'] = '{}/{}'.format(rbd_dict[key]['pool'],
                                                           rbd_dict[key]['name'])


class GatewayConfig(object):
    """
    Configuration class representing the local LIO configuration, based on the
    meta data from the rados configuration object or the cli overrides
    """

    def __init__(self, options):
        """
        Instantiate a gateway object, using the runtime options as a start
        point. The object just serves to hold configuration information about
        the iscsi gateway nodes
        :param options: runtime options
        """

        self.gateways = []      # list of gateway names
        self.diskmap = {}       # dict - device, pointing to client shortname

        self.error = False      # error flag

        # gateway name overrides
        if options.gateways:
            # use the gateway names provided
            self.gateways = options.gateways.split(',')
        else:
            # Neither the config files or the runtime have specified the
            # gateways so pick them up from the config object
            rados_pool, cfg_object = options.config_object.split('/')
            with rados.Rados(conffile=settings.config.cephconf) as cluster:
                with cluster.open_ioctx(rados_pool) as ioctx:
                    try:
                        # default object read is 8k, so use 128K for the read
                        size, mtime = ioctx.stat(cfg_object)
                        config_str = ioctx.read(cfg_object,
                                                length=(size + 1))
                    except rados.ObjectNotFound:
                        self.error = True
                    else:
                        # the object exists, go get the gateway information
                        cfg_json = json.loads(config_str)
                        self.gateways = [gw_key for gw_key in cfg_json['gateways']
                                         if isinstance(cfg_json['gateways'][gw_key], dict)]
                        if not self.gateways:
                            self.error = True



        if not self.error:
            self.diskmap = self._get_mapped_disks()

    def _get_mapped_disks(self):
        '''
        return a dict indexed by a pool/image name that points to the client
        that has this device mapped to it. If the client mapped is currently
        connected the name used is the alias (dns) of the client from LIO
        session information - if not, we just use the last qualifier of the
        iqn
        :return: dict <pool>.<image> --> <client_name> | '- multi -'
        '''

        map = {}
        lio_root = root.RTSRoot()

        # get a list of active sessions on this host indexed by the iqn
        connections = {}
        for con in lio_root.sessions:
            nodeacl = con['parent_nodeacl']
            connections[nodeacl.node_wwn] = {"state": con['state'],
                                             "alias": con['alias'].split('.')[0]}

        # seed the map dict with an entry for each storage object
        for so in lio_root.storage_objects:
            map[so.name] = ''

        # process each client
        for node in lio_root.node_acls:

            # for each client, look at it's luns
            for m_lun in node.mapped_luns:

                tpg_lun = m_lun._get_tpg_lun()
                disk_name = tpg_lun.storage_object.name

                if map[disk_name]:
                    map[disk_name] = '- multi -'
                else:
                    # if this node is connected, try and use it's alias
                    if node.node_wwn in connections:
                        alias_name = connections[node.node_wwn]["alias"]
                        if alias_name:
                            map[disk_name] = "{}(CON)".format(alias_name)
                        else:
                            map[disk_name] = "{}(CON)".format(node.node_wwn.split(':')[-1])
                    else:
                        map[disk_name] = "{}".format(node.node_wwn.split(':')[-1])

        return map

    def _get_client_count(self):
        r = root.RTSRoot()
        nodeACL_list = [client.node_wwn
                        for client in r.node_acls]
        return len(nodeACL_list)

    client_count = property(_get_client_count,
                           doc="return the number of clients defined")

def get_gateway_info(opts):

    config = GatewayConfig(opts)

    return config
