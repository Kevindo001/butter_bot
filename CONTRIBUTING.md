# Contributing

Git etiquette for this repo. Applies to everyone working on Butter.

## Branches

| Branch        | Purpose                                                         |
|----------------|------------------------------------------------------------------|
| `main`         | Stable only. Never push directly. Merges in from `dev` when stable. |
| `dev`          | Integration branch. Feature/fix/etc. branches merge here first.  |
| `feat/xxx`     | New functionality.                                                |
| `fix/xxx`      | Bug fixes.                                                        |
| `chore/xxx`    | Maintenance, deps, scaffolding — no behavior change.              |
| `docs/xxx`     | Documentation only.                                               |
| `refactor/xxx` | Restructuring code with no behavior change.                       |

Branch off `dev` for new work: `git checkout -b feat/wake-word-threshold dev`

## Commit messages

Conventional commits: `<type>: <description>`

Allowed types: `feat`, `fix`, `docs`, `chore`, `refactor`

Examples:

```
feat: add rotate tool to Brain action set
fix: correct reversed left-rear wheel wiring
docs: document TTS pipeline in voice.md
chore: bump piper-tts to 1.4.0
refactor: extract sox pipeline into shared helper
```

Commit at every working milestone, not just when a feature is fully done. Small, frequent commits are preferred over one large commit at the end.

## Never commit

- `.env`
- `models/*.onnx`
- `butter_env/`
- `cache/`

All four are gitignored — if `git status` shows one of these as trackable, stop and check `.gitignore` before adding it.

## Pull before push

Always `git pull` (or `git pull --rebase`) before pushing, to catch conflicts early and avoid needing a force push.

## Merging up

1. Open a PR from `feat/xxx` (or `fix/xxx`, etc.) into `dev`.
2. Once `dev` is stable, open a PR from `dev` into `main`.
3. Never merge a feature branch directly into `main`.
