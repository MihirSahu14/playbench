# Implementation notes

**Spike (Task 1, 2026-10-13, Claude Code 2.1.286, Windows 11):**
- **Live run blocked.** `claude -p "/playbench:spike …" --plugin-dir "<repo>"` exited 1 with `Failed to authenticate: OAuth session expired and could not be refreshed`. The live substitution check could not run in this environment. Rerun it after `claude /login` with a throwaway `skills/spike/SKILL.md` whose body is `` !`echo "root=${CLAUDE_PLUGIN_ROOT} skill=${CLAUDE_SKILL_DIR} shell=$0"` ``.
- **Static check of the installed 2.1.286 binary** (the plugin skill loader, `getPromptForCommand`):
  - **Substitution happens before the `!` lines run.** Plugin skill content has `${CLAUDE_PLUGIN_ROOT}` replaced with the plugin path, with backslashes converted to forward slashes. `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_DATA}` and (for skills) `${CLAUDE_SKILL_DIR}` are replaced too.
  - **Which shell runs them.** The frontmatter `shell:` key takes `bash` or `powershell`. When it is absent, the commands run through the Bash tool's shell, which is **Git Bash** on Windows when it is installed, and PowerShell otherwise.
  - **Permissions.** Each command goes through the normal permission check, so `allowed-tools: Bash(python:*), Bash(py:*)` covers the status line.
- **Decision.** The SKILLs keep the planned line, which uses `${CLAUDE_PLUGIN_ROOT}` with quoted paths (the install path contains spaces). If a future version stops substituting it, this fallback works in the same position:
  `` !`python "${CLAUDE_SKILL_DIR}/../../scripts/studio.py" status || py -3 "${CLAUDE_SKILL_DIR}/../../scripts/studio.py" status || echo "playbench: no working Python 3 found"` ``
- **`claude plugin validate . --strict`.** It first warned `No marketplace description provided`. Fixed by adding `metadata.description` to `marketplace.json`, after which it printed `✔ Validation passed`. `claude plugin validate .claude-plugin/plugin.json --strict` passes as well.

**Small deliberate choices:**
- **Debt is counted for the game folder only.** `status` counts debt with `git rev-list --count --since=<at> HEAD -- .`. The `-- .` limits the count to commits touching the game folder, so a game nested inside a bigger repo (like `examples/`) isn't charged for unrelated commits.
- **Git date limit.** Git's date parser rejects years after 2099. The selftest uses 2099 for its "future report" case.
- **`status` always exits 0**, even when `studio.json` is broken. Otherwise the SKILL's `||` chain would fall through and wrongly report "no working Python".
