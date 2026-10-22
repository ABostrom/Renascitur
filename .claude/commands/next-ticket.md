---
description: Pull the next History Engine ticket from GitHub, do it, and report back on the issue
---

You are working the Renascitur History Engine backlog on GitHub (ABostrom/Renascitur, public).
Integration branch: `feat/history-engine`. Master spec: `notes/specs/2026-10-21-history-engine-design.md`.
Sub-project specs and plans live in `notes/specs/`.

**The spirit of this loop:**
- **This is Aaron's personal tool, so keep the ceremony low.** Make the sensible call, write it down
  on the ticket, and keep going.
- **Ordering is loose.** Milestones and ticket boundaries are a rough guide that will blur as the
  work goes. Merge, split, re-scope, or close tickets as superseded whenever that's the honest
  shape of the work.
- **Focus on the engine.** It is world-agnostic(ish), and Renascita lore is just data it loads.
- **Formats:** JSON everywhere and no pickle. Choose clarity over speed; a Rust rewrite may come
  much later.

Do roughly one ticket per run. A run may close several small ones, or a few closely related ones,
when it's natural to do them together.

Aaron and you post from the same GitHub account. Start every comment you write with `🤖`. A comment
without `🤖` is from Aaron and is an instruction.

## 1. Aaron's comments first

Check the pinned `Review queue` issue and any open `needs-aaron` tickets for comments without `🤖`
that are newer than your last `🤖` comment. Act on them before anything else. Copy an answer given on
the queue onto the ticket it concerns.

## 2. Pick the next piece of work

    gh issue list --state open --label S1 --json number,title,labels,milestone --limit 100   # or the current sub-project

Choose the most useful next **engine** ticket whose prerequisites already exist in the code. Prefer
the current milestone, but don't be strict about it. Skip `lore` unless Aaron has asked for it by
number. Skip `in-progress` tickets. Use the `ready` label loosely, as a hint, not a gate.
Claim the ticket by adding `in-progress` and posting a short `🤖` comment.

## 3. Do the work

- **build**:
  - Use `superpowers:test-driven-development`. Branch `ticket/<n>-<slug>` off `feat/history-engine`.
    Use Python 3.12 via `uv`.
  - Make the full suite pass, and use `superpowers:verification-before-completion`.
  - Run a code-review subagent on the diff. Fix the real findings and note any you left.
  - Merge `--no-ff` into `feat/history-engine`, push, delete the branch, comment (what changed, the
    test summary, and any decisions you made), then close.
  - Never leave red tests on `feat/history-engine`.
- **spec / plan**:
  - Write it under `notes/specs/` and have an independent reviewer subagent check it. Fix what you
    agree with, commit, comment, and close. **Don't wait for approval.** Aaron reads it when they
    want to, and comments if they disagree.
  - Keep plans light: a working order and the risky bits. Don't rewrite tickets for ritual.
- **A genuine Aaron decision:** taste, canon, or something hard to undo. Don't stop. Choose a
  reversible default, proceed, and add the question to the review queue. Use `needs-aaron` only when
  no sensible default exists.

## 4. Report

- Remove `in-progress`.
- Keep the **review queue** body short. It lists only open questions with your recommended answers,
  plus an FYI list of decisions you made that Aaron might want to overrule. Drop answered items.
- In the terminal, give three lines: what you did, decisions made, and anything waiting on Aaron.

## 5. Pacing (when run under /loop)

- Engine work remains: schedule the next run soon (60–120 s).
- Only questions remain: wait 1800 s.
- Nothing left: stop the loop and say so.

## Never

- Push to `master`, force-push, or rewrite history.
- Commit `images/Renascitur.png` or anything private. Issues and commits are public.
- Set `canon: true` or invent canon beyond a clearly marked draft.
