from nailgun.db.sqlalchemy import models
from nailgun.network.proxy import BaseProxy


class IPAddrProxy(BaseProxy):

    def __init__(self):
        super(IPAddrProxy, self).__init__()
        self.model = models.IPAddr


class IPAddrRangeProxy(BaseProxy):

    def __init__(self):
        super(IPAddrRangeProxy, self).__init__()
        self.model = models.IPAddrRange
