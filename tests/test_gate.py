import pandas as pd

from amazon_chaos.nonlinear.gate import _seed, ews_tasks, rejection_rates, tasks, verdict
from amazon_chaos.nonlinear.suite import load_spec, spec_hash, surrogate_suite
from amazon_chaos.nonlinear.synthetic import control


def test_every_task_gets_its_own_seed():
    spec = load_spec()
    work = tasks(spec) + ews_tasks(spec)
    seeds = [_seed(spec, t) for t in work]
    assert len(set(seeds)) == len(seeds)
    g = spec["gate"]
    assert len(tasks(spec)) == (len(g["positive"]) + len(g["negative"])) * len(
        g["lengths"]) * len(g["noise"]) * g["repetitions"]


def test_spec_is_draft_until_frozen_and_hash_is_stable():
    spec = load_spec()
    assert spec["status"] in {"rascunho", "congelado"}
    assert spec_hash(spec) == spec_hash(load_spec())


def test_suite_rejects_linear_null_for_chaos_only():
    spec = load_spec()
    chaos = surrogate_suite(control("henon", 1024, seed=1), spec, n_surrogates=19,
                            names=["pe_complexity", "prediction"])
    noise = surrogate_suite(control("ar1", 1024, seed=1), spec, n_surrogates=19,
                            names=["pe_complexity", "prediction"])
    assert chaos.pvalues["pe_complexity"] <= 0.05 and chaos.pvalues["prediction"] <= 0.05
    assert noise.pvalues["pe_complexity"] > 0.05
    table = chaos.table(control="henon")
    assert set(table.descriptor) == {"pe_complexity", "prediction"} and (table.n_null == 19).all()


def test_verdict_applies_preregistered_criterion():
    spec = load_spec()
    n, noise = max(spec["gate"]["lengths"]), max(spec["gate"]["noise"])
    rows = []
    for name, power, size in [("bom", 1.0, 0.05), ("frouxo", 1.0, 0.5), ("fraco", 0.3, 0.0)]:
        for kind in spec["gate"]["positive"]:
            rows += [{"descriptor": name, "control": kind, "group": "positivo", "n": n,
                      "noise": noise, "pvalue": 0.01 if r < 10 * power else 0.5}
                     for r in range(10)]
        for kind in ["white", "ar1", "seasonal_trend"]:
            rows += [{"descriptor": name, "control": kind, "group": "negativo", "n": n,
                      "noise": noise, "pvalue": 0.01 if r < 10 * size else 0.5}
                     for r in range(10)]
    result = verdict(rejection_rates(pd.DataFrame(rows), 0.05), spec).set_index("descriptor")
    assert result.passa.to_dict() == {"bom": True, "fraco": False, "frouxo": False}


def test_batch_cell_task_produces_tests_ews_and_sensitivity():
    import numpy as np

    from amazon_chaos.nonlinear.batch import cell_task

    spec = load_spec()
    spec = {**spec, "surrogates": {**spec["surrogates"], "per_cell": 3},
            "ews": {**spec["ews"], "surrogates": 3},
            "series": {**spec["series"], "period": ["2001-01-01", "2004-12-31"],
                       "windows": [["2001-01-01", "2002-12-31"]]}}
    days = pd.date_range("1990-01-01", "2004-12-31")
    rng = np.random.default_rng(0)
    series = {"t2m": pd.Series(25 + np.sin(2 * np.pi * days.dayofyear / 365.25)
                               + rng.normal(size=len(days)), index=days)}
    table = cell_task(spec, "ERA5_teste", series)
    assert set(table.kind) == {"teste", "ews", "sensibilidade"}
    assert set(table.window) == {"2001_2004", "2001_2002"}
    assert (table.descriptor != "erro").all()
