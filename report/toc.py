import subprocess,re,json
n=int(re.search(r"Pages:\s+(\d+)",subprocess.run(["pdfinfo","Project_Report.pdf"],capture_output=True,text=True).stdout).group(1))
pages=[subprocess.run(["pdftotext","-f",str(p),"-l",str(p),"-layout","Project_Report.pdf","-"],capture_output=True,text=True).stdout for p in range(1,n+1)]
heads=[l[2:].strip() if l.startswith("##") else l[1:].strip() for l in open("content.txt",encoding="utf8").read().split("\n") if l.startswith("#")]
toc={}
for h in heads:
    for p,t in enumerate(pages,1):
        if p<=2 and not h.startswith("EXEC"): continue
        if p in (3,4) and re.search(r"TABLE OF CONTENTS|\.{5}",t): continue
        if re.search(r"^\s*"+re.escape(h)+r"\s*$",t,re.M): toc[h]=p;break
print(n,len(heads),len(toc))
json.dump(toc,open("toc.json","w"))
