import yaml
import ConfigParser
import collections
import os
try:
  from collections import OrderedDict
except:
  # python 2.6 or earlier use backport
  from ordereddict import OrderedDict

class NailyFacterSettings():
  def __init__(self):
     self.defaultsfile="/etc/naily.facts.default"
     self.settingsfile="/etc/naily.facts"

  def read(self, infile='/etc/naily.facts.default'):
     config = OrderedDict()

     if os.path.isfile(infile):
       fd=open(infile, 'r')
       lines = fd.readlines()
       for line in lines:
         key = line.split('=')[0]
         value = line.split('=')[1]
         config[key]=value
         fd.close()
     return config

  def write(self, newvalues, prefix='mnbs_', 
      defaultsfile=None, outfn=None):
     #Read outfn if it exists
     if not defaultsfile:
       defaultsfile=self.defaultsfile
     if not outfn:
       outfn = self.settingsfile
     config=OrderedDict()
     if defaultsfile is not None:
       config.update(self.read(defaultsfile))
     if os.path.isfile(outfn):
       config.update(self.read(outfn))

     #Insert newvalues with prefix into config
     for key in newvalues.keys():
       config["%s%s" % (prefix,key)]="%s\n" %newvalues[key]
     #Write out new file
     outfile = open(outfn, 'w')
     for key in config.keys():
       outfile.write("%s=%s" % (key, config[key]))
     outfile.close()
     return True
