#!/usr/bin/env python3
"""Reprocessamento rastreável; não altera aquisição nem promove produção."""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import ast
import contextlib
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import re
from pathlib import Path
import sys
import time
from unittest.mock import patch
import numpy as np
import pygrib

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / 'classes_MET'
sys.path.insert(0, str(CLASSES))
from runtime_MET import atomic_text

REGIONS = {'SP': (-56,-42,-28,-18), 'RJ': (-46,-36,-27,-17), 'AM': (-65,-55,-7,7)}
LEVELS = (200,500,850,1000)
HEIGHTS = (20,30,40,50,80)
FROZEN = '994ce16c1480b17a62b78e72761307af2000dc47819abbaf48ce042c72023ce0'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_text(path, encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')

def load_functions(name, names, output):
    """Carrega definições de produção, sem executar seu CLI no import."""
    path = CLASSES / name
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)) or isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    namespace = {'__file__': str(path), '__name__': 'phase4_'+path.stem}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'), namespace)
    namespace['dir_save'] = output
    return namespace

class Output:
    def __init__(self, root, date, cycle): self.root, self.date, self.cycle = Path(root), date, cycle
    def directory(self, family):
        p = self.root / family / self.date / self.cycle; p.mkdir(parents=True,exist_ok=True)
        return str(p)+'/'
    def imprime_dirMapas(self): return self.directory('mapasGrib')
    def imprime_dirMatrizes(self): return self.directory('matrizGrib')
    def imprime_dirMatrizesBluesky(self): return self.directory('matrizGrib/bluesky')
    def imprime_dirMatrizesPredi(self): return self.directory('matrizGrib/predi')

def field(grib, name, kind, level):
    messages = grib.select(name=name,typeOfLevel=kind,level=level)
    if not messages: raise ValueError(f'campo ausente: {name}/{kind}/{level}')
    return messages[0]

class RegionalMessage:
    """Cache de recorte para processamento; a validação relê o GRIB original."""
    def __init__(self, source):self.source=source;self.cached=None;self.expected={}
    def __getattr__(self, key):return getattr(self.source,key)
    def _load(self):
        if self.cached is None:self.cached=self.source.data(lat1=-35,lat2=8,lon1=294,lon2=332)
        return self.cached
    def data(self,lat1=None,lat2=None,lon1=None,lon2=None):
        values,lat,lon=self._load()
        rows=np.ones(lat.shape[0],dtype=bool) if lat1 is None else (lat[:,0]>=lat1)&(lat[:,0]<=lat2)
        cols=np.ones(lon.shape[1],dtype=bool) if lon1 is None else (lon[0,:]>=lon1)&(lon[0,:]<=lon2)
        index=np.ix_(np.flatnonzero(rows),np.flatnonzero(cols))
        return values[index],lat[index],lon[index]
    def latlons(self):return self._load()[1:]

class RegionalGRIB:
    def __init__(self,source):self.source=source;self.cache={}
    def select(self,**kwargs):
        key=tuple(sorted(kwargs.items()))
        if key not in self.cache:self.cache[key]=[RegionalMessage(m) for m in self.source.select(**kwargs)]
        return self.cache[key]

def independently_extract(message, bbox):
    if isinstance(message,RegionalMessage) and bbox in message.expected:return message.expected[bbox]
    source=message.source if isinstance(message,RegionalMessage) else message
    left,right,bottom,top = bbox
    data,lat,lon = source.data(lat1=bottom,lat2=top,lon1=left%360,lon2=right%360)
    lat_order = np.argsort(lat[:,0]); lon_order=np.argsort(lon[0,:])
    result = (np.asarray(lat)[np.ix_(lat_order,lon_order)].reshape(-1),
            (np.asarray(lon)[np.ix_(lat_order,lon_order)]-360).reshape(-1),
            np.asarray(data)[np.ix_(lat_order,lon_order)].reshape(-1))
    if isinstance(message,RegionalMessage):message.expected[bbox]=result
    return result

