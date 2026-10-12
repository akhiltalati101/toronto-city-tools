import pytest

from common.address_norm import ParsedAddress, normalize, parse_query


@pytest.mark.parametrize(
    "text, expected",
    [
        ("100 Queen St W", "100 queen st w"),
        ("100 Queen Street West", "100 queen st w"),
        ("100 QUEEN ST. W.", "100 queen st w"),
        ("  100   queen  st  w ", "100 queen st w"),
        ("100 Queen St W, Toronto, ON", "100 queen st w"),
        ("100 Queen St W, Toronto, Ontario M5H 2N2", "100 queen st w"),
        ("100 Queen St W Toronto ON M5H2N2", "100 queen st w"),
        ("100 Queen St W, Canada", "100 queen st w"),
        # units collapse to the building
        ("100 Queen St W #305", "100 queen st w"),
        ("#305 100 Queen St W", "100 queen st w"),
        ("100 Queen St W Unit 5", "100 queen st w"),
        ("Unit 5, 100 Queen St W", "100 queen st w"),
        ("Apt 12B, 100 Queen St W", "100 queen st w"),
        ("100 Queen St W, Suite 1200", "100 queen st w"),
        ("12-100 Queen St W", "100 queen st w"),
        ("1203 - 1 Bloor St E", "1 bloor st e"),
        # street types
        ("25 Rathburn Road West, Etobicoke", "25 rathburn rd w"),
        ("10 Lower Spadina Avenue", "10 lower spadina ave"),
        ("5 Elm Crescent", "5 elm cres"),
        ("5 Elm Court", "5 elm crt"),
        ("5 Elm Ct", "5 elm crt"),
        ("5 Oak Gardens", "5 oak gdns"),
        ("5 Bayview Blvd", "5 bayview blvd"),
        ("5 Bayview Boulevard", "5 bayview blvd"),
        # leading words that look like a type are left alone
        ("100 St Clair Ave W", "100 st clair ave w"),
        ("100 Saint Clair Avenue West", "100 st clair ave w"),
        ("100 Avenue Rd", "100 avenue rd"),
        ("1 East Mall Cres", "1 east mall cres"),
        # former municipality only stripped as its own segment
        ("10 York St", "10 york st"),
        ("5000 Yonge St, North York", "5000 yonge st"),
        # number suffix
        ("12A Main St", "12a main st"),
        ("12a main street", "12a main st"),
        # punctuation
        ("1 St. John's Rd", "1 st johns rd"),
        ("", ""),
    ],
)
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_normalize_is_idempotent():
    for text in ("100 Queen Street West, Toronto", "Unit 5, 12A St Clair Ave E", "1 Yonge St"):
        once = normalize(text)
        assert normalize(once) == once


@pytest.mark.parametrize(
    "text, expected",
    [
        ("100 Queen St W", ParsedAddress(100, "", "queen st w")),
        ("12A Main Street", ParsedAddress(12, "a", "main st")),
        ("Unit 5, 1 Bloor St E", ParsedAddress(1, "", "bloor st e")),
        ("queen st", ParsedAddress(None, "", "queen st")),
        ("100 quee", ParsedAddress(100, "", "quee")),
        ("100", ParsedAddress(100, "", "")),
        ("", ParsedAddress(None, "", "")),
    ],
)
def test_parse_query(text, expected):
    assert parse_query(text) == expected
