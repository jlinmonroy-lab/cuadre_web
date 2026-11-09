"""Catálogo de países de la ficha de cliente (SPEC-W-006 D-01, Anexo B.1-B).

Los 249 códigos ISO 3166-1 alfa-2 **asignados**, escritos a mano: el spike del hito 0 no encontró ninguna fuente instalada (ni `pycountry`
ni `babel`) y no se añade una dependencia por una lista que casi no cambia. El catálogo lo define esta constante, **no** ICU: `Intl.DisplayNames`
devuelve además `XK` (Kosovo), `EU`, `UK` o `ZZ`, que no son ISO asignados y no entran. Los nombres en español los pone el frontend.
"""

_COUNTRY_CODES = (
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ "
    "BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ "
    "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ "
    "DE DJ DK DM DO DZ "
    "EC EE EG EH ER ES ET "
    "FI FJ FK FM FO FR "
    "GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY "
    "HK HM HN HR HT HU "
    "ID IE IL IM IN IO IQ IR IS IT "
    "JE JM JO JP "
    "KE KG KH KI KM KN KP KR KW KY KZ "
    "LA LB LC LI LK LR LS LT LU LV LY "
    "MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ "
    "NA NC NE NF NG NI NL NO NP NR NU NZ "
    "OM "
    "PA PE PF PG PH PK PL PM PN PR PS PT PW PY "
    "QA "
    "RE RO RS RU RW "
    "SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ "
    "TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ "
    "UA UG UM US UY UZ "
    "VA VC VE VG VI VN VU "
    "WF WS "
    "YE YT "
    "ZA ZM ZW"
)
COUNTRIES = frozenset(_COUNTRY_CODES.split())

# Los 27 Estados miembros de la UE (España incluida: su ámbito es `national`, no `eu`). `GB`, `CH`, `XI` y el resto no están.
_EU_CODES = "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK"
EU_COUNTRIES = frozenset(_EU_CODES.split())
