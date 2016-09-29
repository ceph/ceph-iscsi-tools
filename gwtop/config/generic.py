#!/usr/bin/env python

import os

def get_devid(udev_path):
    """
    return the device id of i.e. rbdX for a given udev path
    """

    if udev_path.startswith('/dev/mapper'):
        dm_id = os.path.realpath(udev_path).split('/')[2]
        dev_id = os.listdir(os.path.join('/sys/class/block/{}/slaves'.format(dm_id)))[0]
    else:
        dev_id = udev_path.split('/')[2]             # rbdX

    return dev_id


class Config(object):
    """
    Simple object to hold the current configuration across the gateways
    """

    def __repr__(self):
        return str(self.__dict__)


class DiskMetrics(Config):
    """
    Simple object used to to hold disk metrics
    """


class GatewayMetrics(Config):
    """
    Simple config object
    """


class HostSummary(object):
    """
    Simple object to hold the current configuration across the gateways
    """

    def __init__(self):
        self.cpu_busy = []
        self.net_in = []
        self.net_out = []
        self.timestamp = ''
        self.total_capacity = 0
        self.total_iops = 0

    def __repr__(self):
        return str(self.__dict__)


class DiskSummary(object):
    """
    Class defining objects providing disk summary statistics
    """

    def __init__(self):
        self.reads = []
        self.writes = []
        self.readkb = []
        self.writekb = []
        self.await = []
        self.r_await = []
        self.w_await = []

    def __repr__(self):
        return str(self.__dict__)
