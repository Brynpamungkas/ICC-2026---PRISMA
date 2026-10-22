"""Tes emas Tabel A-4. FROZEN: tidak boleh diubah AI agar lulus. Hapus 'skip' saat pipeline selesai."""
import pytest

pytestmark = pytest.mark.skip(reason="menunggu orchestrator (M2.8)")


def test_contoh1_tanya():
    from backend.app.orchestrator import run_question
    d = run_question("Provinsi mana yang paling miskin?")
    assert d.decision == "TANYA" and len(d.evidence) == 2


def test_contoh2_jawab():
    from backend.app.orchestrator import run_question
    d = run_question("Berapa total penduduk miskin di Pulau Jawa?")
    assert d.decision == "JAWAB"


def test_contoh3_tahan_t1():
    from backend.app.orchestrator import run_question
    d = run_question("Berapa IPM Jawa Barat?")
    assert d.decision == "TAHAN" and d.reason_code == "T1"
