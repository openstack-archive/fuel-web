import re


def replaceInFile(filename, orig, new):
    lines = open(filename).readlines()
    for lineno, line in enumerate(lines):
        lines[lineno] = re.sub(orig, new, line)
    with open(filename, 'w') as f:
        f.write("".join(lines))

