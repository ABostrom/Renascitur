---
description: Pull the next ready History Engine ticket from GitHub, do it, and report back on the issue
---

You are working the Renascitur History Engine backlog on GitHub (ABostrom/Renascitur, public).
Do **one ticket per run**. The master spec is `notes/specs/2026-10-21-history-engine-design.md`;
the backlog generator is `notes/specs/backlog.py`. Integration branch: `feat/history-engine`.

Aaron and you post from the same GitHub account. Start every comment you write with `🤖`.
A comment without `🤖` is from Aaron and is an instruction.

## 1. Answers first

Look at open issues labelled `needs-aaron`:

    gh issue list --label needs-aaron --state open --json number,title
    gh issue view <n> --comments

If Aaron has commented (no `🤖`) since your last `🤖` comment, that ticket is your work for this run.
Remove `needs-aaron`, act on what they said (revise, finish, or close), then go to step 5.

## 2. Pick a ticket

    gh issue list --label ready --state open --json number,title,labels,milestone --limit 100

Skip anything labelled `in-progress`, `needs-aaron` or `blocked`. Of the rest, take the one in the
earliest milestone (M0 < M1 < … < M7b). Break ties with `spec`/`plan` before `build`, then `lore`, then
the lowest number. Read the issue and its parent epic. If nothing is left, go to step 6.

Claim it: `gh issue edit <n> --add-label in-progress` and post a `🤖 Picking this up.` comment.

## 3. Do the work, by ticket kind

- **lore**: Aaron owns the canon. Draft into `notes/` (or a vault note with `canon: proposed`), read
  the relevant vault notes first, never mark anything `canon: true`. Commit to `feat/history-engine`.
  Comment with a summary, the file path and numbered questions. Label `needs-aaron`. Do not close.
- **spec** (review or write a spec): write or update it under `notes/specs/`, self-review it, commit,
  comment with a summary and the open decisions. Label `needs-aaron`. Close only after they approve.
- **plan**: needs an approved spec. Use the `superpowers:writing-plans` skill and write to
  `notes/specs/plans/`. When it's committed, refresh that sub-project's `build` tickets so they match the
  plan: edit their bodies and create missing tickets via `backlog.py` conventions. Mark the first
  buildable ones `ready`. Comment and close.
- **build**: use `superpowers:test-driven-development`. Branch `ticket/<n>-<slug>` off
  `feat/history-engine`. Python 3.12 via `uv`. Run the full test suite and use
  `superpowers:verification-before-completion`. Merge into `feat/history-engine` with `--no-ff`, push,
  delete the branch, then comment with what changed and the test output summary and close the issue.
  If you're stuck, revert to the comment-and-`needs-aaron` path. Never leave red tests on
  `feat/history-engine`.

## 4. Unblock

When a ticket closes, check the epic's sub-issues. Mark a ticket `ready` (and remove `blocked`) when
everything it depends on (per its body, its epic and the spec's dependency order) is closed.

## 5. Report

Remove `in-progress`. In the terminal, give three lines: the ticket, what you did, and what's waiting on Aaron.

## 6. Pacing (when run under /loop)

- If you finished a ticket and more `ready` work exists, schedule the next run soon (60–120 s).
- If the only remaining work is `needs-aaron`, schedule a long wakeup (1800 s) to check for their replies.
- If there is nothing `ready` and nothing `needs-aaron`, stop the loop and say so.

## Never

- Push to `master`, force-push, or rewrite history.
- Commit `images/Renascitur.png` or anything private. Issues and commits are public.
- Set `canon: true`, close a `lore` or spec-review ticket without Aaron's approval, or invent canon
  beyond a clearly marked draft.
- Work on more than one ticket per run.
