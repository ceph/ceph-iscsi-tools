#!/usr/bin/env python

# get the disks available on this host
# filter for rbd devices and return a dict of
# disk objects to the caller
import subprocess
import json
import glob
import os

from rtslib_fb import root

# from gwtop.config.lio import add_rbd_maps
# from gwtop.config.generic import get_devid
from ceph_iscsi_config.utils import get_pool_name

def str2dict(kv_string, dict_key):
    """ only relevant for testing on non gateway hosts
    :param kv_string: key=value string
    :param dict_key: key to use for the dict returned to the caller
    :return: dict converted from the string
    """

    ret_dict = {}
    members = []
    for dev in kv_string.split('\n'):
        s = ''
        for pair in dev.split():
            k, v = pair.split('=')
            s += '"{}": {}, '.format(k.lower(), v)

        s = '{{ {} }}'.format(s[:-2])               # drop hanging ','
        d = json.loads(s)
        members.append(d)

    ret_dict[dict_key] = members[:-1]               # drop last empty member
    return ret_dict


def get_device_info():
    """ Assuming all devices are mapped to all gateways, we can just
        query the localhost for device information that can later be
        combined with the metrics returned from pcp
    """

    if glob.glob('/sys/kernel/config/target/core/iblock*'):
        return get_lio_devices()
    else:
        # testing only really - should remove in the future
        return get_local_devices()


def get_local_devices():
    """ only relevant for testing
    :return:
    """
    device_blacklist = ('sr', 'vd')
    device_data = {}
    # for upstream lsblk version 2.28, it's simpler to use -J to go straight to json
    # lsblk_out = subprocess.check_output('lsblk -d -S -b -J -o NAME,SIZE,ROTA,TYPE', shell=True)

    # however, for downstream util-linux version is 2.23 doesn't have -J, so use -P instead
    lsblk_out = subprocess.check_output('lsblk -d -b -P -o NAME,SIZE,ROTA', shell=True)
    blk_data = str2dict(lsblk_out, 'blockdevices')

    for dev_dict in blk_data['blockdevices']:
        dev_name = dev_dict['name']
        if dev_name.startswith(device_blacklist):
            continue
        del dev_dict['name']
        device_data[dev_name] = dev_dict

    return device_data


def get_lio_devices():
    """
    LIO uses the kernel's configfs feature to store and manage configuration
    data, so use rtslib to get a list of the devices

    :return: dict of dicts describing the rbd devices mapped to LIO
    """

    device_data = {}
    pools = {}

    lio_root = root.RTSRoot()
    # iterate over all luns - this will pick up the same lun mapped to
    # multiple tpgs - so we look out for that
    for lun in lio_root.luns:

        dm_id = os.path.basename(lun.storage_object.udev_path)
        dm_num = dm_id.split('-')[0]

        dev_path = lun.storage_object.path
        # '/sys/kernel/config/target/core/iblock_0/ansible3'
        iblock_name = dev_path.split('/')[-2]

        image_name = lun.storage_object.name
        if dm_num in pools:
            pool_name = pools[dm_num]
        else:
            pools[dm_num] = get_pool_name(pool_id=int(dm_num))
            pool_name = pools[dm_num]

        if '.' in image_name:
            # assume new format names that have the pool name in already
            key = image_name
        else:
            key = "{}.{}".format(pool_name, image_name)

        if key not in device_data:

            rbd_name = 'rbd{}'.format(iblock_name.split('_')[1])
            image_size = lun.storage_object.size
            wwn = lun.storage_object.wwn

            device_data[key] = {"size": image_size,
                                "wwn": wwn,
                                "rbd_name": rbd_name,
                                "pool": pool_name,
                                "image_name": image_name}

    return device_data


