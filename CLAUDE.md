# Project rules

## Git
- Never run `git push --force` (or `--force-with-lease`) without explicit user confirmation in the same message.
- Always show the exact push command and ask the user to approve before running it.
- Commit `.env` files is strictly forbidden — `.env` must always be in `.gitignore`.
