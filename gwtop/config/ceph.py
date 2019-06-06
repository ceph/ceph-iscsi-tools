#!/usr/bin/env python

__author__ = 'paul'

import rados
import json

import rados
import json

class CephCluster(object):

    conf = '/etc/ceph/ceph.conf'
    keyring = '/etc/ceph/ceph.client.admin.keyring'

    def __init__(self, conf=conf, keyring=keyring):
        self.conf = conf
        self.keyring = keyring
        self.status = {}

    def update_state(self):

        with rados.Rados(conffile=self.conf, conf=dict(keyring=self.keyring)) as cluster:
            cmd = {'prefix': 'status', 'format': 'json'}
            ret, buf_s, out = cluster.mon_command(json.dumps(cmd), b'')

        self.status = json.loads(buf_s)

    def _get_health(self):
        if 'health' not in self.status:
            return ''
        if self.status['health'].has_key('status'):
            return self.status['health']['status']
        else:
            return self.status['health']['overall_status']

    def _get_osds(self):
        return self.status['osdmap']['osdmap']['num_osds'] if 'osdmap' in self.status else ''

    health = property(_get_health,
                      doc="Get overall health of the ceph cluster")

    osds = property(_get_osds,
                    doc="Return a count of OSDs in the cluster")
