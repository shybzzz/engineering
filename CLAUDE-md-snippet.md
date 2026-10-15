# Фрагмент для ~/.claude/CLAUDE.md (необов'язково)

Скіл `save-skill` з плагіна `toolkit` вже вміє обробляти фразу «збережи цей скіл у хмарі».
Якщо хочеш продублювати правило глобально (працюватиме навіть без встановленого плагіна),
додай цей блок у свій `~/.claude/CLAUDE.md`:

```markdown
## Мій маркетплейс скілів

Мій особистий маркетплейс: https://github.com/YOUR-GITHUB-USERNAME/engineering
(локальна копія: ~/engineering, скіли — у plugins/toolkit/skills/).

Коли я кажу «збережи цей скіл у хмарі» (або «збережи в маркетплейс», «зроби з цього скіл»):
1. Онови/клонуй локальну копію репозиторію.
2. Створи plugins/toolkit/skills/<kebab-case-назва>/SKILL.md з frontmatter (name, description
   з тригер-фразами) та чіткими інструкціями для моделі.
3. Підніми version у plugins/toolkit/.claude-plugin/plugin.json.
4. git add -A && git commit && git push (без force push).
5. Скажи мені назву скіла і нагадай про /plugin marketplace update на інших машинах.
```
