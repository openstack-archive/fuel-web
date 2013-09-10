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

def getNetwork(ip, netmask):
   #Return a list excluding ip and broadcast IPs
   try:
     ipn = netaddr.IPNetwork("%s/%s" % (ip, netmask))
     ipn_list = list(ipn)
     #Drop broadcast and network ip
     ipn_list = ipn_list[1:-1]
     #Drop ip
     ipn_list[:] = [value for value in ipn_list if str(value) != ip]
     
     return ipn_list
   except:
     return False