def verify_csv(path, header, columns):
    raw=Path(path).read_bytes()
    if raw.count(b'\n') != raw.count(b'\r\n'):raise ValueError('CSV fora do contrato CRLF')
    with Path(path).open(newline='') as handle: rows=list(csv.reader(handle))
    if not rows or rows[0]!=header: raise ValueError('header divergente: '+str(path))
    got=np.asarray(rows[1:],dtype=float); expected=np.column_stack(columns)
    if got.shape!=expected.shape or not np.isfinite(got).all() or not np.allclose(got,expected,rtol=1e-10,atol=1e-8):
        raise ValueError('valores/grade divergentes: '+str(path))
    if list(map(tuple,got[:,:2])) != sorted(map(tuple,got[:,:2])): raise ValueError('ordem de coordenadas divergente')
    return {'rows':len(got),'header':header,'sha256':sha(path),'bytes':Path(path).stat().st_size}

def assert_identity(grib, sample):
    for m in grib:
        actual=(str(m.dataDate),f'{m.dataTime//100:02d}',int(m.endStep))
        if actual!=(sample['date'],sample['cycle'],sample['forecast']): raise ValueError(f'metadados GRIB divergentes: {actual}')
    grib.seek(0)

def process_sample(sample, destination, regions=REGIONS, maps=False):
    path=Path(sample['path'])
    if sha(path)!=sample['sha256']: raise ValueError('hash da amostra divergente')
    output=Output(destination,sample['date'],sample['cycle'])
    scalar=load_functions('gera_matriz_MET.py',['geraMatriz'],output)
    wind=load_functions('gera_matriz_vento_MET.py',['criaResultanteKnot','criaAngMET','converte_altitude','calcula_hmet','geraMatriz_Vento_Resu','geraMatriz_Vento_UVT_predi'],output)
    files=[]
    when=datetime.strptime(sample['date']+sample['cycle'],'%Y%m%d%H').timetuple()
    with pygrib.open(str(path)) as grib, patch('time.localtime',return_value=when):
        assert_identity(grib,sample)
        grib=RegionalGRIB(grib)
        for region,bbox in regions.items():
            coords=[[bbox[0],bbox[1]],[bbox[2],bbox[3]]]
            scalars=[('temp','Temperature','isobaricInhPa',n) for n in LEVELS]
            scalars += [('temps','Temperature','surface',0),('ps','Surface pressure','surface',0),('prnm','Pressure reduced to MSL','meanSea',0),('umidadeRel','Relative humidity','isobaricInhPa',850)]
            scalars += [('nuvem','Total Cloud Cover','isobaricInhPa',n) for n in (200,500,700)]
            if sample['forecast']:
                scalars += [('chuvaNaoConvec','Total Precipitation','surface',0),('chuvaConvec','Convective precipitation (water)','surface',0)]
            for var,name,kind,level in scalars:
                m=field(grib,name,kind,level); label=level if kind=='isobaricInhPa' else 'surface'
                scalar['geraMatriz']([m],coords,var,region,label)
                ft=int(m.forecastTime)+(6 if var.startswith('chuva') else 0)
                product=Path(output.imprime_dirMatrizes())/f'GFS_{m.iDirectionIncrementInDegrees}_{region}_N{label}_{var}_{sample["cycle"]}_{m.dataDate}_{ft:02}.csv'
                lat,lon,value=independently_extract(m,bbox)
                if var in ('temp','temps'): value=value-273.15
                if var in ('ps','prnm'): value=value/100
                files.append({'path':str(product.relative_to(destination)),**verify_csv(product,['lat','lon',var],[lat,lon,value])})
            for level in (*LEVELS,*HEIGHTS):
                surface=level in HEIGHTS;kind='heightAboveGround' if surface else 'isobaricInhPa'
                u=field(grib,'U component of wind',kind,level);v=field(grib,'V component of wind',kind,level)
                t=field(grib,'Temperature','surface' if surface else kind,0 if surface else level)
                wind['geraMatriz_Vento_Resu']([u],[v],coords,region,level,surface)
                wind['geraMatriz_Vento_UVT_predi']([u],[v],[t],coords,region,level)
                lat,lon,U=independently_extract(u,bbox);V=independently_extract(v,bbox)[2];T=independently_extract(t,bbox)[2]
                height=level*3.28084 if surface else (1-(level/1013.25)**.190284)*145366.45
                angle=np.mod(np.degrees(np.arctan2(-U,-V))+360,360)
                speed=np.hypot(U,V)*1.943
                suffix=f'{region}_N{level}_{sample["cycle"]}_{u.dataDate}_{int(u.forecastTime):02}.csv'
                for family,prefix,header,columns in [
                    ('bluesky','matriz_lat_lon_alt_angMET_VentoResult',['lat','lon','hMET','angMET','vento_resultante'],[lat,lon,np.full_like(U,height),angle,speed]),
                    ('predi','matriz_lat_lon_Vento_UVT_Predi',['lat','lon','vento U','vento V','temp'],[lat,lon,U,V,T])]:
                    product=Path(output.directory('matrizGrib/'+family))/f'GFS_{u.iDirectionIncrementInDegrees}_{prefix}_{suffix}'
                    files.append({'path':str(product.relative_to(destination)),**verify_csv(product,header,columns)})
            if maps:
                module=load_functions('gera_mapas_MET.py',['O','gera_mapas'],output)
                module['gera_mapas']([field(grib,'Temperature','isobaricInhPa',850)],coords,'temp',region,850)
        if maps:
            for product in Path(output.imprime_dirMapas()).glob('*.png'):
                if product.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('PNG invalido')
                files.append({'path':str(product.relative_to(destination)),'sha256':sha(product),'bytes':product.stat().st_size})
    return files

