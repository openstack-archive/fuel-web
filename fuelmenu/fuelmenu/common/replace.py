import re


def replaceInFile(filename, orig, new):
    lines = open(filename).readlines()
    for lineno, line in enumerate(lines):
        lines[lineno] = re.sub(orig, new, line)
    f = open(filename, 'w')
    f.write("".join(lines))
    f.flush()
    f.close()
