import re

<<<<<<< HEAD

def replaceInFile(filename, orig, new):
    lines = open(filename).readlines()
    for lineno, line in enumerate(lines):
        lines[lineno] = re.sub(orig, new, line)
    f = open(filename, 'w')
    f.write("".join(lines))
    f.flush()
    f.close()
=======
def replaceInFile(filename, orig, new):
   lines=open(filename).readlines()
   for lineno,line in enumerate(lines):
     lines[lineno]=re.sub(orig, new, line)
   f=open(filename, 'w')
   print ''.join(lines)
   f.write("".join(lines))
   f.flush()
   f.close()


>>>>>>> 265265e6e18510422b50eba78bac1483d41e5052
