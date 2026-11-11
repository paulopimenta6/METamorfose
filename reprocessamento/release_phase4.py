#!/usr/bin/env python3
"""Release imutável com verificação de hashes, promoção e rollback atômicos."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,data):
    path=Path(path); fd,name=tempfile.mkstemp(prefix='.release-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def inventory(root):
    result={}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():raise ValueError('release nao aceita symlink: '+str(p))
        if p.is_file() and p.relative_to(root).as_posix()!='release.json':result[str(p.relative_to(root))]=digest(p)
    return result

def build(source, validation, destination):
    source,validation,destination=Path(source),Path(validation),Path(destination)
    if destination.exists():raise ValueError('release existente e imutavel')
    if digest(source/'goGribV2.sh')!='994ce16c1480b17a62b78e72761307af2000dc47819abbaf48ce042c72023ce0':raise ValueError('downloader congelado divergente')
    report=json.loads((validation/'validation.json').read_text())
    if report['status']!='ok' or report.get('failures'):raise ValueError('validacao incompleta; nao criar release aprovavel')
    for item in report['files']:
        p=(validation/item['path']).resolve()
        if not p.is_relative_to(validation.resolve()) or digest(p)!=item['sha256']:raise ValueError('produto alterado/fora da raiz')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.candidate-',dir=destination.parent))
    try:
        for family in ('classes_MET','bash','environment','METARpy'):
            base=source/family
            for p in base.rglob('*'):
                if p.is_file() and (p.suffix in ('.py','.sh','.conf') or p.name in ('setup.cfg','README.md')):
                    if '__pycache__' in p.parts or 'build' in p.parts or 'python-metar-master' in p.parts:continue
                    relative=p.relative_to(source)
                    target=temporary/'code'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for name in ('goGribV2.sh','remove_GRIBS_antigos.sh','requirements.txt','requirements-dev.txt'):
            shutil.copy2(source/name,temporary/'code'/name)
        tools=temporary/'code/reprocessamento';tools.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/'reprocessamento/release_phase4.py',tools/'release_phase4.py')
        for item in report['files']:
            relative=Path(item['path'])
            if relative.parts[0]=='cases':relative=Path(*relative.parts[2:])
            target=temporary/'products'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and digest(target)!=item['sha256']:raise ValueError('colisao de produtos entre previsoes')
            shutil.copy2(validation/item['path'],target)
        shutil.copy2(validation/'validation.json',temporary/'validation.json')
        manifest={'created_at':datetime.now(timezone.utc).isoformat(),'validation_sha256':digest(temporary/'validation.json'),'files':inventory(temporary),'consumer_acceptance_required':True}
        dump(temporary/'release.json',manifest);os.rename(temporary,destination)
    except BaseException:
        shutil.rmtree(temporary,ignore_errors=True);raise
    return verify(destination)

def verify(candidate):
    candidate=Path(candidate);manifest=json.loads((candidate/'release.json').read_text())
    if inventory(candidate)!=manifest['files']:raise ValueError('inventario/hash da release divergente')
    if digest(candidate/'validation.json')!=manifest['validation_sha256']:raise ValueError('relatorio alterado')
    report=json.loads((candidate/'validation.json').read_text())
    if report.get('status')!='ok' or report.get('failures'):raise ValueError('relatorio nao aprovado')
    return manifest

@contextmanager
def locked(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'.deployment.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield root

def current(root):
    p=Path(root)/'current'
    if p.exists() and not p.is_symlink():raise ValueError('current existente nao e symlink; nada sera sobrescrito')
    return os.readlink(p) if p.is_symlink() else None

def switch(root,target,action):
    previous=current(root)
    if previous==target:return {'action':'noop','current':target,'previous':previous}
    if previous is not None:
        prior=root/('.previous-'+uuid.uuid4().hex)
        try:prior.symlink_to(previous);os.replace(prior,root/'previous')
        finally:prior.unlink(missing_ok=True)
    name=root/('.current-'+uuid.uuid4().hex)
    try:
        name.symlink_to(target);os.replace(name,root/'current')
    finally:name.unlink(missing_ok=True)
    event={'action':action,'previous':previous,'current':target,'at':datetime.now(timezone.utc).isoformat()}
    with (root/'history.jsonl').open('a') as stream:stream.write(json.dumps(event)+'\n');stream.flush();os.fsync(stream.fileno())
    return event

def promote(candidate,root,acceptance=None,rehearsal=False):
    candidate=Path(candidate).resolve();verify(candidate)
    if not rehearsal:
        if acceptance is None:raise ValueError('aceite real dos consumidores e obrigatorio')
        approved=json.loads(Path(acceptance).read_text())
        if approved.get('release_sha256')!=digest(candidate/'release.json') or approved.get('approved') is not True or set(approved.get('consumers',[]))!={'BlueSky','preditor','planilhas'}:
            raise ValueError('aceite nao corresponde a release/consumidores')
    with locked(root) as root:
        if not rehearsal and (root/'REHEARSAL').exists():raise ValueError('destino de ensaio nao e producao')
        if rehearsal:
            if (root/'current').exists() and not (root/'REHEARSAL').exists():raise ValueError('nao executar ensaio sobre producao')
            (root/'REHEARSAL').touch()
        current(root)  # Validate before copying.
        releases=root/'releases';releases.mkdir(exist_ok=True)
        tag=digest(candidate/'release.json')[:20];target=releases/tag
        if not target.exists():
            temporary=Path(tempfile.mkdtemp(prefix='.release-',dir=releases))
            try:shutil.copytree(candidate,temporary,dirs_exist_ok=True);verify(temporary);os.rename(temporary,target)
            finally:
                if temporary.exists():shutil.rmtree(temporary)
        verify(target)
        return switch(root,'releases/'+tag,'rehearsal' if rehearsal else 'promote')

def rollback(root):
    with locked(root) as root:
        previous=os.readlink(root/'previous') if (root/'previous').is_symlink() else None
        if previous is None:raise ValueError('sem release anterior para restaurar')
        target=(root/previous).resolve()
        if not target.is_relative_to((root/'releases').resolve()):raise ValueError('rollback fora das releases')
        verify(target)
        return switch(root,previous,'rollback')

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    build_p=sub.add_parser('build');build_p.add_argument('--validation',type=Path,required=True);build_p.add_argument('--output',type=Path,required=True)
    for command in ('verify','promote'):
        p=sub.add_parser(command);p.add_argument('candidate',type=Path)
        if command=='promote':p.add_argument('--target',type=Path,required=True);p.add_argument('--acceptance',type=Path);p.add_argument('--rehearsal',action='store_true')
    p=sub.add_parser('rollback');p.add_argument('--target',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='build':result=build(ROOT,args.validation,args.output)
    elif args.command=='verify':result=verify(args.candidate)
    elif args.command=='promote':result=promote(args.candidate,args.target,args.acceptance,args.rehearsal)
    else:result=rollback(args.target)
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
