"""SYNTHETIC M5 review-provenance tests, not actual human annotation evidence."""
import csv
import hashlib
import json

import pytest

from scripts import dataset_tools as dt
from scripts import eval_protocol as ep


def fixture_review(tmp_path, monkeypatch):
    monkeypatch.setattr(ep,'ROOT',tmp_path)
    paths={}
    rows=[]
    for name,status in [('final','VERIFIED'),('draft','DRAFT')]:
        p=tmp_path/(name+'.csv')
        row=dict.fromkeys(dt.L_COLS,'')
        row.update(question_id='SYN_Q',annotator_id='SYN_FINAL',decision_reference='JAWAB',
                   question_group='TAK_AMBIGU',interpretation_id='I1',indicator_code='SYN_I',
                   reference_sql='SELECT 1',verification_status=status)
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=dt.L_COLS)
            w.writeheader()
            w.writerow(row)
        paths['labels_final' if name=='final' else 'draft_llm']=p
        rows.append(row)
    for name in ['reference_answers','database','catalog_version','questions']:
        p=tmp_path/(name+'.json')
        p.write_text('SYNTHETIC '+name)
        paths[name]=p
    record={'method':'llm_draft_human_review','question_ids':['SYN_Q'],
        'approval':{'reporter':'SYN_REVIEWER','statement':'SYNTHETIC reviewed draft',
                    'human_approval_reported':True,'recorded_at':'2099-01-01T00:00:00+00:00'},
        'kappa':None,'independent_initial_labels_claimed':False,
        'artifacts':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()}}
    path=tmp_path/'review.json'
    path.write_text(json.dumps(record))
    return path,record


def test_m5_review_is_reported_as_llm_review_without_fictitious_kappa(tmp_path,monkeypatch):
    path,_=fixture_review(tmp_path,monkeypatch)
    result=ep.validate_annotation_evidence({'annotation_method':'llm_draft_human_review','annotation_review':str(path)}, {'SYN_Q'})
    assert result['method']=='llm_draft_human_review' and result['kappa'] is None
    assert not result['paper_independent_annotation_claimed']


def test_m5_mode_does_not_accept_missing_approval(tmp_path,monkeypatch):
    path,record=fixture_review(tmp_path,monkeypatch)
    record['approval']['human_approval_reported']=False
    path.write_text(json.dumps(record))
    with pytest.raises(SystemExit,match='persetujuan'):
        ep.validate_annotation_evidence({'annotation_method':'llm_draft_human_review','annotation_review':str(path)}, {'SYN_Q'})


def test_changed_final_labels_require_new_review_hash(tmp_path,monkeypatch):
    path,_=fixture_review(tmp_path,monkeypatch)
    with (tmp_path/'final.csv').open('a') as f:
        f.write('changed\n')
    with pytest.raises(SystemExit,match='hash'):
        ep.validate_annotation_evidence({'annotation_method':'llm_draft_human_review','annotation_review':str(path)}, {'SYN_Q'})


def test_unreviewed_question_is_not_added_silently(tmp_path,monkeypatch):
    path,_=fixture_review(tmp_path,monkeypatch)
    with pytest.raises(SystemExit,match='cakupan'):
        ep.validate_annotation_evidence({'annotation_method':'llm_draft_human_review','annotation_review':str(path)}, {'SYN_OTHER'})


def test_two_independent_humans_mode_is_preserved(tmp_path):
    with pytest.raises(SystemExit,match='dua penilai'):
        ep.validate_annotation_evidence({'annotation_method':'two_independent_humans','annotation_protocol':str(tmp_path/'missing')},{'SYN_Q'})


def test_unknown_method_does_not_fall_back_to_llm_review():
    with pytest.raises(SystemExit,match='Metode anotasi'):
        ep.validate_annotation_evidence({'annotation_method':'unknown'},{'SYN_Q'})
