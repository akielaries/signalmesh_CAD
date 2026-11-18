import re, glob, sys, os, pickle
idx={}
for f in glob.glob('/usr/share/kicad/symbols/*.kicad_sym'):
    lib=os.path.basename(f)[:-10]
    for m in re.finditer(r'^\t\(symbol "([^"]+)"', open(f).read(), re.M):
        idx.setdefault(m.group(1),[]).append(lib)
pickle.dump(idx,open(sys.argv[1],'wb'))
