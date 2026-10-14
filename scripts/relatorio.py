"""Gera o relatorio diario em Markdown a partir do resultado REAL da execucao."""
from datetime import date

import triagem

STATUS_TXT = {"ok": "consultada com sucesso", "parcial": "consulta INCOMPLETA", "indisponivel": "INDISPONIVEL",
              "autenticacao": "FALHA DE AUTENTICACAO/CHAVE", "nao_configurada": "NAO CONFIGURADA",
              "requer_humano": "REQUER INTERVENCAO HUMANA", "manual": "NAO consultada (manual)",
              "sem_consultas": "sem consultas a fazer"}


def _urgencia(data_final, hoje: date):
    if not data_final:
        return "URGENTE (a confirmar)"
    d = (date.fromisoformat(data_final) - hoje).days
    return "URGENTE" if d <= 5 else ("alta" if d <= 15 else "normal")


def gerar(res: dict, state: dict, cfg: dict, prazos: list, agora) -> str:
    hoje = agora.date()
    L = []
    L.append(f"# Relatorio juridico diario - {hoje.strftime('%d/%m/%Y')} {agora.strftime('%H:%M')} (America/Sao_Paulo)\n")
    achados = res["comunicacoes_novas"]
    novas_mov = sum(len(p.get("novas_movimentacoes", [])) for p in res["processos"])
    pend = [a for a in state.get("alertas", []) if not a["reconhecido"]]
    urg = [a for a in pend if a["nivel"] == "urgente"]
    L.append("## RESUMO EXECUTIVO\n")
    L.append(f"- Status da execucao: **{res['status'].upper()}**")
    L.append(f"- Possiveis processos/comunicacoes novas (a confirmar): {len(achados)}")
    L.append(f"- Processos conhecidos lidos: {sum(1 for p in res['processos'] if p.get('encontrado'))} | movimentacoes novas: {novas_mov}")
    L.append(f"- Prazos pendentes cadastrados: {sum(1 for p in prazos if p.get('situacao') != 'concluido')}")
    L.append(f"- Alertas urgentes nao reconhecidos: {len(urg)} (total pendentes: {len(pend)})")
    if res["status"] != "completa":
        L.append("- **Atencao:** verificacao incompleta. A ausencia de resultados NAO certifica a inexistencia de processos.")
    L.append("\n## NOVOS PROCESSOS IDENTIFICADOS\n")
    if not achados:
        L.append("Nenhum item novo nas fontes efetivamente consultadas.\n")
    for a in achados:
        L.append(f"### {a['numero'] or 'numero nao informado'} - {a['tribunal']}")
        L.append(f"- Empresa/termo pesquisado: {a['empresa']} / '{a['termo']}'")
        L.append(f"- Orgao: {a['orgao']} | Tipo da comunicacao: {a['tipo']} | Classe: {a.get('classe') or 'nao informada'}")
        L.append(f"- Disponibilizacao: {a['disponibilizacao']}")
        L.append("- Quem processa / o que pede / valor / fundamentos: **nao extraido automaticamente** - ler o texto abaixo e os autos; analise via skill no Claude Code.")
        L.append(f"- Confirmacao da existencia: **{a['confirmacao']}**")
        L.append(f"- Link oficial: {a['link']}")
        L.append("- Trecho da publicacao (alegacao/registro, nao conclusao):\n")
        L.append("  > " + (a["texto"][:600].replace("\n", " ") or "(sem texto)") + "\n")
    L.append("## PROCESSOS EM ANDAMENTO\n")
    casos = []
    for p in res["processos"]:
        if not p.get("encontrado"):
            L.append(f"- {p['numero']}: nao localizado no DataJud (pode haver sigilo ou atraso; consultar o tribunal).")
            continue
        d = p["dados"]
        ult = d["movimentos"][-1] if d["movimentos"] else None
        L.append(f"### {p['numero']} ({d.get('tribunal')}, {d.get('orgao')})")
        L.append(f"- Classe: {d.get('classe')} | Ajuizamento: {d.get('ajuizamento')}")
        L.append(f"- Ultima movimentacao registrada: {ult['nome'] if ult else '-'} em {ult['dataHora'] if ult else '-'}")
        for m in p.get("novas_movimentacoes", []):
            L.append(f"  - NOVA: {m['nome']} ({m['dataHora']})")
        L.append("- Significado em linguagem simples e proxima etapa: **requer analise da skill/advogado** (o DataJud traz apenas movimentos codificados, nao o conteudo dos autos).")
        casos.append((p["numero"], {"prazos": [x for x in prazos if x.get("processo") == p["numero"]],
                                    "textos": [m["nome"] or "" for m in d["movimentos"][-10:]],
                                    "confirmado": True}))
    if not res["processos"]:
        L.append("Nenhum processo conhecido cadastrado.")
    L.append("\n## PRAZOS E AUDIENCIAS\n")
    if prazos:
        L.append("| Evento | Data final | Providencia | Responsavel | Fonte | Certeza | Urgencia |\n|---|---|---|---|---|---|---|")
        for p in prazos:
            L.append(f"| {p.get('ato', '')} ({p.get('processo', '')}) | {p.get('data_final') or 'A CONFIRMAR'} | {p.get('providencia', '')} | "
                     f"{p.get('responsavel', '')} | {p.get('fonte', '')} | {p.get('grau_certeza', '')} | {_urgencia(p.get('data_final'), hoje)} |")
        L.append("\nTodo prazo exige conferencia por advogado (ver docs/prazos-processuais.md).")
    else:
        L.append("Nenhum prazo cadastrado (data/prazos.json). Prazos NAO sao inferidos automaticamente.")
    L.append("\n## RISCOS E EXPOSICAO\n")
    L.append("Valor da causa, valores pedidos, eventual condenacao e exposicao estimada sao coisas distintas; "
             "o valor da causa nao e condenacao provavel. Sem leitura da inicial, a exposicao **nao foi estimada**.")
    L.append("\n## CONTRATACAO DE ADVOGADO\n")
    if casos:
        for num, caso in casos:
            t = triagem.classificar(caso, hoje)
            L.append(f"- **{num}: {t['classificacao']}** (confianca {t['confianca']}) - {'; '.join(t['justificativa'])}. {t['proxima_acao']}")
    for a in achados:
        L.append(f"- **{a['numero']}: RECOMENDADA** (triagem preliminar; item novo a confirmar, confianca baixa). "
                 "Se houver citacao/intimacao, tratar como URGENTE e buscar advogado imediatamente.")
    if not casos and not achados:
        L.append("Sem caso concreto identificado nesta execucao. Triagem informativa; nao dispensa avaliacao profissional.")
    L.append("\n## PROVIDENCIAS RECOMENDADAS\n")
    L.append("1. Abrir cada link oficial e confirmar a existencia e a identidade da parte (homonimos).")
    L.append("2. Verificar data real de recebimento de citacao/intimacao e guardar o comprovante.")
    L.append("3. Separar contratos, pedidos, rastreio, comunicacoes com o cliente e comprovantes da operacao.")
    L.append("4. Levar ao advogado: prazo de defesa, risco de revelia, necessidade de prova, possibilidade de acordo.")
    L.append("5. Nao responder a parte contraria nem reconhecer fatos sem orientacao profissional.")
    L.append("\n## LIMITACOES DA VERIFICACAO\n")
    L.append("| Fonte | Situacao | Detalhe | Consultas |\n|---|---|---|---|")
    for f in res["fontes"]:
        L.append(f"| {f['fonte']} | {STATUS_TXT.get(f['status'], f['status'])} | {f['detalhe'] or '-'} | {f['consultas']} |")
    L.append("\n- Busca web, administrativos (MTE/Receita/Procon) e portais autenticados: **nao executados por este script**; fazer via skill/manual.")
    L.append("- DataJud nao traz o conteudo integral dos autos nem processos sigilosos.")
    L.append("- Nao foi pesquisado \"todos os lugares possiveis\": apenas as fontes da tabela acima.")
    L.append("\nProxima verificacao prevista: amanha as 08:00 (America/Sao_Paulo), se o agendador estiver instalado.")
    return "\n".join(L) + "\n"
