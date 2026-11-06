"""Corpus sintético del spike del hito 0 (Anexo B.1 de SPEC-W-003).

Los valores se calcularon con la propia librería a partir de cuerpos aleatorios con semilla fija, sin copiar los de nadie (salvo `12345678Z`,
el DNI de ejemplo del prototipo y de `contracts/`): pueden coincidir por azar con números reales y no identifican a nadie (RES-07).
Las entradas hostiles se regeneran aquí con los mismos criterios que usó el spike (2.369 en cuatro familias).
"""

import random

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
CIF_TYPES = "ABCDEFGHJNPQRSUVW"

ES_DNI = ("12345678Z", "01230956L")
ES_NIE = ("X4001342D", "Y2492503F", "Z8019878J")
ES_KLM = ("K3315686Y", "L1261942R", "M6637350X")
ES_CIF = (
    "A30789028",
    "P7766239C",
)  # control numérico y control con letra (la librería acepta las dos formas en todos los tipos)
ES_ALL = (*ES_DNI, *ES_NIE, *ES_KLM, *ES_CIF)

EU_VAT = {
    "AT": "ATU84543291",
    "BE": "BE1981162939",
    "BG": "BG1096398855",
    "CY": "CY76957253G",
    "CZ": "CZ532215599",
    "DE": "DE534861408",
    "DK": "DK11659721",
    "EE": "EE050611436",
    "EL": "EL333906790",
    "FI": "FI14848328",
    "FR": "FR89195505110",
    "HR": "HR95593513929",
    "HU": "HU46727594",
    "IE": "IE9134973S",
    "IT": "IT65531970062",
    "LT": "LT709161183614",
    "LU": "LU74142252",
    "LV": "LV85251632718",
    "MT": "MT55619217",
    "NL": "NL131073515B49",
    "PL": "PL8023132347",
    "PT": "PT731220820",
    "RO": "RO9573",
    "SE": "SE768590534601",
    "SI": "SI53348966",
    "SK": "SK7592280674",
}

# La librería los acepta; la lista blanca de `cuadre.validators` no.
XI = "XI722847175"
EU_OSS = "EU440138732"

SPECIAL_CHARS = {
    "LF": chr(10),
    "CR": chr(13),
    "TAB": chr(9),
    "VT": chr(11),
    "FF": chr(12),
    "NUL": chr(0),
    "NEL": chr(0x85),
    "NBSP": chr(0xA0),
    "ZWSP": chr(0x200B),
    "ZWJ": chr(0x200D),
    "LRM": chr(0x200E),
    "RLO": chr(0x202E),
    "LS": chr(0x2028),
}
LOOKALIKE_DIGITS = (chr(0x663), chr(0xFF13), chr(0xB2))  # cifra arábiga, cifra de ancho completo y superíndice
LIGATURE_FI = chr(0xFB01)

# Las seis muestras del spike, en su orden.
SAMPLES = ("12345678Z", "X4001342D", "A30789028", EU_VAT["DE"], EU_VAT["EL"], EU_VAT["FI"])


def hostile_inputs() -> dict[str, list[str]]:
    """Cuatro familias, 2.369 entradas: insertadas (845) y cifras parecidas (147), sustituidas (767) y fabricadas con un salto de línea (610)."""
    inserted = [s[:i] + ch + s[i:] for s in SAMPLES for i in range(len(s) + 1) for ch in SPECIAL_CHARS.values()]
    lookalike_digits = [
        s[:i] + ch + s[i + 1 :] for s in SAMPLES for i, c in enumerate(s) if c.isdigit() for ch in LOOKALIKE_DIGITS
    ]
    substituted = [s[:i] + ch + s[i + 1 :] for s in SAMPLES for i in range(len(s)) for ch in SPECIAL_CHARS.values()]

    rng = random.Random(20261106)

    def digits(n: int) -> str:
        return "".join(rng.choice("0123456789") for _ in range(n))

    lf = chr(10)
    crafted: list[str] = []
    for _ in range(200):  # DNI: siete dígitos, un salto de línea y la letra que corresponde a esos siete dígitos
        body = digits(7)
        crafted.append(body + lf + DNI_LETTERS[int(body) % 23])
    for letter in "XYZ":
        for _ in range(40):
            body = digits(6)
            crafted.append(letter + body + lf + DNI_LETTERS[int(str("XYZ".index(letter)) + body) % 23])
    for letter in "KLM":
        for _ in range(40):
            body = digits(6)
            crafted.append(letter + body + lf + DNI_LETTERS[int(body) % 23])
    for letter in CIF_TYPES:  # CIF: la librería lanza `ValueError`
        for _ in range(10):
            crafted.append(letter + digits(6) + lf + rng.choice("0123456789"))
    return {
        "insertadas": inserted,
        "cifras_parecidas": lookalike_digits,
        "sustituidas": substituted,
        "fabricadas_con_salto_de_linea": crafted,
    }
