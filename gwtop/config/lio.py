#!/usr/bin/env python

# import random
import subprocess
import json
import rados

from rtslib_fb import root

from gwtop.config.generic import get_devid

CEPH_CONF = '/etc/ceph/ceph.conf'

def add_rbd_maps(devices):
    """
    Add image name and pool for the rbd to the device dict
    :param devices: dict contained an item for each device
    :return: updates the passed in devices dict
    """

    rbd_str = subprocess.check_output('rbd showmapped --format=json', shell=True)
    rbd_dict = json.loads(rbd_str)      # make a dict

    for key in rbd_dict:
        dev_id = rbd_dict[key]['device'].split('/')[-1]
        # it's possible that there is a difference between LIO and rbd showmapped
        # we first check that the dev_id from LIO is in the dict before updating it
        if dev_id in devices:
            devices[dev_id]['pool-image'] = '{}/{}'.format(rbd_dict[key]['pool'], rbd_dict[key]['name'])


class GatewayConfig(object):
    """
    Configuration class representing the local LIO configuration
    """

    def __init__(self, options):
        """
        Instantiate a gateway object, using the runtime options as a start point
        The object just serves to hold configuration information about the iscsi gateway nodes
        :param options: runtime options
        """

        self.gateways = []      # list of gateway names
        self.diskmap = {}       # dict - device, pointing to client shortname
        self.client_count = 0   # default count of clients connected to the gateway cluster

        self.config = None      # config object from the rados config object
        self.error = False      # error flag

        # when setting the environment up, 1st allow for overrides
        # TEST mode
        # if runtime_opts.test:
        #     # use some test names and make up some clients
        #     self.gateways = ['localhost','eric']
        #     self.diskmap = self._disk2client_mangler(devices)

        # gateway name overrides
        if options.gateways:
            # use the gateway names provided
            self.gateways = options.gateways.split(',')
        else:
            # Neither the config files or the runtime have specified the gateways
            # so try and pick them up from the config object in the rbd pool
            rados_pool, cfg_object = options.config_object.split('/')
            with rados.Rados(conffile=CEPH_CONF) as cluster:
                with cluster.open_ioctx(rados_pool) as ioctx:
                    try:
                        # default object read is 8k, so use 128K for the read
                        config_str = ioctx.read(cfg_object, length=131072)
                    except rados.ObjectNotFound:
                        self.error = True
                    else:
                        # the object exists, so try and get the gateway information
                        config_js = json.loads(config_str)
                        self.gateways = [gw_key for gw_key in config_js['gateways']
                                         if isinstance(config_js['gateways'][gw_key], dict)]
                        if not self.gateways:
                            self.error = True

        if not self.error:
            self.diskmap = self._get_mapped_disks()
            self.client_count = self._unique_clients()

    def _get_mapped_disks(self):
        map = {}
        lio_root = root.RTSRoot()

        connections = {}
        for con in lio_root.sessions:
            nodeacl = con['parent_nodeacl']
            connections[nodeacl.node_wwn] = con['state']

        for m_lun in lio_root.mapped_luns:
            udev_path = m_lun.tpg_lun.storage_object.udev_path
            dev_id = get_devid(udev_path)
            if dev_id in map:
                # seen this device before, so it's shared across clients
                suffix = ""
                client_shortname = "- multi -"
            else:
                client_iqn = m_lun.node_wwn
                suffix = ' (C)' if client_iqn in connections else ''
                client_shortname = client_iqn.split(':')[-1]

            map[dev_id] = client_shortname + suffix

        return map

    #
    # def _disk2client_mangler(self, devices):
    #     map = {}
    #     client_pfx = 'client-'
    #     client_sfx = random.sample(xrange(len(devices)*10), len(devices))
    #     ptr = 0
    #     for devname in devices:
    #         map[devname] = client_pfx + str(client_sfx[ptr])
    #         ptr += 1
    #
    #     return map

    def _unique_clients(self):
        # determine the number of unique client names in the disk -> client dict
        return len(set(self.diskmap.values()))

    # def refresh(self):
    #     pass


def get_gateway_info(opts):

    config = GatewayConfig(opts)

    return config
