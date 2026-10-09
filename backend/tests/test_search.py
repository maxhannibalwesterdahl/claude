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


# --- nemlig.com ---------------------------------------------------------------

NEMLIG = {
    "Products": {"Products": [{"Name": "Lasagne Bolognese", "Url": "lasagne-bolognese-5067470"}]},
    "Recipes": [
        {"Name": "Lasagne med rodfrugter", "Url": "/opskrifter/maries-magiske-lasagne-98000520",
         "PrimaryImage": "https://www.nemlig.com/scommerce/images/a.jpg?i={DCFC}&v=AOi"},
        {"Name": "Lasagne med rodfrugter", "Url": "/opskrifter/maries-magiske-lasagne-98000520", "PrimaryImage": ""},
        {"Name": "Dumpling lasagne", "Url": "/opskrifter/dumpling-lasagne-98004560", "PrimaryImage": None},
        {"Name": "En vare", "Url": "/en-vare-5067470", "PrimaryImage": ""},
    ],
}

NEMLIG_RECIPE = {
    "content": [
        {"TemplateName": "ribbon"},
        {
            "TemplateName": "recipedetailspot",
            "Header": "Lasagne med rodfrugter",
            "NumberOfPersons": 4,
            "Media": [{"MediaType": "image", "Url": "https://www.nemlig.com/scommerce/images/a.jpg?i={DCFC}&v=AOi"}],
            "IngredientGroups": [
                {"Name": "Kødsovs", "Ingredients": [
                    {"Text": "Løg", "Amount": "2", "Unit": "stk."},
                    {"Text": "Salt og peber", "Amount": "", "Unit": ""},
                ]},
                {"Name": "Bechamel", "Ingredients": [{"Text": "Mælk", "Amount": "0.5", "Unit": "l"}]},
            ],
            "Instructions": "<h4>K&oslash;dsovs</h4><ul><li>\n<p>Pil l&oslash;g</p>\n</li><li><p>Brun k&oslash;det</p></li></ul>"
                            "<p><strong>Tips:</strong></p><p>Lav dobbelt portion</p>",
        },
    ]
}


def test_nemlig_parse_takes_only_recipes():
    from madplan import search_nemlig as sn

    hits = sn.parse(NEMLIG)
    assert [h.title for h in hits] == ["Lasagne med rodfrugter", "Dumpling lasagne"]
    assert hits[0].url == "https://www.nemlig.com/opskrifter/maries-magiske-lasagne-98000520"
    assert hits[0].image_url.endswith("&w=120&h=120&mode=crop") and hits[1].image_url == ""
    assert sn.parse({"Recipes": None}) == []


def test_nemlig_search_endpoint(client, monkeypatch):
    from madplan import search_nemlig as sn

    monkeypatch.setattr(sn, "search", lambda q: sn.parse(NEMLIG))
    rec = client.post("/api/recipes", json={"title": "Lasagne", "source_url": "https://www.nemlig.com/opskrifter/maries-magiske-lasagne-98000520/"}).json()
    hits = client.get("/api/search/nemlig?q=lasagne").json()
    assert [(h["title"], h["recipe_id"]) for h in hits] == [("Lasagne med rodfrugter", rec["id"]), ("Dumpling lasagne", None)]

    def fail(q):
        raise sv.SearchError("nemlig.com svarer ikke lige nu")
    monkeypatch.setattr(sn, "search", fail)
    assert client.get("/api/search/nemlig?q=lasagne").status_code == 502


def test_nemlig_recipe_is_read_from_page_json():
    import json

    from madplan import importer

    url = "https://www.nemlig.com/opskrifter/maries-magiske-lasagne-98000520"
    r = importer.scrape_nemlig(json.dumps(NEMLIG_RECIPE), url)
    assert (r.title, r.servings) == ("Lasagne med rodfrugter", 4)
    assert [(g.name, g.lines) for g in r.groups] == [("Kødsovs", ["2 stk. løg", "Salt og peber"]), ("Bechamel", ["0,5 l mælk"])]
    assert r.instructions == ["Pil løg", "Brun kødet"]
    assert r.image_url.endswith("&w=1200") and r.warnings == []
    assert importer.is_nemlig(url) and not importer.is_nemlig("https://nemlig.com.example.dk/opskrifter/x")
    with pytest.raises(importer.RecipeImportError):
        importer.scrape_nemlig('{"content": [{"TemplateName": "ribbon"}]}', url)
    with pytest.raises(importer.RecipeImportError):
        importer.scrape_nemlig("<html>", url)
