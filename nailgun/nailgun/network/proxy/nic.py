from nailgun.db.sqlalchemy import models
from nailgun.network.proxy import BaseProxy


class NICProxy(BaseProxy):

    def __init__(self):
        super(NICProxy, self).__init__()
        self.model = models.NodeNICInterface


class BondProxy(BaseProxy):

    def __init__(self):
        super(BondProxy, self).__init__()
        self.model = models.NodeBondInterface


class NetworkNICAssignmentProxy(BaseProxy):

    def __init__(self):
        super(NetworkNICAssignmentProxy, self).__init__()
        self.model = models.NetworkNICAssignment


class NetworkBondAssignmentProxy(BaseProxy):

    def __init__(self):
        super(NetworkBondAssignmentProxy, self).__init__()
        self.model = models.NetworkBondAssignment
