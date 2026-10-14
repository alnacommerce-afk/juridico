"""Triagem informativa sobre contratacao de advogado. Nao e garantia de dispensa de representacao."""
from datetime import date

PALAVRAS_URGENTES = ("citacao", "citação", "intimacao", "intimação", "audiencia", "audiência", "revelia",
                     "penhora", "bloqueio", "sisbajud", "execucao", "execução", "cumprimento de sentenca",
                     "cumprimento de sentença", "sentenca", "sentença", "liminar", "tutela", "multa")

URGENTE, RECOMENDADA = "URGENTE", "RECOMENDADA"
INICIAL = "AVALIAÇÃO INICIAL POSSÍVEL SEM CONTRATAÇÃO IMEDIATA"

ACOES = {
    URGENTE: "Contatar advogado habilitado HOJE; separar citacao/intimacao, comprovante de recebimento e "
             "documentos da operacao. Se necessario, consultar Defensoria Publica ou assistencia juridica.",
    RECOMENDADA: "Agendar consulta com advogado da area para estrategia de defesa e avaliacao de risco.",
    INICIAL: "Acompanhar; revisar a cada nova movimentacao, prazo ou documento. A analise tem limitacoes "
             "e nao dispensa avaliacao profissional.",
}


def classificar(caso: dict, hoje=None) -> dict:
    """caso: {'prazos': [{'data_final','grau_certeza'}], 'audiencia': 'YYYY-MM-DD', 'textos': [str],
    'valor_causa': float|None, 'confirmado': bool}"""
    hoje = hoje or date.today()
    razoes, nivel = [], INICIAL
    for p in caso.get("prazos", []):
        if not p.get("data_final") or str(p.get("grau_certeza", "")).startswith("PRAZO A CONFIRMAR"):
            razoes.append("prazo com marco inicial nao confirmado")
            nivel = URGENTE
            continue
        dias = (date.fromisoformat(p["data_final"]) - hoje).days
        if dias <= 7:
            razoes.append(f"prazo vencido ou a vencer em {dias} dia(s) (conferir)")
            nivel = URGENTE
    if caso.get("audiencia"):
        dias = (date.fromisoformat(caso["audiencia"]) - hoje).days
        if dias <= 15:
            razoes.append(f"audiencia em janela de {dias} dia(s): risco de revelia/perda de prazo")
            nivel = URGENTE
    texto = " ".join(caso.get("textos", [])).lower()
    achadas = sorted({w for w in PALAVRAS_URGENTES if w in texto})
    if achadas:
        razoes.append("termos sensiveis nas movimentacoes: " + ", ".join(achadas))
        if nivel == INICIAL:
            nivel = RECOMENDADA
    if caso.get("valor_causa") and nivel == INICIAL:
        razoes.append("ha valor de causa/risco financeiro a avaliar")
        nivel = RECOMENDADA
    if not razoes:
        razoes.append("sem prazo, audiencia ou termo sensivel identificado nas fontes consultadas")
    confianca = "baixa" if caso.get("confirmado") is False or nivel == INICIAL else "media"
    return {"classificacao": nivel, "justificativa": razoes, "confianca": confianca,
            "proxima_acao": ACOES[nivel]}
