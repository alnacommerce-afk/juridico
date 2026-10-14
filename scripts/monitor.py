"""Orquestrador do monitoramento diario.

Uso:
  python scripts/monitor.py run [--sem-portais]   executa consultas, compara com o historico e gera relatorio
  python scripts/monitor.py status                 ultima execucao iniciada/concluida, alertas pendentes
  python scripts/monitor.py ack <id|todos>         reconhece alertas
Dados reais ficam em data/ (ignorado pelo Git) ou em JURIDICO_DATA_DIR.
"""
import argparse
import hashlib
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fontes as F  # noqa: E402
import portais as P  # noqa: E402
import relatorio  # noqa: E402
from common import (ROOT, FalhaAutenticacao, FonteIndisponivel, agora, data_dir,  # noqa: E402
                    read_json, write_json)

JANELA_INICIAL_DIAS = 30


class ApiReal:
    datajud = staticmethod(F.datajud_processo)
    djen = staticmethod(F.djen_busca)
    portal = staticmethod(P.checar_portal)


def termos_busca(emp: dict):
    t = [emp.get("razao_social"), emp.get("nome_fantasia"), *emp.get("nomes_anteriores", []),
         *emp.get("marcas", []), *emp.get("aliases_busca", [])]
    vistos, out = set(), []
    for x in t:
        if x and x.strip().upper() not in vistos:
            vistos.add(x.strip().upper())
            out.append(x.strip())
    return out


def _chave_mov(m):
    return f"{m.get('dataHora')}|{m.get('codigo')}|{m.get('nome')}"


def novo_alerta(tipo, msg, ref, nivel="info"):
    return {"id": hashlib.sha1(f"{tipo}|{ref}".encode()).hexdigest()[:10], "tipo": tipo, "nivel": nivel,
            "mensagem": msg, "ref": ref, "reconhecido": False}


