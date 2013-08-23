import netaddr

def inSameSubnet(ip1,ip2,netmask_or_cidr):
   try:
     cidr1=netaddr.IPNetwork("%s/%s" % (ip1,netmask_or_cidr))
     cidr2=netaddr.IPNetwork("%s/%s" % (ip2,netmask_or_cidr))
     return cidr1 == cidr2 
   except:
     return False

def getCidr(ip, netmask):
   try:
     ipn = netaddr.IPNetwork("%s/%s" % (ip, netmask))
     return str(ipn.cidr)
   except:
     return False

def getCidrSize(cidr):
   try:
     ipn = netaddr.IPNetwork(cidr)
     return ipn.size
   except:
     return False

