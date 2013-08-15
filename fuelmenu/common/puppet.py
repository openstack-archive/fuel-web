import subprocess
import sys
import logging
def puppetApply(classname, name=None, params=None):
  '''Runs puppet apply -e "classname {'name': params}" '''
  log = logging
  log.basicConfig(filename='./fuelmenu.log',level=logging.DEBUG)
  log.info("Puppet start")

#name should be a string
#params should be a dict
  command=["puppet","apply","-e","'",classname,"{",'"%s":' % name]
  #Build params
  for key,value in params.items():
     command.extend([key,"=>",'"%s",' % value])
  command.append("}'")
  
  log.debug("%s", ' '.join(command))
  output=""
  try:
    output = subprocess.check_output(command)
  except Exception, e:
    log.error(e)
    if "err:" in output:
      log.error(output)
    return False
  else:
    return True
