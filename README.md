# JURÍDICO ALNA

Skill do Claude Code + rotina local de monitoramento jurídico empresarial (processos contra as empresas cadastradas, movimentações, prazos, triagem sobre contratação de advogado). **Auxilia; não substitui advogado e não garante resultados.**

> **Repositório público.** Contém apenas código, modelos e documentação. Dados reais (empresas, processos, PDFs, relatórios, credenciais) ficam em `data/` (no `.gitignore`) ou em `JURIDICO_DATA_DIR`.

## Requisitos
Python 3.10+ (somente biblioteca padrão). Opcional: `pip install playwright && playwright install chromium` (verificação de portais). Windows para o agendador incluído.

## Uso rápido
```
copy config\empresas.example.json data\empresas.json     # preencher
setx DATAJUD_API_KEY "<chave publica do CNJ>"            # DataJud
python scripts/monitor.py run                             # consulta + relatório em data/relatorios/
python scripts/monitor.py status
powershell -ExecutionPolicy Bypass -File scripts\agendador.ps1 -Acao instalar   # 08:00 diário
python -m unittest discover -s tests -v                   # testes (dados sintéticos)
```
No Claude Code, a skill fica em `.claude/skills/juridico-alna/SKILL.md` (acione com `/juridico-alna` ou descrevendo o caso).

## Estrutura
`scripts/` (monitor, fontes DataJud/DJEN, prazos, triagem, relatório, agendador) · `config/` · `docs/` · `tests/`.

## Limitações
- Automático: DataJud (processos **conhecidos**, com chave) e DJEN (busca por nome, com homônimos). Demais fontes (gov.br, e-CAC, TJs com CAPTCHA, busca web) são manuais/assistidas pela skill e **não contornam CAPTCHA/login**.
- Ausência de resultados não certifica inexistência de processos. Prazos calculados exigem conferência por advogado.
- Notificações: apenas arquivo de alertas/`status`.
- Respeite termos de uso dos portais e a LGPD.

Docs: [fontes](docs/fontes-oficiais.md) · [prazos](docs/prazos-processuais.md) · [triagem](docs/triagem-advogado.md) · [monitoramento](docs/monitoramento-diario.md)
