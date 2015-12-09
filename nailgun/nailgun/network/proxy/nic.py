from nailgun.db.sqlalchemy import models
from nailgun.network.proxy import BaseProxy


class NICProxy(BaseProxy):

    def __init__(self):
        super(NICProxy, self).__init__()
        self.model = models.NodeNICInterface


class NetworkNICAssignmentProxy(BaseProxy):

    def __init__(self):
        super(NetworkNICAssignmentProxy, self).__init__()
        self.model = models.NetworkNICAssignment
