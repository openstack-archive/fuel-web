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
     pass
  def read(self, infile='naily.facts.default'):
     config = OrderedDict()
     fd=open(infile, 'r')
     lines = fd.readlines()
     print "asdf"
     print lines
     for line in lines:
       key = line.split('=')[0]
       value = line.split('=')[1]
       config[key]=value
       print key,value
     print infile,config
     fd.close()
     return config

  def write(self, newvalues, prefix='mnbs_', defaultsfile='naily.facts.default', outfn='naily.facts'):
     print outfn
     print os.path.isfile(outfn)
     print defaultsfile
     #Read outfn if it exists
     if os.path.isfile(outfn):
       config=self.read(outfn)
     elif defaultsfile is not None:
     #Get default config or start new
       config=self.read(defaultsfile)
     else:
       config=OrderedDict()
     #Insert newvalues with prefix into config
     for key in newvalues.keys():
       config["%s%s" % (prefix,key)]="%s\n" %newvalues[key]
     #Write out new file
     outfile = open(outfn, 'w')
     for key in config.keys():
       outfile.write("%s=%s" % (key, config[key]))
     outfile.close()
     print config
     return True
