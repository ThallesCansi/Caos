import numpy as np
import pandas as pd

from amazon_chaos.features.fire_weather import _window_sum, dry_run, events


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


def test_window_sum_wraps_around_the_calendar():
    cube = np.zeros((1, 366, 1))
    cube[0, 0, 0] = 1.0  # 1º de janeiro
    total = _window_sum(cube, 2)[0, :, 0]
    assert total[[364, 365, 0, 1, 2]].tolist() == [1, 1, 1, 1, 1] and total[3] == 0
