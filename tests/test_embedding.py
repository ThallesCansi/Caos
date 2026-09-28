import numpy as np
import pytest

from amazon_chaos.nonlinear.embedding import delay_embedding


def test_delay_embedding_shape():
    x = np.arange(10.0)
    embedded = delay_embedding(x, dimension=3, delay=2)
    assert embedded.shape == (6, 3)
    assert np.allclose(embedded[0], [0.0, 2.0, 4.0])


def test_delay_embedding_rejects_short_series():
    with pytest.raises(ValueError):
        delay_embedding(np.arange(3.0), dimension=4, delay=2)