def station_coordinates():
    source=ROOT/'METARpy/python-metar-master/metar/nsd_cccc.txt';result={}
    def coordinate(text):
        parts=text[:-1].split('-');value=int(parts[0])+int(parts[1])/60
        return -value if text[-1] in 'SW' else value
    for line in source.read_text(errors='replace').splitlines():
        parts=line.split(';')
        if len(parts)>8 and parts[0] in ('SBGR','SBGL','SBCT','SBPA','SBCF','SBBE','SBEG','SBRF','SBFZ'):
            result[parts[0]]=(coordinate(parts[7]),coordinate(parts[8]))
    return result

def compare_metar(samples):
    """Diagnóstico observado × GFS, sem confundir pele/850 hPa com ar a 2 m."""
    records=[];coordinates=station_coordinates()
    for sample in samples:
        valid=datetime.strptime(sample['date']+sample['cycle'],'%Y%m%d%H')+timedelta(hours=sample['forecast'])
        with pygrib.open(sample['path']) as grib:
            temperature=RegionalMessage(field(grib,'2 metre temperature','heightAboveGround',2))
            wind_fields=[RegionalMessage(field(grib,name,'heightAboveGround',10)) for name in ('10 metre U wind component','10 metre V wind component')]
            for station,(lat,lon) in coordinates.items():
                choices=[]
                paths=[]
                for shift in (-1,0,1):
                    paths.extend((ROOT/'METARpy'/(valid+timedelta(days=shift)).strftime('%Y%m%d')).glob(station+'*_traduzido.json'))
                for p in sorted(paths):
                    try:
                        record=json.loads(p.read_text())['data'][0]
                        observed=datetime.strptime(record['data'],'%Y%m%d%H%M')
                        delta=abs((observed-valid).total_seconds())
                        if delta<=10800 and isinstance(record.get('temperatura [C]'),(int,float)):choices.append((delta,record,p))
                    except (ValueError,KeyError,TypeError):continue
                if not choices:continue
                delta,record,p=min(choices,key=lambda x:(x[0],str(x[2])))
                point=temperature.data(lat1=lat-.26,lat2=lat+.26,lon1=lon%360-.26,lon2=lon%360+.26)
                distance=(point[1]-lat)**2+(point[2]-lon%360)**2
                model=float(point[0].reshape(-1)[np.argmin(distance)])-273.15
                entry={'station':station,'valid_time':valid.isoformat(),'observation':str(p.relative_to(ROOT)),'difference_minutes':delta/60,'model_2m_C':model,'observed_C':record['temperatura [C]'],'error_C':model-record['temperatura [C]']}
                wind=record.get('vento')
                if isinstance(wind,dict) and isinstance(wind.get('vento [KT]'),(int,float)):
                    components=[]
                    for wind_field in wind_fields:
                        values,lats,lons=wind_field.data(lat1=lat-.26,lat2=lat+.26,lon1=lon%360-.26,lon2=lon%360+.26)
                        index=np.argmin((lats-lat)**2+(lons-lon%360)**2)
                        components.append(float(values.reshape(-1)[index]))
                    speed=float(np.hypot(*components)*1.943)
                    entry.update(model_10m_kt=speed,observed_kt=wind['vento [KT]'],wind_error_kt=speed-wind['vento [KT]'])
                records.append(entry)
    errors=np.array([r['error_C'] for r in records])
    wind_errors=np.array([r['wind_error_kt'] for r in records if 'wind_error_kt' in r])
    return {'wind_pairs':len(wind_errors),'wind_mae_kt':float(np.abs(wind_errors).mean()) if len(wind_errors) else None,'pairs':len(records),'mae_C':float(np.abs(errors).mean()) if len(errors) else None,'bias_C':float(errors.mean()) if len(errors) else None,'max_time_difference_minutes':180,'coordinate_source':'METARpy/python-metar-master/metar/nsd_cccc.txt','records':records}

