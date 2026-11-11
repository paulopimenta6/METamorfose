"""Aceitação local da fase 4: releases reais não são promovidas pelos testes."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reprocessamento'))
import release_phase4 as release
import phase4

@pytest.fixture
def candidate(tmp_path):
    def make(name='one'):
        p=tmp_path/name;p.mkdir()
        (p/'data.csv').write_text('lat,lon,temp\n0,0,20\n')
        (p/'version.txt').write_text(name)
        (p/'validation.json').write_text(json.dumps({'status':'ok','failures':[]}))
        manifest={'validation_sha256':release.digest(p/'validation.json'),'files':release.inventory(p)}
        (p/'release.json').write_text(json.dumps(manifest))
        return p
    return make

def test_reject_changed_product(candidate):
    p=candidate();(p/'data.csv').write_text('broken')
    with pytest.raises(ValueError):release.verify(p)

def test_reject_extra_file(candidate):
    p=candidate();(p/'extra').write_text('extra')
    with pytest.raises(ValueError):release.verify(p)

def test_reject_symlink(candidate,tmp_path):
    p=candidate();(p/'link').symlink_to(tmp_path/'outside')
    with pytest.raises(ValueError):release.verify(p)

def test_production_requires_acceptance_before_mutation(candidate,tmp_path):
    p=candidate();target=tmp_path/'production'
    with pytest.raises(ValueError,match='aceite'):release.promote(p,target)
    assert not target.exists()

def test_acceptance_bound_to_exact_release(candidate,tmp_path):
    p=candidate();accept=tmp_path/'accept.json';accept.write_text(json.dumps({'approved':True,'release_sha256':'wrong','consumers':['BlueSky','preditor','planilhas']}))
    with pytest.raises(ValueError):release.promote(p,tmp_path/'production',accept)

def test_promotion_and_rollback_preserve_both_releases(candidate,tmp_path):
    a=candidate('a');b=candidate('b');target=tmp_path/'deployment'
    release.promote(a,target,rehearsal=True);first=(target/'current').resolve()
    release.promote(b,target,rehearsal=True);second=(target/'current').resolve()
    assert first!=second
    release.rollback(target)
    assert (target/'current').resolve()==first
    assert first.is_dir() and second.is_dir()

def test_failed_verification_keeps_current(candidate,tmp_path):
    a=candidate('a');b=candidate('b');target=tmp_path/'deployment'
    release.promote(a,target,rehearsal=True);before=(target/'current').resolve()
    (b/'data.csv').write_text('corrupt')
    with pytest.raises(ValueError):release.promote(b,target,rehearsal=True)
    assert (target/'current').resolve()==before

def test_first_release_has_no_rollback(candidate,tmp_path):
    p=candidate();target=tmp_path/'deployment';release.promote(p,target,rehearsal=True)
    with pytest.raises(ValueError,match='anterior'):release.rollback(target)

def test_reject_real_directory_as_current(candidate,tmp_path):
    target=tmp_path/'deployment';(target/'current').mkdir(parents=True)
    with pytest.raises(ValueError):release.promote(candidate(),target,rehearsal=True)
    assert (target/'current').is_dir()

def test_validate_csv_rejects_bad_header(tmp_path):
    p=tmp_path/'p.csv';p.write_bytes(b'wrong\r\n1\r\n')
    with pytest.raises(ValueError):phase4.verify_csv(p,['lat','lon','temp'],[[0],[0],[20]])

def test_validate_csv_rejects_wrong_value(tmp_path):
    p=tmp_path/'p.csv';p.write_bytes(b'lat,lon,temp\r\n0,0,99\r\n')
    with pytest.raises(ValueError):phase4.verify_csv(p,['lat','lon','temp'],[[0],[0],[20]])

def test_refuse_reused_run_directory(tmp_path):
    with pytest.raises(ValueError,match='novo'):phase4.run(tmp_path/'absent.json',tmp_path)

def test_bundled_station_coordinates_are_used():
    stations=phase4.station_coordinates()
    assert len(stations)==9
    assert stations['SBGR'][0]==pytest.approx(-23-26/60)

def test_reject_sample_metadata_masquerading_as_future():
    class Message:
        dataDate=20221215;dataTime=0;endStep=0
    class Source:
        def __iter__(self):return iter([Message()])
        def seek(self,n):pass
    with pytest.raises(ValueError):phase4.assert_identity(Source(),{'date':'20221215','cycle':'00','forecast':6})


def test_validate_csv_accepts_contract_and_rejects_lf(tmp_path):
    p=tmp_path/'p.csv';p.write_bytes(b'lat,lon,temp\r\n0,0,20\r\n')
    assert phase4.verify_csv(p,['lat','lon','temp'],[[0],[0],[20]])['rows']==1
    p.write_bytes(b'lat,lon,temp\n0,0,20\n')
    with pytest.raises(ValueError,match='CRLF'):phase4.verify_csv(p,['lat','lon','temp'],[[0],[0],[20]])

def test_repromoting_same_release_is_noop(candidate,tmp_path):
    a=candidate('a');b=candidate('b');target=tmp_path/'deployment'
    release.promote(a,target,rehearsal=True);first=(target/'current').resolve()
    release.promote(b,target,rehearsal=True)
    assert release.promote(b,target,rehearsal=True)['action']=='noop'
    release.rollback(target)
    assert (target/'current').resolve()==first


def test_regional_cache_matches_native_subset():
    import numpy as np
    class Source:
        calls=0
        def data(self,**kwargs):
            self.calls+=1
            lon,lat=np.meshgrid([294.,295.,296.],[2.,1.,0.])
            return lat*10+lon,lat,lon
    source=Source();message=phase4.RegionalMessage(source)
    values,lat,lon=message.data(lat1=0,lat2=1,lon1=295,lon2=296)
    assert values.tolist()==[[305.,306.],[295.,296.]]
    assert lat[:,0].tolist()==[1.,0.]
    message.latlons();assert source.calls==1


def test_metar_comparison_includes_previous_day(tmp_path,monkeypatch):
    import numpy as np
    from contextlib import nullcontext
    monkeypatch.setattr(phase4,'ROOT',tmp_path)
    monkeypatch.setattr(phase4,'station_coordinates',lambda:{'SBGR':(0,0)})
    class Temperature:
        def data(self,**kwargs):return np.array([[293.15]]),np.array([[0.]]),np.array([[0.]])
    monkeypatch.setattr(phase4,'field',lambda *args:Temperature())
    monkeypatch.setattr(phase4.pygrib,'open',lambda *args:nullcontext(object()))
    for day,hour in [('20221215','2300'),('20221216','0300')]:
        p=tmp_path/'METARpy'/day;p.mkdir(parents=True)
        (p/f'SBGR{day}{hour}_traduzido.json').write_text(json.dumps({'data':[{'data':day+hour,'temperatura [C]':20}]}))
    result=phase4.compare_metar([{'path':'fake','date':'20221216','cycle':'00','forecast':0}])
    assert result['pairs']==1
    assert result['records'][0]['difference_minutes']==60
    assert '202212152300' in result['records'][0]['observation']

@pytest.fixture
def build_fixture(tmp_path):
    import shutil
    source=tmp_path/'source'
    for family in ('classes_MET','bash','environment','METARpy','reprocessamento'):(source/family).mkdir(parents=True)
    (source/'classes_MET/dirty.py').write_text('VALUE = "uncommitted snapshot"\n')
    (source/'environment/path.conf').write_text('original configuration\n')
    for name in ('goGribV2.sh','remove_GRIBS_antigos.sh','requirements.txt','requirements-dev.txt','reprocessamento/release_phase4.py'):
        shutil.copy2(ROOT/name,source/name)
    validation=tmp_path/'validation';(validation/'cases/one/matrizGrib/day/cycle').mkdir(parents=True)
    product=validation/'cases/one/matrizGrib/day/cycle/data.csv';product.write_bytes(b'lat,lon,temp\r\n0,0,20\r\n')
    report={'status':'ok','failures':[],'files':[{'path':str(product.relative_to(validation)),'sha256':release.digest(product)}]}
    (validation/'validation.json').write_text(json.dumps(report))
    return source,validation,report

def test_build_captures_working_code_and_operational_paths(build_fixture,tmp_path):
    source,validation,report=build_fixture;destination=tmp_path/'candidate'
    release.build(source,validation,destination)
    assert (destination/'code/classes_MET/dirty.py').read_text()=='VALUE = "uncommitted snapshot"\n'
    assert (destination/'products/matrizGrib/day/cycle/data.csv').is_file()
    assert (destination/'code/reprocessamento/release_phase4.py').is_file()
    release.verify(destination)
    with pytest.raises(ValueError,match='imutavel'):release.build(source,validation,destination)

def test_build_rejects_changed_frozen_downloader(build_fixture,tmp_path):
    source,validation,report=build_fixture;(source/'goGribV2.sh').write_text('changed')
    with pytest.raises(ValueError,match='downloader'):release.build(source,validation,tmp_path/'candidate')

def test_build_rejects_path_traversal(build_fixture,tmp_path):
    source,validation,report=build_fixture;outside=tmp_path/'outside.csv';outside.write_text('outside')
    report['files']=[{'path':'../outside.csv','sha256':release.digest(outside)}]
    (validation/'validation.json').write_text(json.dumps(report))
    with pytest.raises(ValueError):release.build(source,validation,tmp_path/'candidate')
    assert not (tmp_path/'candidate').exists()

def test_rollback_survives_interrupted_history(candidate,tmp_path):
    a=candidate('a');b=candidate('b');target=tmp_path/'deployment'
    release.promote(a,target,rehearsal=True);first=(target/'current').resolve()
    (target/'history.jsonl').unlink();(target/'history.jsonl').mkdir()
    with pytest.raises(IsADirectoryError):release.promote(b,target,rehearsal=True)
    (target/'history.jsonl').rmdir()
    release.rollback(target)
    assert (target/'current').resolve()==first


def test_manifest_date_cannot_escape_run_directory(tmp_path):
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'samples':[{'date':'../../escape','cycle':'00','forecast':0,'sha256':'0'*64,'path':'missing'}]}))
    with pytest.raises(ValueError,match='data'):phase4.run(manifest,tmp_path/'run')
    assert not (tmp_path/'escape').exists()
