<!-- owner-model:generated — do not edit. The shared rules come from the owner
     model; put anything specific to this repository in AGENTS.local.md
     and it is preserved across updates. -->

# Working agreements

- NOTES.md is this project's working memory. Capture tasks under `## Now`,
  open questions under `## Questions`. Items under `## For me` are reserved
  for the owner — never execute them.
- State what you verified and how. Unrun code is "unverified", not "works".
- The project's purpose and constraints live in the console's Project
  context — read it before large changes.
- Do not prefix a command with environment variables (`FOO=1 python3 x.py`).
  Permission rules match the start of the command, so the prefix hides the
  real one and an allowed command is refused. Take configuration as a CLI
  flag or read it from a file instead.