def process_case(sample, destination, maps=False):
    case_root=destination/'cases'/f"{sample['date']}-{sample['cycle']}-f{sample['forecast']:03}"
    with (destination/(sample['date']+f'-{sample["forecast"]:03}.log')).open('w') as log, contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        items=process_sample(sample,case_root,maps=maps)
    for item in items:item['path']=str((case_root/item['path']).relative_to(destination))
    return items

def run(manifest, destination, maps=False):
    destination=Path(destination).resolve()
    if destination.exists(): raise ValueError('use um diretorio novo; releases anteriores sao imutaveis')
    destination.mkdir(parents=True)
    samples=json.loads(Path(manifest).read_text())['samples']; files=[]; failures=[]
    for sample in samples:
        if not isinstance(sample['date'],str) or not re.fullmatch(r'\d{8}',sample['date']):raise ValueError('data de amostra invalida')
        datetime.strptime(sample['date'],'%Y%m%d')
        if sample['cycle'] not in ('00','06','12','18') or type(sample['forecast']) is not int or sample['forecast'] not in (0,6,12,18):raise ValueError('ciclo/previsao de amostra invalidos')
        if not re.fullmatch(r'[0-9a-f]{64}',sample['sha256']):raise ValueError('SHA-256 invalido')
    identities=[(s['date'],s['cycle'],s['forecast']) for s in samples]
    if len(identities)!=len(set(identities)):raise ValueError('amostras duplicadas no manifesto')
    if sha(ROOT/'goGribV2.sh')!=FROZEN: raise ValueError('downloader congelado alterado')
    with ProcessPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(process_case,sample,destination,maps and sample==samples[0]):sample for sample in samples}
        for future in as_completed(pending):
            sample=pending[future]
            try:files.extend(future.result())
            except Exception as e:failures.append({'sample':sample,'error':str(e)})
            print('sample',sample['date'],sample['forecast'],'failures',len(failures),flush=True)
    dates=sorted({s['date'] for s in samples});forecasts=sorted({s['forecast'] for s in samples})
    complete=len(dates)>=3 and all({s['forecast'] for s in samples if s['date']==d}>={0,6,12,18} for d in dates)
    observations=compare_metar(samples) if not failures else {'pairs':0}
    report={'phase':4,'status':'ok' if not failures and complete and observations['pairs'] else 'incomplete','generated_at':datetime.now(timezone.utc).isoformat(),'samples':samples,'coverage':{'dates':dates,'forecasts':forecasts,'regions':list(REGIONS),'pressure_levels':list(LEVELS),'height_levels':list(HEIGHTS)},'files':files,'failures':failures,'observations':observations,'downloader_sha256':FROZEN,'external_consumers_validated':False,'production_promoted':False}
    write_json(destination/'validation.json',report)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--maps',action='store_true')
    args=parser.parse_args(); report=run(args.manifest,args.output,args.maps)
    print(json.dumps({'status':report['status'],'products':len(report['files']),'pairs':report['observations']['pairs']}))
    return 0 if report['status']=='ok' else 1
if __name__=='__main__':raise SystemExit(main())
