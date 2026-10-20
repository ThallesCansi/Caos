"""Fixed discriminants; choose parameters before inspecting surrogate ranks."""
import numpy as np
from scipy.spatial import cKDTree

from amazon_chaos.nonlinear.embedding import delay_embedding
from amazon_chaos.nonlinear.surrogates import validate_series


def _positive_integer(value, name):
    if not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} deve ser inteiro positivo")


def time_reversal_asymmetry(series, lag=1):
    """Signed third increment moment / population standard deviation cubed."""
    x = validate_series(series)
    _positive_integer(lag, "lag")
    if lag >= len(x) - 2:
        raise ValueError("Atraso deixa menos de três incrementos")
    z = (x - x.mean()) / x.std()
    return float(np.mean((z[lag:] - z[:-lag]) ** 3))


def nonlinear_prediction_error(series, dimension=3, delay=1, horizon=1,
                               neighbors=5, theiler=14, train_fraction=0.6):
    """Chronological holdout local-constant forecast, RMSE / training sigma.

    Every training target precedes the first test embedding by > theiler
    samples, including embedding span. No test target trains the model.
    """
    x = validate_series(series, min_length=32)
    for name, value in [("dimension", dimension), ("delay", delay),
                        ("horizon", horizon), ("neighbors", neighbors)]:
        _positive_integer(value, name)
    if not isinstance(theiler, (int, np.integer)) or theiler < 0:
        raise ValueError("theiler deve ser inteiro não negativo")
    if not 0.2 <= train_fraction <= 0.8:
        raise ValueError("train_fraction deve estar entre 0.2 e 0.8")
    span = (dimension - 1) * delay
    cutoff = int(len(x) * train_fraction)
    vectors = delay_embedding(x, dimension, delay)
    endpoints = np.arange(span, len(x))
    train = endpoints + horizon + theiler < cutoff - span
    test = (endpoints >= cutoff) & (endpoints + horizon < len(x))
    if train.sum() < neighbors or test.sum() < 3:
        raise ValueError("Série insuficiente para treino/teste com exclusão temporal")
    _, idx = cKDTree(vectors[train]).query(vectors[test], k=neighbors)
    idx = np.asarray(idx).reshape(test.sum(), neighbors)
    prediction = x[endpoints[train] + horizon][idx].mean(axis=1)
    sigma = np.std(x[:cutoff])
    if sigma == 0:
        raise ValueError("Treino constante")
    return float(np.sqrt(np.mean((prediction - x[endpoints[test] + horizon]) ** 2)) / sigma)
