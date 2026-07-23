from yh010g.parsers.amova import parse_amova
from yh010g.parsers.mufg_trust import parse_mufg_trust
from yh010g.parsers.nissay import parse_nissay

PARSERS = {
    "mufg_trust": parse_mufg_trust,
    "amova": parse_amova,
    "nissay": parse_nissay,
}

__all__ = ["PARSERS", "parse_amova", "parse_mufg_trust", "parse_nissay"]
