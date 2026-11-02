from amazon_chaos.io import appeears


class _Response:
    def __init__(self, code, status=None):
        self.status_code, self._status = code, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return {"status": self._status}


def test_wait_renews_an_expired_token(monkeypatch):
    replies = iter([_Response(200, "processing"), _Response(403), _Response(200, "done")])
    seen = []

    def get(url, headers, timeout):
        seen.append(headers["Authorization"])
        return next(replies)

    monkeypatch.setattr(appeears.requests, "get", get)
    monkeypatch.setattr(appeears, "login", lambda report=print: "novo")
    monkeypatch.setattr(appeears.time, "sleep", lambda s: None)
    appeears.wait("tarefa", "velho", report=lambda m: None)
    assert seen == ["Bearer velho", "Bearer velho", "Bearer novo"]


def test_wait_fails_when_a_fresh_token_is_also_refused(monkeypatch):
    monkeypatch.setattr(appeears.requests, "get", lambda url, headers, timeout: _Response(403))
    monkeypatch.setattr(appeears, "login", lambda report=print: "novo")
    try:
        appeears.wait("tarefa", "velho", report=lambda m: None)
    except RuntimeError as error:
        assert error.args == (403,)
    else:
        raise AssertionError("deveria falhar")
