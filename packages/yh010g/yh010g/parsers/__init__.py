from yh010g.parsers.amova import parse_amova
from yh010g.parsers.daiwa import parse_daiwa
from yh010g.parsers.mufg_am import parse_mufg_am
from yh010g.parsers.mufg_trust import parse_mufg_trust
from yh010g.parsers.nissay import parse_nissay
from yh010g.parsers.nomura import parse_nomura
from yh010g.parsers.smdam import parse_smdam
from yh010g.parsers.smtam import parse_smtam

PARSERS = {
    "mufg_trust": parse_mufg_trust,
    "amova": parse_amova,
    "nissay": parse_nissay,
    "nomura": parse_nomura,
    "daiwa": parse_daiwa,
    "smdam": parse_smdam,
    "mufg_am": parse_mufg_am,
    "smtam": parse_smtam,
}

__all__ = ["PARSERS", "parse_amova", "parse_daiwa", "parse_mufg_am", "parse_mufg_trust",
           "parse_nissay", "parse_nomura", "parse_smdam", "parse_smtam"]
