import pytest

from madplan.ingredients import DanishRuleParser

parse = DanishRuleParser().parse


@pytest.mark.parametrize(
    "line, qty, unit, item",
    [
        ("1½ dl piskefløde", 1.5, "dl", "piskefløde"),
        ("½ tsk salt", 0.5, "tsk", "salt"),
        ("1,5 dl fløde", 1.5, "dl", "fløde"),
        ("1/2 citron", 0.5, None, "citron"),
        ("0,40 liter vaniljeis", 0.4, "l", "vaniljeis"),
        ("1 knivspids salt", 1, "knsp", "salt"),
        ("2 dåser sorte bønner, drænede", 2, "dåse", "sorte bønner"),
        ("4 stk æg", 4, None, "æg"),
        ("salt og friskkværnet peber", None, None, "salt og friskkværnet peber"),
        ("fed hvidløg", None, "fed", "hvidløg"),
    ],
)
def test_quantity_and_unit(line, qty, unit, item):
    p = parse(line)
    assert (p.quantity, p.unit, p.item) == (qty, unit, item)


def test_range_keeps_upper_bound():
    p = parse("2-3 forårsløg")
    assert (p.quantity, p.quantity_max, p.item) == (2, 3, "forårsløg")


def test_decimal_comma_is_not_a_note_separator():
    p = parse("1 renset høne på ca. 2,2 kg eller et par kyllinger")
    assert p.item == "høne"


@pytest.mark.parametrize(
    "line, item",
    [
        ("2 hakkede løg", "løg"),
        ("400 g hakket oksekød", "hakket oksekød"),
        ("1 dåse hakkede tomater", "hakkede tomater"),
        ("150 g revet cheddar", "revet cheddar"),
        ("1 dl hakket persille", "persille"),
        ("2 store tomater (skåret i skiver)", "tomater"),
    ],
)
def test_preparation_removed_but_products_kept(line, item):
    assert parse(line).item == item


def test_unit_after_preparation_word():
    p = parse("2 hakkede fed hvidløg")
    assert (p.quantity, p.unit, p.item) == (2, "fed", "hvidløg")


def test_size_word_before_comma_is_not_a_note():
    p = parse("2 små, finthakkede fed hvidløg")
    assert (p.unit, p.item) == ("fed", "hvidløg")


def test_note_is_kept():
    p = parse("100 g røget laks, skåret i strimler")
    assert p.item == "røget laks"
    assert p.note == "skåret i strimler"


def test_trailing_cut_without_comma():
    p = parse("2 bundter forårsløg i 3 cm skrå stykker (ca. 200 g)")
    assert (p.quantity, p.unit, p.item) == (2, "bundt", "forårsløg")
