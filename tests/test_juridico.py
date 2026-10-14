"""Testes com dados 100% sinteticos. Execute: python -m unittest discover -s tests -v"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import cnj  # noqa: E402
import fontes  # noqa: E402
import monitor  # noqa: E402
import portais  # noqa: E402
import prazos  # noqa: E402
import relatorio  # noqa: E402
import triagem  # noqa: E402
from common import FalhaAutenticacao, FonteIndisponivel  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
DV = cnj.calc_dv("1234567", "2026", "8", "05", "0001")
NUM = f"1234567-{DV}.2026.8.05.0001"
CFG = {"empresas": [{"id": "ex", "razao_social": "EMPRESA SINTETICA LTDA", "nome_fantasia": "Sintetica",
                     "processos_conhecidos": [{"numero": NUM}]}]}
AGORA = datetime(2026, 1, 15, 8, 0, tzinfo=timezone(timedelta(hours=-3)))


def fx(nome):
    return json.loads((FIX / nome).read_text(encoding="utf-8"))


class ApiFake:
    def __init__(self, datajud="fx1", djen=None, erro_datajud=None, erro_djen=None, portal=None):
        self.dj, self.dn, self.ed, self.en, self.pt = datajud, djen or [], erro_datajud, erro_djen, portal

    def datajud(self, numero):
        if self.ed:
            raise self.ed
        return fx("datajud_v1.json" if self.dj == "fx1" else "datajud_v2.json")

    def djen(self, **kw):
        if self.en:
            raise self.en
        return self.dn

    def portal(self, url):
        return self.pt or {"status": "requer_humano", "detalhe": "barreira detectada: captcha"}


class TestCNJ(unittest.TestCase):
    def test_validacao_e_alias(self):
        self.assertTrue(cnj.valido(NUM))
        self.assertFalse(cnj.valido(NUM[:-1] + "9"))
        self.assertEqual(cnj.alias_datajud(NUM), "tjba")
        self.assertEqual(cnj.alias_datajud(f"1234567-{cnj.calc_dv('1234567','2026','5','15','0001')}.2026.5.15.0001"), "trt15")
        self.assertIsNone(cnj.alias_datajud("lixo"))


class TestPrazos(unittest.TestCase):
    def test_dias_uteis_simples(self):
        r = prazos.calcular("2026-03-02", 15, hoje="2026-03-10")
        self.assertEqual(r["data_final"], "2026-03-23")
        self.assertEqual(r["situacao"], "pendente")
        self.assertTrue(r["conferencia_advogado"])

    def test_feriado_nacional_nao_conta(self):
        r = prazos.calcular("2026-04-17", 2)  # sex; 20/04 seg, 21/04 Tiradentes -> 22/04
        self.assertEqual(r["data_final"], "2026-04-22")

    def test_sexta_santa_2026(self):
        self.assertEqual(prazos.pascoa(2026), date(2026, 4, 5))
        self.assertIn(date(2026, 4, 3), prazos.feriados_nacionais(2026))

    def test_corridos_prorroga(self):
        r = prazos.calcular("2026-03-06", 1, tipo="corridos")  # sab 07 -> seg 09
        self.assertEqual(r["data_final"], "2026-03-09")

    def test_marco_desconhecido_exige_confirmacao(self):
        r = prazos.calcular(None, 15)
        self.assertEqual(r["grau_certeza"], prazos.CERTEZA_CONFIRMAR)
        self.assertIsNone(r["data_final"])

    def test_marco_nao_confirmado(self):
        r = prazos.calcular("2026-03-02", 15, marco_confirmado=False, hoje="2026-06-01")
        self.assertEqual(r["grau_certeza"], prazos.CERTEZA_CONFIRMAR)
        self.assertEqual(r["situacao"], "aguardando confirmacao")  # nunca afirma vencido sem marco certo

    def test_vencido_e_cauteloso(self):
        r = prazos.calcular("2026-03-02", 5, hoje="2026-06-01")
        self.assertIn("confirmar", r["situacao"])

    def test_suspensao_cpc_220_e_extra(self):
        cal = prazos.Calendario(aplicar_suspensao_cpc_220=True)
        r = prazos.calcular("2026-12-18", 5, cal=cal)
        self.assertGreater(r["data_final"], "2027-01-20")
        cal2 = prazos.Calendario(feriados_extra={"2026-03-03": "local"})
        self.assertEqual(prazos.calcular("2026-03-02", 1, cal=cal2)["data_final"], "2026-03-04")

    def test_publicacao_dje(self):
        self.assertEqual(prazos.marco_publicacao_dje("2026-03-06", prazos.Calendario()), date(2026, 3, 9))


class TestMonitor(unittest.TestCase):
    def test_primeira_execucao_e_diff(self):
        r1, st = monitor.executar(CFG, {}, ApiFake(), {}, hoje=date(2026, 1, 15), portais=False)
        self.assertEqual(r1["status"], "completa")
        self.assertTrue(r1["processos"][0]["primeira_leitura"])
        self.assertEqual(len(st["alertas"]), 1)
        r2, st2 = monitor.executar(CFG, st, ApiFake(datajud="fx2"), {}, hoje=date(2026, 1, 16), portais=False)
        novas = r2["processos"][0]["novas_movimentacoes"]
        self.assertEqual([m["nome"] for m in novas], ["Audiencia designada"])
        self.assertTrue(any(a["tipo"] == "nova_movimentacao" for a in st2["alertas"]))
        r3, _ = monitor.executar(CFG, st2, ApiFake(datajud="fx2"), {}, hoje=date(2026, 1, 17), portais=False)
        self.assertEqual(r3["processos"][0]["novas_movimentacoes"], [])  # sem alteracao

    def test_djen_novo_vs_conhecido_e_dedup(self):
        itens = fx("djen_items.json")
        r, st = monitor.executar(CFG, {}, ApiFake(djen=itens), {}, hoje=date(2026, 1, 15), portais=False)
        tipos = {a["tipo"] for a in r["alertas_novos"]}
        self.assertEqual(tipos, {"possivel_processo_novo", "comunicacao_processo_conhecido", "processo_conhecido_lido"})
        self.assertTrue(all("A CONFIRMAR" in c["confirmacao"] for c in r["comunicacoes_novas"]))
        r2, _ = monitor.executar(CFG, st, ApiFake(djen=itens), {}, hoje=date(2026, 1, 16), portais=False)
        self.assertEqual(r2["comunicacoes_novas"], [])

    def test_indisponibilidade_nao_vira_sucesso(self):
        api = ApiFake(erro_datajud=FonteIndisponivel("HTTP 503"), erro_djen=FonteIndisponivel("timeout"))
        r, st = monitor.executar(CFG, {}, api, {}, hoje=date(2026, 1, 15), portais=False)
        self.assertEqual(r["status"], "falha")
        self.assertNotIn("ultima_concluida_sucesso_data", st)

    def test_falha_de_autenticacao_sinalizada(self):
        api = ApiFake(erro_datajud=FalhaAutenticacao("HTTP 401"))
        r, _ = monitor.executar(CFG, {}, api, {}, hoje=date(2026, 1, 15), portais=False)
        dj = next(f for f in r["fontes"] if f["fonte"] == "datajud")
        self.assertEqual(dj["status"], "autenticacao")
        self.assertEqual(r["status"], "parcial")

    def test_chave_ausente(self):
        os.environ.pop("DATAJUD_API_KEY", None)
        with self.assertRaises(FonteIndisponivel):
            fontes.datajud_processo(NUM)

    def test_fontes_manuais_nunca_marcadas_como_consultadas(self):
        fcfg = {"fontes": [{"id": "mte", "automacao": "manual", "url": "x"},
                           {"id": "portal", "automacao": "navegador_saude", "url": "y"}]}
        r, _ = monitor.executar(CFG, {}, ApiFake(), fcfg, hoje=date(2026, 1, 15), portais=True)
        st = {f["fonte"]: f["status"] for f in r["fontes"]}
        self.assertEqual(st["mte"], "manual")
        self.assertEqual(st["portal"], "requer_humano")

    def test_termos_busca_sem_duplicata(self):
        t = monitor.termos_busca({"razao_social": "A LTDA", "nome_fantasia": "a ltda", "marcas": ["Marca"]})
        self.assertEqual(t, ["A LTDA", "Marca"])


class TestRelatorioETriagem(unittest.TestCase):
    def test_relatorio_secoes_e_honestidade(self):
        api = ApiFake(djen=fx("djen_items.json"), erro_djen=None)
        r, st = monitor.executar(CFG, {}, api, {"fontes": [{"id": "mte", "automacao": "manual", "url": ""}]},
                                 hoje=date(2026, 1, 15), portais=False)
        md = relatorio.gerar(r, st, CFG, [{"processo": NUM, "ato": "Contestacao", "data_final": "2026-01-20",
                                           "grau_certeza": "MEDIA"}], AGORA)
        for sec in ("RESUMO EXECUTIVO", "NOVOS PROCESSOS IDENTIFICADOS", "PROCESSOS EM ANDAMENTO", "PRAZOS E AUDIENCIAS",
                    "RISCOS E EXPOSICAO", "CONTRATACAO DE ADVOGADO", "PROVIDENCIAS RECOMENDADAS", "LIMITACOES DA VERIFICACAO"):
            self.assertIn(sec, md)
        self.assertIn("NAO consultada (manual)", md)
        self.assertIn("A CONFIRMAR", md)
        self.assertIn("URGENTE", md)

    def test_triagem_urgente_por_prazo_e_audiencia(self):
        t = triagem.classificar({"prazos": [{"data_final": "2026-01-18", "grau_certeza": "MEDIA"}]}, date(2026, 1, 15))
        self.assertEqual(t["classificacao"], triagem.URGENTE)
        t = triagem.classificar({"audiencia": "2026-01-20"}, date(2026, 1, 15))
        self.assertEqual(t["classificacao"], triagem.URGENTE)

    def test_triagem_nunca_dispensa_definitivamente(self):
        t = triagem.classificar({"textos": [], "confirmado": True}, date(2026, 1, 15))
        self.assertEqual(t["classificacao"], triagem.INICIAL)
        self.assertIn("nao dispensa", t["proxima_acao"])
        self.assertEqual(t["confianca"], "baixa")

    def test_triagem_recomendada_por_termo(self):
        t = triagem.classificar({"textos": ["Expedida carta de citacao"]}, date(2026, 1, 15))
        self.assertEqual(t["classificacao"], triagem.RECOMENDADA)

    def test_barreira_portal(self):
        self.assertTrue(portais.detectar_barreira("Complete o reCAPTCHA"))
        self.assertIsNone(portais.detectar_barreira("Consulta processual"))
        # frame de CAPTCHA de terceiro (visto no Projudi/TJBA) deve ser detectado pela URL
        self.assertTrue(portais.detectar_barreira("https://global.turing.captcha.gtimg.com/template/drag.html"))


class TestAgendadorEPrivacidade(unittest.TestCase):
    def test_cli_status_e_run_sem_config_em_dir_temporario(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "JURIDICO_DATA_DIR": d}
            s = subprocess.run([sys.executable, str(ROOT / "scripts" / "monitor.py"), "status"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(s.returncode, 0)
            self.assertIn("Alertas nao reconhecidos: 0", s.stdout)
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "monitor.py"), "run"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)  # sem empresas.json: nao simula pesquisa

    def test_run_completo_offline_gera_relatorio_e_registros(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "empresas.json").write_text(json.dumps({"empresas": []}), encoding="utf-8")
            old = os.environ.get("JURIDICO_DATA_DIR")
            os.environ["JURIDICO_DATA_DIR"] = d
            try:
                monitor.ApiReal.djen = staticmethod(lambda **k: [])
                rc = monitor.main(["run", "--sem-portais"])
            finally:
                monitor.ApiReal.djen = staticmethod(fontes.djen_busca)
                os.environ.pop("JURIDICO_DATA_DIR") if old is None else os.environ.__setitem__("JURIDICO_DATA_DIR", old)
            st = json.loads((Path(d) / "state.json").read_text(encoding="utf-8"))
            self.assertIn("ultima_iniciada", st)
            self.assertEqual(len(list((Path(d) / "relatorios").glob("*.md"))), 1)
            self.assertTrue((Path(d) / "runs.jsonl").exists())
            self.assertEqual(rc, 1)  # nenhuma fonte consultada de fato -> 'falha', nao 'sucesso'

    def test_agendador_ps1_sintaxe(self):
        if os.name != "nt":
            self.skipTest("Windows")
        cmd = "$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile(" \
              f"'{ROOT / 'scripts' / 'agendador.ps1'}',[ref]$null,[ref]$e);if($e){{$e;exit 1}}"
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_gitignore_protege_dados(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for p in ("data/", ".env", "*.pdf", "browser-profile/", "config/empresas.json"):
            self.assertIn(p, gi)

    def test_exemplo_nao_tem_dados_reais(self):
        ex = json.loads((ROOT / "config" / "empresas.example.json").read_text(encoding="utf-8"))
        self.assertEqual(ex["empresas"][0]["cnpj"], "00.000.000/0001-00")


if __name__ == "__main__":
    unittest.main()
