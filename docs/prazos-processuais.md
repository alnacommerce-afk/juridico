# Prazos processuais — metodologia

`scripts/prazos.py` é **auxiliar**. Todo prazo exige conferência por advogado (`conferencia_advogado: true` sempre).

## Regras implementadas
- **Dias úteis** (CPC art. 219; Lei 9.099/95 art. 12-A nos Juizados) ou **corridos**.
- **CPC art. 224:** exclui o dia do começo, inclui o do vencimento; o prazo começa no primeiro dia útil seguinte ao marco; vencimento em dia sem expediente prorroga.
- **Publicação no DJe:** considera-se publicada no 1º dia útil seguinte à disponibilização (`marco_publicacao_dje`).
- **Feriados:** nacionais fixos + Sexta-feira Santa. Feriados locais/estaduais/atos do tribunal e a suspensão do CPC art. 220 (20/12–20/01, `aplicar_suspensao_cpc_220`) devem ser informados — **não são presumidos**.
- Carnaval, Quarta de Cinzas, Corpus Christi e 28/10 variam por tribunal: não são aplicados, mas aparecem na memória de cálculo como "datas a conferir".

## Marco inicial (conferir sempre — CPC art. 231 e Lei 9.099 art. 18)
Registre qual evento e por quê: juntada do AR/mandado cumprido, ciência no sistema, publicação, término do prazo de consulta etc. **Data de expedição de citação ≠ data de citação efetiva.** Sem documento que prove o marco ⇒ `marco=None` ou `marco_confirmado=False` ⇒ **"PRAZO A CONFIRMAR URGENTEMENTE"**, sem data afirmada como certa.

## Registro (`data/prazos.json`)
`processo, ato, fonte, marco, justificativa_marco, regra, tipo (uteis/corridos), dias, data_final, grau_certeza, conferencia_advogado, responsavel, situacao` (pendente | em preparação | concluído | vencido | aguardando confirmação). O cálculo nunca declara "vencido" com certeza: usa "possivelmente vencido (confirmar com advogado)".
