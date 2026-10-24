"""Go8 school filters and exact aliases for existing free-text education records.

Membership reference (2026-10-24): https://go8.edu.au/about
The former University of Adelaide name remains a recognised education alias.
"""

from ..db.skills import normalise_title

GO8 = {
    "ADELAIDE": ("Adelaide University", "University of Adelaide", "The University of Adelaide", "阿德莱德大学"),
    "ANU": ("Australian National University", "The Australian National University", "澳大利亚国立大学", "澳洲国立大学"),
    "MELBOURNE": ("University of Melbourne", "The University of Melbourne", "UniMelb", "墨尔本大学"),
    "MONASH": ("Monash University", "Monash", "莫纳什大学", "蒙纳士大学"),
    "UNSW": ("UNSW Sydney", "University of New South Wales", "The University of New South Wales", "新南威尔士大学"),
    "UQ": ("University of Queensland", "The University of Queensland", "昆士兰大学"),
    "USYD": ("University of Sydney", "The University of Sydney", "USyd", "悉尼大学"),
    "UWA": ("University of Western Australia", "The University of Western Australia", "西澳大学"),
}
ALIASES = {normalise_title(alias): code for code, names in GO8.items() for alias in (code, *names)}


def university_code(value):
    return ALIASES.get(normalise_title(value))
