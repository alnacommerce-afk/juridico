"""Numeracao unica CNJ (Res. CNJ 65/2008): validacao e mapeamento para tribunal."""
import re

_RE = re.compile(r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$")

TJ = ["", "ac", "al", "ap", "am", "ba", "ce", "dft", "es", "go", "ma", "mt", "ms", "mg",
      "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "se", "sp", "to"]


def parse(numero: str):
    m = _RE.match(numero.strip())
    if not m:
        return None
    n, dv, ano, j, tr, o = m.groups()
    return {"sequencial": n, "dv": dv, "ano": ano, "justica": j, "tribunal": tr, "origem": o}


def calc_dv(sequencial, ano, j, tr, origem) -> str:
    resto = int(f"{sequencial}{ano}{j}{tr}{origem}00") % 97
    return f"{98 - resto:02d}"


def valido(numero: str) -> bool:
    p = parse(numero)
    return bool(p) and calc_dv(p["sequencial"], p["ano"], p["justica"], p["tribunal"], p["origem"]) == p["dv"]


def formatar(numero: str) -> str:
    p = parse(numero)
    if not p:
        raise ValueError("numero CNJ invalido")
    return f"{p['sequencial']}-{p['dv']}.{p['ano']}.{p['justica']}.{p['tribunal']}.{p['origem']}"


def somente_digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero)


def alias_datajud(numero: str):
    """Alias do indice DataJud (ex.: 'tjba'); None quando nao mapeado."""
    p = parse(numero)
    if not p:
        return None
    j, tr = p["justica"], int(p["tribunal"])
    if j == "8" and 1 <= tr <= 27:
        return "tj" + TJ[tr]
    if j == "5":
        return "tst" if tr == 0 else (f"trt{tr}" if 1 <= tr <= 24 else None)
    if j == "4" and 1 <= tr <= 6:
        return f"trf{tr}"
    if j == "3" and tr == 0:
        return "stj"
    return None
