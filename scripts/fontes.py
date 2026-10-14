"""Clientes das fontes oficiais automatizaveis: DataJud (CNJ) e DJEN (comunicacoes)."""
import os
import urllib.parse
from datetime import date

import cnj
from common import FonteIndisponivel, http_json

DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"
DJEN_BASE = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
LINK_CONSULTA_DJEN = "https://comunica.pje.jus.br/"


def datajud_processo(numero: str, api_key=None, _http=http_json):
    """Consulta um processo conhecido no DataJud. Retorna dict normalizado ou None (nao encontrado).
    A chave publica do CNJ (wiki da API) vai em DATAJUD_API_KEY; nao e versionada."""
    api_key = api_key or os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        raise FonteIndisponivel("DATAJUD_API_KEY nao configurada (ver docs/monitoramento-diario.md)")
    alias = cnj.alias_datajud(numero)
    if not alias:
        raise FonteIndisponivel("tribunal nao mapeado para o numero informado")
    url = f"{DATAJUD_BASE}/api_publica_{alias}/_search"
    r = _http(url, "POST", {"query": {"match": {"numeroProcesso": cnj.somente_digitos(numero)}}},
              {"Authorization": f"APIKey {api_key}"})
    hits = r.get("hits", {}).get("hits", [])
    if not hits:
        return None
    s = hits[0].get("_source", {})
    movs = [{"codigo": m.get("codigo"), "nome": m.get("nome"), "dataHora": m.get("dataHora"),
             "complementos": [c.get("nome") for c in m.get("complementosTabelados", []) or []]}
            for m in s.get("movimentos", []) or []]
    movs.sort(key=lambda m: m.get("dataHora") or "")
    return {"numero": numero, "tribunal": s.get("tribunal"), "grau": s.get("grau"),
            "classe": (s.get("classe") or {}).get("nome"),
            "orgao": (s.get("orgaoJulgador") or {}).get("nome"),
            "ajuizamento": s.get("dataAjuizamento"),
            "assuntos": [a.get("nome") for a in s.get("assuntos", []) or [] if isinstance(a, dict)],
            "movimentos": movs, "fonte": f"DataJud/{alias}"}


def djen_busca(nome_parte=None, numero_processo=None, inicio: date = None, fim: date = None,
               max_paginas=5, _http=http_json):
    """Comunicacoes/publicacoes do DJEN. Busca por NOME pode trazer homonimos: sempre 'a confirmar'."""
    achados, pagina = [], 1
    while pagina <= max_paginas:
        q = {"pagina": pagina, "itensPorPagina": 100}
        if nome_parte:
            q["nomeParte"] = nome_parte
        if numero_processo:
            q["numeroProcesso"] = cnj.somente_digitos(numero_processo)
        if inicio:
            q["dataDisponibilizacaoInicio"] = inicio.isoformat()
        if fim:
            q["dataDisponibilizacaoFim"] = fim.isoformat()
        r = _http(DJEN_BASE + "?" + urllib.parse.urlencode(q))
        if r.get("status") not in (None, "success"):
            raise FonteIndisponivel(f"DJEN respondeu status={r.get('status')}: {r.get('message')}")
        itens = r.get("items", []) or []
        for i in itens:
            achados.append({"id": str(i.get("id")),
                            "numero": i.get("numeroprocessocommascara") or i.get("numero_processo"),
                            "tribunal": i.get("siglaTribunal"), "orgao": i.get("nomeOrgao"),
                            "tipo": i.get("tipoComunicacao"), "classe": i.get("nomeClasse"),
                            "disponibilizacao": i.get("data_disponibilizacao"),
                            "texto": (i.get("texto") or "")[:4000],
                            "link": i.get("link") or LINK_CONSULTA_DJEN})
        if len(itens) < 100:
            break
        pagina += 1
    return achados
