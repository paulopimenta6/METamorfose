import subprocess,concurrent.futures,json,hashlib,re,os
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Amostras de validacao GFS arquivadas, sem alterar goGribV2.sh')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--dates',nargs='+',default=['20221215','20221216','20221217'])
args=parser.parse_args()
from datetime import datetime
for value in args.dates:
 if not re.fullmatch(r"\d{8}",value):parser.error("data invalida: use AAAAMMDD")
 try:datetime.strptime(value,"%Y%m%d")
 except ValueError:parser.error("data de calendario invalida")
D=args.output.resolve();D.mkdir(parents=True,exist_ok=True)
SELECTORS=[(v,f'{n} mb') for n in (200,500,850,1000) for v in ('TMP','UGRD','VGRD')]+[('RH','850 mb')]+[('TCDC',f'{n} mb') for n in (200,500,700)]+[('PRMSL','mean sea level'),('PRES','surface'),('TMP','surface'),('TMP','2 m above ground'),('UGRD','10 m above ground'),('VGRD','10 m above ground')]+[(v,f'{n} m above ground') for n in (20,30,40,50,80) for v in ('UGRD','VGRD')]
def curl(url,path,span=None):
 cmd=['curl','--fail','--location','--http1.1','--silent','--show-error','--retry','2','--max-time','50','--max-filesize','10000000']
 if span:cmd+=['--range',f'{span[0]}-{span[1]}']
 r=subprocess.run(cmd+[url,'-o',str(path)],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-300:])
def run(case):
 date,ft=case;tag=f'{date}-00-f{ft:03}';p=D/(tag+'.grb2');url=f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{date}/00/atmos/gfs.t00z.pgrb2.0p25.f{ft:03}'
 if p.exists() and p.with_suffix('.json').exists():
  cached=json.loads(p.with_suffix('.json').read_text())
  if hashlib.sha256(p.read_bytes()).hexdigest()!=cached['sha256']:raise ValueError('hash do cache divergente')
  cached['path']=str(p)
  return cached
 idx=D/(tag+'.idx');curl(url+'.idx',idx)
 entries=[x.split(':') for x in idx.read_text().splitlines() if x.strip()];selectors=SELECTORS+([('APCP','surface'),('ACPCP','surface')] if ft else [])
 chunks=[];ranges=[]
 for v,l in selectors:
  matches=[i for i,e in enumerate(entries) if e[3:5]==[v,l]]
  if not matches:raise ValueError(f'{tag}: {v}/{l}: {len(matches)} mensagens')
  i=matches[0];start=int(entries[i][1]);end=int(entries[i+1][1])-1;part=D/(tag+f'-{i}.part')
  curl(url,part,(start,end));data=part.read_bytes();part.unlink()
  if len(data)!=end-start+1 or data[:4]!=b'GRIB' or data[-4:]!=b'7777':raise ValueError('Range GRIB invalido')
  chunks.append(data);ranges.append({'field':v,'level':l,'start':start,'end':end,'sha256':hashlib.sha256(data).hexdigest()})
 p.write_bytes(b''.join(chunks));result={'date':date,'cycle':'00','forecast':ft,'path':str(p),'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'ranges':ranges}
 p.with_suffix('.json').write_text(json.dumps(result,indent=2));print(tag,p.stat().st_size,flush=True);return result
cases=[(d,f) for d in args.dates for f in (0,6,12,18)]
results=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(run,c):c for c in cases}
 for future in concurrent.futures.as_completed(futures):
  try:results.append(future.result())
  except Exception as e:errors.append({'case':futures[future],'error':str(e)});print('ERROR',errors[-1],flush=True)
(D/'manifest.json').write_text(json.dumps({'samples':sorted(results,key=lambda x:(x['date'],x['forecast'])),'errors':errors},indent=2));print('DONE',len(results),'ERRORS',len(errors),flush=True)

raise SystemExit(1 if errors else 0)
