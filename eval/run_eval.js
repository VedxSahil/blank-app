// Usage: node eval/run_eval.js <document.txt (pdftotext output)> <gold.json> [rag/index.html]
const fs=require('fs');const [,,txt,gold,page='rag/index.html']=process.argv;
const h=fs.readFileSync(page,'utf8');const s=h.match(/<script>([\s\S]*)<\/script>/)[1];
const els={};global.document={getElementById:id=>els[id]||(els[id]={value:'',style:{},addEventListener(){}})};
global.window={};global.out={};global.amt={value:'1000000'};global.co={};
const f={text:async()=>fs.readFileSync(gold,'utf8')};
eval('(async()=>{'+s+`;chunkPages(fs.readFileSync(txt,'utf8').split('\\f'),'doc.pdf');await runEval(f);const t=els.ev.innerHTML.replace(/<\\/tr>/g,'\\n').replace(/<[^>]+>/g,' | ').replace(/ \\| +\\| /g,' | ');console.log(t)})()`);
