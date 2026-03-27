# !createbet Flow Redesign

**Date:** 2026-03-26
**Status:** Approved

## Summary

Improve `!createbet` with two modes: instant creation via a single piped command, and a multi-step flow that edits a single bot message instead of printing a new message per step.

## Modes

### Instant mode

**Syntax:** `!createbet <description> | <outcome1> | <outcome2> | ...`

- Split input on `|`, strip whitespace from each segment
- First segment = description; remaining segments = outcome names
- On success: create bet in DB, send confirmation embed (same content as today)
- On parse error: send error embed with correct format example

### Multi-step mode

**Trigger:** `!createbet` with no arguments

- Bot sends one initial prompt message and stores the message object
- Each step edits that message with the new prompt (clean replace — no progress history shown)
- Steps: description → outcome count → outcome names one by one
- User replies in the channel; bot reads reply and edits its message for the next step
- On completion: edits the message to the final confirmation embed
- On `cancel`: edits the message to a "Cancelled" embed and stops
- On timeout: edits the message to a "Timed out" embed and stops
- The multi-step flow handles edit logic directly; `get_reply_or_cancel` is not used for this command

## Validation

| Condition | Response |
|-----------|----------|
| Fewer than 2 outcomes | Error: "Need at least 2 outcomes" |
| More than 10 outcomes | Error: "Maximum 10 outcomes" |
| Empty outcome name (e.g. trailing `|`) | Error: "Outcome names can't be empty" |
| Empty description | Error: "Description can't be empty" |
| Non-number or out-of-range outcome count (multi-step) | Error embed, same as today |

## Scope

- Only `create_bet` in `cogs/betting.py` is changed
- `!bet`, `!bets`, `!resolve` are untouched
