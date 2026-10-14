# Monitoramento diário (08:00, America/Sao_Paulo)

## Escolha do agendador
- **Windows Task Scheduler (adotado):** roda localmente, mantém dados privados em `data/`, permite sessão/perfil autorizado para portais. Requer PC ligado (ou executa ao ligar: `StartWhenAvailable`).
- **GitHub Actions: NÃO usado.** O repositório é público e a rotina lida com dados sensíveis; não se movem credenciais/documentos para pipeline público.
- Cron: só se migrar para Linux/macOS (`0 8 * * * TZ=America/Sao_Paulo python scripts/monitor.py run`).

## Configuração
1. `copy config\empresas.example.json data\empresas.json` e preencher (razão social, CNPJ, aliases, processos conhecidos). Esse arquivo é ignorado pelo Git.
2. DataJud: obter a chave pública na wiki do CNJ e definir `DATAJUD_API_KEY` (variável de ambiente do usuário: `setx DATAJUD_API_KEY "<chave>"`). Sem ela a fonte aparece como "NÃO CONFIGURADA".
3. Playwright (Microsoft; instalado nesta máquina, v1.64, `python -m playwright ...`): `pip install playwright` e `python -m playwright install chromium`. Usado para abrir portais e ler páginas; ao encontrar CAPTCHA/login (ex.: consulta pública do Projudi/TJBA, CAPTCHA deslizante) **para e pede intervenção humana** — não contorna.
4. Testar sem instalar: `powershell -ExecutionPolicy Bypass -File scripts\agendador.ps1 -Acao testar`
5. Instalar: `powershell -ExecutionPolicy Bypass -File scripts\agendador.ps1 -Acao instalar` (ajuste `-Hora` se o fuso do Windows não for Brasília; o script avisa).

## Verificar / alertas / desativar
- Status: `scripts\agendador.ps1 -Acao status` e `python scripts/monitor.py status` (última execução **iniciada**, última **concluída com sucesso** [todas as fontes automáticas ok], alertas não reconhecidos).
- Relatórios: `data/relatorios/AAAA-MM-DD.md`; histórico: `data/runs.jsonl`; estado/alertas: `data/state.json`.
- Reconhecer alertas: `python scripts/monitor.py ack <id|todos>`.
- Canais de notificação realmente implementados: **arquivo de alertas + `status`**. Não há e-mail/push configurado (exigiria credenciais; não incluído).
- Desativar: `scripts\agendador.ps1 -Acao remover`.

## Registros separados
`ultima_iniciada` · `ultima_concluida_sucesso` · `ultima_status` (completa | parcial | falha | erro_técnico) · fontes por execução (`runs.jsonl`) · alertas `reconhecido: false`.

## Limites
Fontes manuais (gov.br, e-CAC, portais com CAPTCHA, busca web) **não** são consultadas pelo agendador; aparecem como "NÃO consultada (manual)". Faça-as pela skill no Claude Code.