def executar(cfg: dict, state: dict, api=ApiReal, fontes_cfg=None, hoje: date = None, portais=True):
    """Funcao pura (sem I/O de disco). Retorna (resultado, novo_state)."""
    hoje = hoje or agora().date()
    state = {"processos": {}, "comunicacoes": {}, "alertas": [], **state}
    fontes_res, alertas, processos_vistos, achados_novos = [], [], [], []

    def reg(fonte, status, detalhe="", consultas=0):
        fontes_res.append({"fonte": fonte, "status": status, "detalhe": detalhe, "consultas": consultas})

    ultima = state.get("ultima_concluida_sucesso_data")
    inicio = (date.fromisoformat(ultima) - timedelta(days=2)) if ultima else hoje - timedelta(days=JANELA_INICIAL_DIAS)

    # --- DataJud: processos conhecidos ---
    conhecidos = [(e, p) for e in cfg.get("empresas", []) for p in e.get("processos_conhecidos", []) if p.get("numero")]
    n_ok, erros = 0, []
    for emp, proc in conhecidos:
        num = proc["numero"]
        try:
            dados = api.datajud(num)
        except FonteIndisponivel as e:
            erros.append(f"{type(e).__name__}: {e}")
            if isinstance(e, FalhaAutenticacao) or "nao configurada" in str(e):
                break
            continue
        n_ok += 1
        if dados is None:
            processos_vistos.append({"numero": num, "empresa": emp["id"], "encontrado": False})
            continue
        ant = state["processos"].get(num)
        chaves = [_chave_mov(m) for m in dados["movimentos"]]
        novas = [m for m in dados["movimentos"] if ant is not None and _chave_mov(m) not in set(ant["movimentos"])]
        processos_vistos.append({"numero": num, "empresa": emp["id"], "encontrado": True, "dados": dados,
                                 "novas_movimentacoes": novas, "primeira_leitura": ant is None})
        if ant is None:
            alertas.append(novo_alerta("processo_conhecido_lido", f"Primeira leitura de {num}: {len(chaves)} movimentacoes registradas.", num))
        for m in novas:
            alertas.append(novo_alerta("nova_movimentacao", f"{num}: {m['nome']} em {m['dataHora']}", f"{num}|{_chave_mov(m)}", "atencao"))
        state["processos"][num] = {"movimentos": chaves, "ultima_leitura": hoje.isoformat()}
    if conhecidos:
        st = "ok" if n_ok == len(conhecidos) else ("indisponivel" if n_ok == 0 else "parcial")
        if erros and any("nao configurada" in e for e in erros):
            st = "nao_configurada"
        elif erros and any("FalhaAutenticacao" in e for e in erros):
            st = "autenticacao"
        reg("datajud", st, "; ".join(sorted(set(erros)))[:300], n_ok)
    else:
        reg("datajud", "sem_consultas", "nenhum processo conhecido cadastrado", 0)

    # --- DJEN: busca por nome de parte ---
    n_q, n_err, errs = 0, 0, []
    numeros_conhecidos = {p["numero"] for _, p in conhecidos}
    for emp in cfg.get("empresas", []):
        for termo in termos_busca(emp):
            try:
                itens = api.djen(nome_parte=termo, inicio=inicio, fim=hoje)
                n_q += 1
            except FonteIndisponivel as e:
                n_err += 1
                errs.append(str(e))
                continue
            for it in itens:
                if it["id"] in state["comunicacoes"]:
                    continue
                state["comunicacoes"][it["id"]] = {"visto_em": hoje.isoformat(), "numero": it["numero"]}
                conhecido = it["numero"] in numeros_conhecidos
                tipo = "comunicacao_processo_conhecido" if conhecido else "possivel_processo_novo"
                achados_novos.append({**it, "empresa": emp["id"], "termo": termo, "processo_conhecido": conhecido,
                                      "confirmacao": "A CONFIRMAR (busca por nome; possivel homonimo)"})
                alertas.append(novo_alerta(tipo, f"DJEN: {it['tipo']} em {it['numero']} ({it['tribunal']}) - termo '{termo}'",
                                           it["id"], "urgente" if "intima" in (it["tipo"] or "").lower() or "cita" in (it["tipo"] or "").lower() else "atencao"))
    nome_djen = "djen"
    if n_q + n_err == 0:
        reg(nome_djen, "sem_consultas", "nenhuma empresa cadastrada", 0)
    else:
        reg(nome_djen, "ok" if n_err == 0 else ("indisponivel" if n_q == 0 else "parcial"),
            "; ".join(sorted(set(errs)))[:300], n_q)

    # --- Portais (saude) e fontes manuais ---
    for f in (fontes_cfg or {}).get("fontes", []):
        if f.get("automacao") == "navegador_saude" and portais:
            r = api.portal(f["url"])
            reg(f["id"], r["status"], r["detalhe"], 0)
        elif f.get("automacao") in ("manual", "navegador_saude"):
            reg(f["id"], "manual", "requer consulta humana/autenticacao; NAO consultada automaticamente", 0)

    automaticas_ok = [f for f in fontes_res if f["fonte"] in ("datajud", "djen")]
    todas_ok = all(f["status"] in ("ok", "sem_consultas") for f in automaticas_ok)
    nenhuma_ok = not any(f["status"] == "ok" for f in automaticas_ok)
    completa = todas_ok and any(f["status"] == "ok" for f in automaticas_ok)
    status = "completa" if completa else ("falha" if nenhuma_ok else "parcial")

    for a in alertas:
        if not any(x["id"] == a["id"] for x in state["alertas"]):
            state["alertas"].append({**a, "criado_em": agora().isoformat(timespec="seconds")})
    if completa:
        state["ultima_concluida_sucesso_data"] = hoje.isoformat()
    resultado = {"status": status, "fontes": fontes_res, "processos": processos_vistos,
                 "comunicacoes_novas": achados_novos, "alertas_novos": alertas}
    return resultado, state


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--sem-portais", action="store_true")
    r.add_argument("--dados", help="diretorio de dados (padrao: data/ ou JURIDICO_DATA_DIR)")
    sub.add_parser("status").add_argument("--dados")
    a = sub.add_parser("ack")
    a.add_argument("id")
    a.add_argument("--dados")
    args = ap.parse_args(argv)
    if getattr(args, "dados", None):
        import os
        os.environ["JURIDICO_DATA_DIR"] = args.dados
    d = data_dir()
    st_path = d / "state.json"
    state = read_json(st_path, {})

    if args.cmd == "status":
        print(f"Ultima execucao iniciada : {state.get('ultima_iniciada', '-')}")
        print(f"Ultima execucao concluida (completa): {state.get('ultima_concluida_sucesso', '-')}")
        print(f"Ultima execucao (qualquer status)  : {state.get('ultima_status', '-')} em {state.get('ultima_finalizada', '-')}")
        pend = [x for x in state.get("alertas", []) if not x["reconhecido"]]
        print(f"Alertas nao reconhecidos: {len(pend)}")
        for x in pend:
            print(f"  [{x['id']}] ({x['nivel']}) {x['mensagem']}")
        return 0
    if args.cmd == "ack":
        n = 0
        for x in state.get("alertas", []):
            if args.id == "todos" or x["id"] == args.id:
                x["reconhecido"] = True
                n += 1
        write_json(st_path, state)
        print(f"{n} alerta(s) reconhecido(s).")
        return 0

    cfg = read_json(d / "empresas.json")
    if cfg is None:
        print("ERRO: data/empresas.json nao encontrado. Copie config/empresas.example.json para data/empresas.json e preencha.")
        return 2
    fontes_cfg = read_json(ROOT / "config" / "fontes.json", {})
    state["ultima_iniciada"] = agora().isoformat(timespec="seconds")
    state["ultima_status"] = "em_andamento"
    write_json(st_path, state)
    try:
        resultado, state = executar(cfg, state, ApiReal, fontes_cfg, portais=not args.sem_portais)
    except Exception as e:  # erro tecnico inesperado: registra e nao simula pesquisa
        state["ultima_status"] = f"erro_tecnico: {type(e).__name__}: {e}"[:300]
        state["ultima_finalizada"] = agora().isoformat(timespec="seconds")
        write_json(st_path, state)
        raise
    state["ultima_finalizada"] = agora().isoformat(timespec="seconds")
    state["ultima_status"] = resultado["status"]
    if resultado["status"] == "completa":
        state["ultima_concluida_sucesso"] = state["ultima_finalizada"]
    write_json(st_path, state)
    prazos = read_json(d / "prazos.json", [])
    md = relatorio.gerar(resultado, state, cfg, prazos, agora())
    out = d / "relatorios" / f"{agora().date().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    with open(d / "runs.jsonl", "a", encoding="utf-8") as fh:
        import json
        fh.write(json.dumps({"em": state["ultima_finalizada"], "status": resultado["status"],
                             "fontes": resultado["fontes"], "alertas_novos": len(resultado["alertas_novos"])},
                            ensure_ascii=False) + "\n")
    print(f"Execucao {resultado['status']}. Relatorio: {out}")
    return 0 if resultado["status"] != "falha" else 1


if __name__ == "__main__":
    sys.exit(main())
