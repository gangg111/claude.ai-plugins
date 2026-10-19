# claude.ai-plugins

## tool-testing

Hook PostToolUse (Write/Edit) dla narzędzi Pythona w `tools/`:
- brak testu albo czerwony test → blokada z komunikatem dla agenta,
- zmiana istniejącej asercji → zgłoszenie,
- wszystkie testy pominięte → nie liczy się jako zielony.

Komunikaty odsyłają do skilla `tool-testing` (zapisanego na koncie claude.ai).

Instalacja:

```
/plugin marketplace add gangg111/claude.ai-plugins
/plugin install tool-testing@gangg111-plugins
```

Wymaga `python3` z zainstalowanym `pytest`.
Windows: komenda hooka to `python3`; jeśli u Ciebie działa tylko `py -3.12`, zostań przy lokalnej instalacji w `~/.claude/hooks` i nie instaluj pluginu, bo hook uruchomiłby się dwa razy.
