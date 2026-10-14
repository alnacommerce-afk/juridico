# Fontes oficiais, escopo e limitações

Configuração legível por máquina: `config/fontes.json`. Resultado de cada rodada aparece na seção **LIMITAÇÕES DA VERIFICAÇÃO** do relatório.

| Fonte | Como é usada | Automação | Limitações |
|---|---|---|---|
| DataJud (CNJ) — https://datajud-wiki.cnj.jus.br/api-publica/ | Metadados e movimentos de **processos já conhecidos** (índice por tribunal, `api_publica_<alias>/_search`) | `scripts/fontes.py`; exige `DATAJUD_API_KEY` (chave pública divulgada na wiki do CNJ, pode mudar; sem ela a API responde 401 — verificado) | Não busca por nome de parte; sem conteúdo dos autos; sem sigilosos; pode haver atraso |
| DJEN — https://comunica.pje.jus.br/ | Intimações/publicações por **nome de parte** e nº do processo (API pública `comunicaapi.pje.jus.br`, validada sem login) | Automática | Homônimos; nem todo ato é publicado; resultado = "a confirmar" |
| TST / CSJT / TRTs | Verificação de acessibilidade por Playwright (opcional) | Parcial | Consulta por parte costuma ter CAPTCHA — **não contornado** |
| TJs/TRFs (PJe, e-SAJ, Projudi, eproc) | Consulta manual/assistida pela skill por parte, OAB ou número | Manual | CAPTCHA/login; termos de uso de cada portal |
| MTE (autos de infração/NDFGTS) | Consulta por empregador | Manual | Exige gov.br |
| Receita (e-CAC), Procons, consumidor.gov.br | Notificações/reclamações | Manual | Certificado digital/login da empresa |
| Busca web | Pistas via skill (razão social, nomes anteriores, CNPJ + termos processuais) | Manual (Claude Code) | Nunca é prova |

Princípios: preferir API oficial; navegador só para acesso legítimo; respeitar termos de uso e LGPD; não armazenar senhas/cookies em arquivos versionados; ausência de resultado não certifica inexistência.
