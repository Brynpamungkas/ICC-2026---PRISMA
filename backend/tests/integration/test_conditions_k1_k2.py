"""K1/K2 (D10 C2, keputusan tim K-08). DB hasil ETL data BPS asli + klien TIRUAN; bukan bukti kinerja model."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import etl  # noqa: E402

from backend.app.conditions import parse_k1_output, run_condition, run_k1, run_k2  # noqa: E402
from backend.app.llm.mock import MockLlmClient  # noqa: E402
from backend.app.orchestrator import run_question_with_log  # noqa: E402

RANK = ("SELECT p.nama AS wilayah, n.nilai AS nilai FROM nilai_indikator n JOIN provinsi p ON p.kode=n.kode_provinsi "
        "WHERE n.kode_indikator=:indikator AND n.periode=:periode ORDER BY n.nilai DESC LIMIT 1")
SUM6 = ("SELECT SUM(n.nilai) AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode "
        "AND n.kode_provinsi IN (:wilayah_0,:wilayah_1,:wilayah_2,:wilayah_3,:wilayah_4,:wilayah_5)")
ONE = ("SELECT n.nilai AS nilai FROM nilai_indikator n WHERE n.kode_indikator=:indikator AND n.periode=:periode "
       "AND n.kode_provinsi = :wilayah_0")
TAU = {"%": 0.0, "ribu jiwa": 0.0, "orang": 0.0}


class Counting(MockLlmClient):
    calls = 0

    def generate(self, prompt, n, system=None):
        type(self).calls += 1
        self.last_system = system
        return super().generate(prompt, n)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    d = tmp_path_factory.mktemp("db")
    assert etl.build(False, etl.RAW_DIR / "manifest.yaml", d / "p.sqlite", d / "r.json") == 0
    return d / "p.sqlite"


def test_parse_k1_output():
    code, sql = parse_k1_output("INDIKATOR: `KMS_PERSEN`\n```sql\nSELECT 1\n```", {"KMS_PERSEN"})
    assert code == "KMS_PERSEN" and sql == "SELECT 1"
    assert parse_k1_output("INDIKATOR: NGAWUR\nSELECT 1", {"KMS_PERSEN"})[0] is None


def test_k2_asks_before_execution_when_catalog_has_two(db):
    Counting.calls = 0
    d, rec = run_k2("Provinsi mana yang paling miskin?", llm=Counting([RANK]), db_path=db, tau=TAU)
    assert d.decision == "TANYA" and d.evidence == [] and Counting.calls == 0
    assert rec.mode == "K2" and rec.k == ["KMS_PERSEN", "KMS_JUMLAH"] and rec.skeletons == []


def test_k2_single_candidate_equals_k3(db):
    d2, rec2 = run_k2("TPT Bali", llm=MockLlmClient([ONE]), db_path=db, tau=TAU)
    d3, _ = run_question_with_log("TPT Bali", llm=MockLlmClient([ONE]), db_path=db, tau=TAU)
    assert rec2.mode == "K2" and d2.model_dump() == d3.model_dump() and d2.decision == "JAWAB"


def test_k1_model_picks_indicator_and_answers_without_clarifying(db):
    llm = Counting(["INDIKATOR: KMS_PERSEN\n" + RANK])
    d, rec = run_k1("Provinsi mana yang paling miskin?", llm=llm, db_path=db)
    assert llm.last_system is not None and "INDICATOR_LIST" in llm.last_system
    assert d.decision == "JAWAB" and d.answer.candidate.code == "KMS_PERSEN"
    assert d.period_used == "2026-03" and d.answer.result.rows == [["Papua Tengah", 30.41]]   # periode terbaru indikator pilihan
    assert rec.mode == "K1" and rec.k == ["KMS_PERSEN", "KMS_JUMLAH"] and rec.votes[0].votes == 64


def test_k1_unknown_code_is_t4(db):
    d, _ = run_k1("Provinsi mana yang paling miskin?", llm=MockLlmClient(["INDIKATOR: NGAWUR\n" + RANK]), db_path=db)
    assert d.decision == "TAHAN" and d.reason_code == "T4"


def test_k1_gate_on_chosen_indicator(db):
    d, _ = run_k1("total persentase penduduk miskin di Pulau Jawa", llm=MockLlmClient(["INDIKATOR: KMS_PERSEN\n" + SUM6]),
                  db_path=db)
    assert d.decision == "TAHAN" and d.reason_code == "T3"


def test_run_condition_dispatch(db):
    d, rec = run_condition("K3", "TPT Bali", llm=MockLlmClient([ONE]), db_path=db, tau=TAU)
    assert rec.mode == "K3" and d.decision == "JAWAB"
    with pytest.raises(ValueError):
        run_condition("K9", "x")


def test_k2_delegated_trace_keeps_actual_condition(db, tmp_path):
    """A K2 run delegated to K3's single-candidate pipeline must not become K3 evidence."""
    import json
    from backend.app.config import load_config
    cfg = load_config()
    cfg['logging']['trace_dir'] = str(tmp_path)
    _, rec = run_k2('TPT Bali', llm=MockLlmClient([ONE]), db_path=db, tau=TAU, config=cfg)
    trace = [json.loads(line) for line in (tmp_path / (rec.run_id + '.trace.jsonl')).read_text().splitlines()]
    assert trace[0]['data']['mode'] == 'K2'
    assert trace[-1]['data']['record']['mode'] == 'K2'


@pytest.mark.parametrize('n',[8,64])
def test_configured_sample_counts_are_preserved_for_cpu_and_baseline_mock(db,n):
    """Mock sampling proves configuration is respected, not real CPU/GPU inference quality."""
    from backend.app.config import load_config
    cfg=load_config('config/config.yaml')
    cfg['sampling']['n_samples']=n
    d1,r1=run_k1('Provinsi mana yang paling miskin?',llm=MockLlmClient(['INDIKATOR: KMS_PERSEN\n'+RANK]),
                 db_path=db,config=cfg)
    d3,r3=run_question_with_log('Provinsi mana yang paling miskin?',llm=MockLlmClient([RANK]),
                              db_path=db,config=cfg,tau=TAU)
    assert d1.decision == 'JAWAB' and d3.decision == 'TANYA'
    assert len(r1.skeletons) == len(r3.skeletons) == n
    assert all(v.votes == n for v in r1.votes+r3.votes)
    assert cfg['sampling']['n_samples'] == n
