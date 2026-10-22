"""Load reviewed dev examples only; never promote the team's draft implicitly."""
from __future__ import annotations

import csv
import json

from backend.app.config import ROOT, ConfigError


def load_examples(config: dict, *, catalog=None) -> list[dict]:
    selected = config["prompt"].get("examples_file")
    if selected is None:
        return []
    try:
        data = json.loads((ROOT / selected).read_text(encoding="utf-8"))
        if not isinstance(data.get("ditinjau_oleh"), str) or not data["ditinjau_oleh"].strip():
            raise ConfigError("Contoh dev belum ditinjau manusia; jangan mengaktifkan draf sebagai reviewed dev.")
        split = json.loads((ROOT / data["split"]).read_text(encoding="utf-8"))
        dev, test = split["dev"], split["test"]
        if len(dev) != len(set(dev)) or len(test) != len(set(test)) or set(dev) & set(test):
            raise ConfigError("ID split contoh dev tidak sah.")
        k = config["prompt"]["few_shot_k"]
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ConfigError("few_shot_k harus bilangan bulat tidak negatif.")
        examples = data["contoh"][:k]
        if any(e["id"] not in dev or e["id"] in test for e in examples):
            raise ConfigError("Contoh prompt harus berasal dari dev, tanpa ID test.")
        from backend.app.llm.prompt import extraction_context
        from backend.app.steps.s1_extract import extract
        from backend.app.sqlguard.validator import validate_sql
        questions_path = (ROOT / selected).parent / "pertanyaan.csv"
        with questions_path.open(encoding="utf-8-sig", newline="") as stream:
            questions = {q["question_id"]: q["question_text"] for q in csv.DictReader(stream)
                         if q["question_id"] in {e["id"] for e in examples}}
        out = []
        for e in examples:
            if questions.get(e["id"]) != e["question"]:
                raise ConfigError("Teks contoh berbeda dari soal dev yang dirujuk.")
            ext = extract(e["question"], catalog=catalog, config=config)
            valid, reason = validate_sql(e["sql"], region_count=len(ext.regions),
                                        shape=(ext.operation, ext.rank_direction, ext.top_n))
            if not valid:
                raise ConfigError(f"SQL contoh dev tidak sah: {reason}")
            out.append({**e, "context": extraction_context(ext)})
        return out
    except ConfigError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ConfigError("Berkas contoh/split dev belum lengkap atau tidak sah.") from exc
