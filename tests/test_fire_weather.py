import numpy as np
import pandas as pd

from amazon_chaos.features import fire_weather as F
from amazon_chaos.features.fire_weather import dry_run, events


def test_episode_starts_need_a_quiet_gap():
    days = pd.date_range("2010-01-01", periods=120, freq="D")
    fires = pd.DataFrame(0, index=days, columns=["a", "b"])
    fires.loc[days[40], "a"] = 3   # início (40 dias sem foco antes)
    fires.loc[days[45], "a"] = 1   # mesmo episódio
    fires.loc[days[90], "a"] = 2   # novo início (45 dias depois do último)
    fires.loc[days[10], "b"] = 1   # sem 30 dias de histórico: não conta
    ev = events(fires, gap=30)
    assert ev.dia.tolist() == [days[40], days[90]] and ev.cell_id.tolist() == ["a", "a"]
    assert ev.focos.tolist() == [3, 2]


def test_dry_run_counts_consecutive_dry_days():
    rain = pd.DataFrame({"a": [5.0, 0.0, 0.2, 0.0, 3.0, 0.0]})
    assert dry_run(rain).a.tolist() == [0, 1, 2, 3, 0, 1]


def test_same_dates_keep_the_calendar_and_move_leap_day():
    days = pd.Series(pd.to_datetime(["2004-02-29", "2005-01-05"]))
    assert list(F.same_dates(days, 2003)) == list(pd.to_datetime(["2003-02-28", "2003-01-05"]))
    assert list(F.same_dates(days, 2008)) == list(pd.to_datetime(["2008-02-29", "2008-01-05"]))


def test_controls_use_real_dates_across_new_year():
    days = pd.date_range(f"{F.YEARS[0]}-01-01", f"{F.YEARS[1]}-12-31", freq="D")
    fires = pd.DataFrame(0, index=days, columns=["a"])
    fires.loc["2005-01-05", "a"] = 1
    fires.loc["2010-01-03", "a"] = 1  # outro evento: 2010 deixa de servir de controle
    signal = pd.DataFrame(0.0, index=days, columns=["a"])
    signal.loc["2005-01-05", "a"] = 1.0
    cond = {name: signal for name in F.MEASURES}
    out = F.composite({}, fires=fires, cond=cond)
    assert out.dia.tolist() == list(pd.to_datetime(["2005-01-05", "2010-01-03"]))
    # 20 anos inteiros (31 dias, dezembro do ano anterior incluído) menos o começo de 2003,
    # que não tem os 15 dias de dezembro de 2002
    first = 22 - 2
    assert out.controles.tolist() == [(first - 1) * 31 + 20, (first - 1) * 31 + 18]
    assert out.vpd_7d_percentil.tolist() == [1.0, 0.5]


def test_contrast_resamples_years_jointly():
    ev = pd.DataFrame({"ano": [2003, 2003, 2004, 2004] * 5,
                       "terco": ["preservada", "perturbada"] * 10})
    for name in F.MEASURES:
        ev[f"{name}_percentil"] = np.where(ev.terco == "preservada", 0.7, 0.5)
    out = F.contrast(ev, n=99)
    assert np.allclose(out.diferenca, 0.2) and np.allclose(out.ic_inf, 0.2)
    assert out.exclui_zero.all()


def test_thirds_are_cut_on_cells_not_on_events():
    from amazon_chaos.features.fire_weather import cell_thirds

    cells = pd.DataFrame({"perda_antecedente": np.arange(9) / 10,
                          "elegivel": [True] * 9},
                         index=[f"c{i}" for i in range(9)])
    cells.loc["fora"] = [0.95, False]
    thirds = cell_thirds(cells)
    assert "fora" not in thirds.index
    assert thirds.value_counts().tolist() == [3, 3, 3]
    # uma célula preservada com muitos episódios não muda o terço das outras
    events = pd.DataFrame({"cell_id": ["c0"] * 50 + [f"c{i}" for i in range(1, 9)]})
    events = events.join(thirds, on="cell_id")
    assert events.groupby("cell_id").terco.first().to_dict() == thirds.to_dict()
    assert (events.terco == "preservada").sum() == 52
