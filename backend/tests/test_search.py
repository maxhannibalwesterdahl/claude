import pytest

from madplan import search_valdemarsro as sv

PAGE = """
<div class="post-list-item" data-terms="">
  <div class="post-list-item-image lazyload ver2" data-src="https://www.valdemarsro.dk/wp-content/a.jpg"><a href="#"></a></div>
  <span class="post-list-item-title"><a href="https://www.valdemarsro.dk/kyllingefrikadeller/">Kyllingefrikadeller</a></span>
</div>
<div class="post-list-item" data-terms="">
  <div class="post-list-item-image" data-src="https://www.valdemarsro.dk/wp-content/b.jpg"></div>
  <span class="post-list-item-title"><a href="https://www.valdemarsro.dk/16-skoenne-opskrifter/">16 skønne opskrifter til fryseren</a></span>
</div>
<div class="post-list-item" data-terms="">
  <div class="post-list-item-image" data-src="https://www.valdemarsro.dk/wp-content/c.jpg"></div>
  <span class="post-list-item-title"><a href="https://www.valdemarsro.dk/smaa-glimt-52/">Små glimt</a></span>
</div>
<div class="post-list-item" data-terms="">
  <div class="post-list-item-image" data-src="https://www.valdemarsro.dk/wp-content/d.jpg"></div>
  <span class="post-list-item-title"><a href="https://www.valdemarsro.dk/kylling-i-karry/">Kylling i karry &amp; ris</a></span>
</div>
<div class="post-list-item" data-terms="">
  <div class="post-list-item-image" data-src="https://www.valdemarsro.dk/wp-content/d.jpg"></div>
  <span class="post-list-item-title"><a href="https://www.valdemarsro.dk/kylling-i-karry/">Kylling i karry &amp; ris</a></span>
</div>
"""


def test_parse_skips_articles_and_duplicates():
    hits = sv.parse(PAGE)
    assert [h.title for h in hits] == ["Kyllingefrikadeller", "Kylling i karry & ris"]
    assert hits[0].url == "https://www.valdemarsro.dk/kyllingefrikadeller/"
    assert hits[0].image_url.endswith("a.jpg")


def test_search_endpoint_marks_imported(client, monkeypatch):
    monkeypatch.setattr(sv, "search", lambda q: sv.parse(PAGE))
    rec = client.post("/api/recipes", json={"title": "Frikadeller", "source_url": "https://www.valdemarsro.dk/kyllingefrikadeller"}).json()
    hits = client.get("/api/search/valdemarsro?q=kylling").json()
    assert [(h["title"], h["recipe_id"]) for h in hits] == [("Kyllingefrikadeller", rec["id"]), ("Kylling i karry & ris", None)]
    assert client.get("/api/search/valdemarsro?q=ky").json() == []


def test_search_endpoint_when_site_is_down(client, monkeypatch):
    def fail(q):
        raise sv.SearchError("Valdemarsro svarer ikke lige nu")
    monkeypatch.setattr(sv, "search", fail)
    r = client.get("/api/search/valdemarsro?q=kylling")
    assert r.status_code == 502 and "Valdemarsro" in r.json()["detail"]


def test_search_is_cached(monkeypatch):
    calls = []

    class FakeClient:
        def get(self, url, params):
            calls.append(params["s"])
            class R:
                text = PAGE
                def raise_for_status(self): pass
            return R()

    sv._cache.clear()
    sv.search("Kylling", client=FakeClient())
    sv.search("kylling ", client=FakeClient())
    assert calls == ["kylling"]


def test_duplicate_import_ignores_trailing_slash(client):
    client.post("/api/recipes", json={"title": "A", "source_url": "https://www.valdemarsro.dk/lasagne/"})
    r = client.post("/api/recipes", json={"title": "B", "source_url": "https://www.valdemarsro.dk/lasagne"})
    assert r.status_code == 409


def test_recipe_summary_lists_ingredients(client):
    client.post("/api/recipes", json={"title": "Aftensmad", "ingredients": [{"raw": "500 g kyllingebryst"}, {"raw": "1 dragefrugt"}]})
    s = client.get("/api/recipes").json()[0]
    assert s["ingredients"] == ["dragefrugt", "kyllingebryst"]
