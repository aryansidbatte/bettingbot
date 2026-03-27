# !bet and !resolve Flow Redesign

**Date:** 2026-03-26
**Status:** Approved

## Summary

Migrate `!bet` and `!resolve` to the same two-mode pattern introduced for `!createbet`: instant mode via positional args, and an edit-based wizard that edits a single bot message instead of sending new messages per step. Also fix the `!createbet` error message to show both syntaxes.

---

## !bet

### Instant mode

**Syntax:** `!bet <bet_id> <outcome_number> <amount>`

- All three args must be provided together; partial args (1 or 2) → error showing both syntaxes
- Validations: bet exists and is open, user hasn't already bet on this bet, outcome number in range, amount positive, sufficient balance
- On success: deduct points, insert wager, send confirmation embed

### Multi-step wizard

**Trigger:** `!bet` with no arguments

- Bot sends one message upfront (`wizard_msg`), edits it for each step (clean replace)
- Step 1: list open bets, ask for bet ID → validate bet exists, is open, user hasn't already bet
- Step 2: list outcomes with pools, ask for outcome number → validate in range
- Step 3: ask for amount → validate positive and sufficient balance
- `cancel` or timeout → edit `wizard_msg` with cancelled/timed out embed
- On completion: edit `wizard_msg` with confirmation embed

### Error message (both modes)

```
Usage:
• !bet <bet_id> <outcome_number> <amount>
• Or just !bet for guided setup
```

---

## !resolve

### Instant mode

**Syntax:** `!resolve <bet_id> <outcome_num>`

- Both args must be provided together; `!resolve <bet_id>` alone → error showing both syntaxes
- Validations: bet exists and is open, user is the bet creator, outcome number in range
- On success: distribute winnings, close bet

### Wizard mode

**Trigger:** `!resolve` with no arguments

- Check user's open bets in this guild:
  - **0 bets** → error: "You have no open bets to resolve."
  - **1 bet** → send `wizard_msg`, go straight to outcome picker (no bet selector step)
  - **2+ bets** → send `wizard_msg`, list user's open bets, ask for bet ID, then edit for outcome picker
- `cancel` or timeout → edit `wizard_msg` with cancelled/timed out embed
- On completion: edit `wizard_msg` with result embed

### Error message (both modes)

```
Usage:
• !resolve <bet_id> <outcome_number>
• Or just !resolve for guided setup
```

---

## !createbet fix

Update the instant-mode error message in `create_bet` to show both syntaxes:

```
Usage:
• !createbet description | outcome 1 | outcome 2
• Or just !createbet for guided setup
```

---

## Scope

- Only `place_bet`, `resolve_bet`, and the error message in `create_bet` in `cogs/betting.py` are changed
- `get_reply_or_cancel` will no longer be used after this change and its import can be removed
- No changes to `view_bets`, horserace, bigrace, economy, or vcrewards
