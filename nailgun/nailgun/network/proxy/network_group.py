from nailgun.db.sqlalchemy import models
from nailgun.network.proxy import BaseProxy


class NetworkGroupProxy(BaseProxy):

    def __init__(self):
        super(NetworkGroupProxy, self).__init__()
        self.model = models.NetworkGroup
