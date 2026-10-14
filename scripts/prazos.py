"""Calculo auxiliar de prazos processuais. NUNCA substitui conferencia por advogado.

Regras base (CPC): art. 219 (dias uteis), art. 224 (exclui o dia do comeco, inclui o do
vencimento; inicio no primeiro dia util seguinte; vencimento em dia sem expediente
prorroga), art. 231 (marcos iniciais) e art. 220 (suspensao 20/12-20/01, quando aplicavel).
Feriados locais e suspensoes por ato do tribunal NAO sao conhecidos: devem ser informados.
"""
from datetime import date, timedelta

CERTEZA_CONFIRMAR = "PRAZO A CONFIRMAR URGENTEMENTE"


def pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> dict:
    fixos = {(1, 1): "Confraternizacao Universal", (4, 21): "Tiradentes", (5, 1): "Dia do Trabalho",
             (9, 7): "Independencia", (10, 12): "N. Sra. Aparecida", (11, 2): "Finados",
             (11, 15): "Proclamacao da Republica", (11, 20): "Consciencia Negra (Lei 14.759/2023)",
             (12, 25): "Natal"}
    r = {date(ano, m, d): n for (m, d), n in fixos.items()}
    r[pascoa(ano) - timedelta(days=2)] = "Sexta-feira Santa"
    return r


def datas_a_conferir(ano: int) -> dict:
    """Nao aplicadas automaticamente: variam conforme o tribunal."""
    p = pascoa(ano)
    return {p - timedelta(days=48): "Carnaval (segunda)", p - timedelta(days=47): "Carnaval (terca)",
            p - timedelta(days=46): "Quarta de Cinzas", p + timedelta(days=60): "Corpus Christi",
            date(ano, 10, 28): "Dia do Servidor Publico (ponto facultativo)"}


def _parse(d):
    return d if isinstance(d, date) else date.fromisoformat(d)


class Calendario:
    def __init__(self, feriados_extra=None, suspensoes=None, aplicar_suspensao_cpc_220=False):
        self.extra = {_parse(k): v for k, v in (feriados_extra or {}).items()}
        self.suspensoes = [(_parse(a), _parse(b)) for a, b in (suspensoes or [])]
        self.cpc220 = aplicar_suspensao_cpc_220

    def motivo_nao_util(self, d: date):
        if d.weekday() >= 5:
            return "fim de semana"
        if d in self.extra:
            return self.extra[d]
        nac = feriados_nacionais(d.year)
        if d in nac:
            return nac[d]
        for a, b in self.suspensoes:
            if a <= d <= b:
                return "suspensao informada"
        if self.cpc220 and (d.month == 12 and d.day >= 20 or d.month == 1 and d.day <= 20):
            return "suspensao CPC art. 220 (20/12-20/01)"
        return None

    def util(self, d):
        return self.motivo_nao_util(d) is None

    def proximo_util(self, d):
        d += timedelta(days=1)
        while not self.util(d):
            d += timedelta(days=1)
        return d


def marco_publicacao_dje(disponibilizacao, cal: Calendario) -> date:
    """CPC art. 224 par. 2: publicacao = primeiro dia util seguinte a disponibilizacao."""
    d = _parse(disponibilizacao)
    return cal.proximo_util(d)


def calcular(marco, dias: int, tipo="uteis", cal: Calendario = None, marco_confirmado=True,
             hoje=None, regra="", ato="", fonte="", responsavel="advogado/empresa"):
    """marco: data do evento que dispara o prazo (ciencia, juntada do AR, publicacao...).
    O dia 1 do prazo e o primeiro dia util seguinte ao marco (CPC art. 224)."""
    cal = cal or Calendario()
    if marco is None:
        return {"ato": ato, "fonte": fonte, "data_final": None, "grau_certeza": CERTEZA_CONFIRMAR,
                "conferencia_advogado": True, "situacao": "aguardando confirmacao",
                "memoria": ["Marco inicial desconhecido: nao calcular por suposicao."],
                "responsavel": responsavel}
    marco = _parse(marco)
    memoria = [f"Marco considerado: {marco.isoformat()} (regra: {regra or 'nao informada'}).",
               "Exclui-se o dia do comeco (CPC art. 224)."]
    d = marco
    if tipo == "uteis":
        contados = 0
        while contados < dias:
            d += timedelta(days=1)
            if cal.util(d):
                contados += 1
        final = d
    else:
        final = marco + timedelta(days=dias)
        while not cal.util(final):
            memoria.append(f"{final.isoformat()} sem expediente ({cal.motivo_nao_util(final)}): prorroga.")
            final += timedelta(days=1)
    memoria.append(f"{dias} dias {'uteis' if tipo == 'uteis' else 'corridos'} -> vencimento {final.isoformat()}.")
    conferir = [f"{k.isoformat()} {v}" for k, v in datas_a_conferir(marco.year).items()
                if marco < k <= final] + \
               [f"{k.isoformat()} {v}" for k, v in datas_a_conferir(final.year).items()
                if final.year != marco.year and marco < k <= final]
    if conferir:
        memoria.append("Datas a conferir com o tribunal (nao aplicadas): " + "; ".join(conferir))
    certeza = "MEDIA" if marco_confirmado else CERTEZA_CONFIRMAR
    if marco_confirmado and not conferir and not cal.extra:
        memoria.append("Feriados locais/ato do tribunal nao verificados.")
    hoje = _parse(hoje) if hoje else date.today()
    if not marco_confirmado:
        situacao = "aguardando confirmacao"
    elif final < hoje:
        situacao = "possivelmente vencido (confirmar com advogado)"
    else:
        situacao = "pendente"
    return {"ato": ato, "fonte": fonte, "marco": marco.isoformat(), "dias": dias, "tipo": tipo,
            "regra": regra, "data_final": final.isoformat(), "grau_certeza": certeza,
            "conferencia_advogado": True, "responsavel": responsavel, "situacao": situacao,
            "memoria": memoria}


