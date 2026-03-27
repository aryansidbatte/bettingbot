# !createbet Flow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add instant creation mode (`!createbet desc | o1 | o2`) and make the multi-step flow edit a single bot message instead of printing a new one per step.

**Architecture:** A pure `parse_instant_bet(args)` helper handles parsing and validation for instant mode — it's easily testable without Discord. The `create_bet` command checks if args were passed to choose the mode. Multi-step uses `bot.wait_for` directly (same logic as `get_reply_or_cancel`) but edits the stored bot message instead of sending new messages.

**Tech Stack:** discord.py 2.6.4, SQLite via `database.py`, pytest

---

### Task 1: `parse_instant_bet` helper + tests

**Files:**
- Modify: `cogs/betting.py` — add `parse_instant_bet` at module level
- Create: `tests/test_betting.py`

- [ ] **Step 1: Create `tests/test_betting.py` with failing tests**

```python
import pytest
from cogs.betting import parse_instant_bet


class TestParseInstantBet:
    def test_valid_two_outcomes(self):
        desc, outcomes = parse_instant_bet("Who wins? | Team A | Team B")
        assert desc == "Who wins?"
        assert outcomes == ["Team A", "Team B"]

    def test_valid_three_outcomes(self):
        desc, outcomes = parse_instant_bet("Best fruit? | Apple | Banana | Cherry")
        assert desc == "Best fruit?"
        assert outcomes == ["Apple", "Banana", "Cherry"]

    def test_strips_whitespace(self):
        desc, outcomes = parse_instant_bet("  Foo?  |  Bar  |  Baz  ")
        assert desc == "Foo?"
        assert outcomes == ["Bar", "Baz"]

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="Description can't be empty"):
            parse_instant_bet(" | A | B")

    def test_one_outcome_raises(self):
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            parse_instant_bet("Foo? | Only one")

    def test_eleven_outcomes_raises(self):
        outcomes = " | ".join(f"O{i}" for i in range(11))
        with pytest.raises(ValueError, match="Maximum 10 outcomes"):
            parse_instant_bet(f"Foo? | {outcomes}")

    def test_empty_outcome_name_raises(self):
        with pytest.raises(ValueError, match="Outcome names can't be empty"):
            parse_instant_bet("Foo? | A | ")

    def test_no_pipe_raises(self):
        with pytest.raises(ValueError, match="at least 2 outcomes"):
            parse_instant_bet("Just a description")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_betting.py -v
```

Expected: `ImportError` — `parse_instant_bet` doesn't exist yet.

- [ ] **Step 3: Add `parse_instant_bet` to `cogs/betting.py`**

Add this function before the `Betting` class:

```python
def parse_instant_bet(args: str) -> tuple:
    """Parse 'description | outcome1 | outcome2 ...' into (description, [outcomes]).
    Raises ValueError with a user-facing message on invalid input.
    """
    parts = [p.strip() for p in args.split("|")]
    description = parts[0]
    outcomes = parts[1:]

    if not description:
        raise ValueError("Description can't be empty.")
    if len(outcomes) < 2:
        raise ValueError("Need at least 2 outcomes.")
    if len(outcomes) > 10:
        raise ValueError("Maximum 10 outcomes.")
    if any(o == "" for o in outcomes):
        raise ValueError("Outcome names can't be empty.")

    return description, outcomes
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source venv/bin/activate && python3 -m pytest tests/test_betting.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cogs/betting.py tests/test_betting.py
git commit -m "feat: add parse_instant_bet helper with tests"
```

---

### Task 2: Instant mode in `create_bet`

**Files:**
- Modify: `cogs/betting.py` — update `create_bet` command signature and add instant path

- [ ] **Step 1: Update the command signature**

Change the existing command signature from:

```python
@commands.command(name="createbet", help="Interactively create a bet with multiple outcomes")
async def create_bet(self, ctx):
```

To:

```python
@commands.command(name="createbet", help="Create a bet: !createbet desc | o1 | o2  or just !createbet for guided setup")
async def create_bet(self, ctx, *, args: str = ""):
```

- [ ] **Step 2: Add instant mode path at the top of `create_bet`**

Add this block immediately after the `async def create_bet(self, ctx, *, args: str = ""):` line, before the existing multi-step logic:

```python
        if args:
            try:
                description, option_names = parse_instant_bet(args)
            except ValueError as e:
                await ctx.send(embed=error_embed(
                    f"{e}\nUsage: `!createbet description | outcome 1 | outcome 2`"
                ))
                return

            c.execute(
                "INSERT INTO bets (guild_id, creator_id, description) VALUES (?, ?, ?)",
                (str(ctx.guild.id), str(ctx.author.id), description),
            )
            conn.commit()
            bet_id = c.lastrowid

            for name in option_names:
                c.execute(
                    "INSERT INTO bet_options (bet_id, name) VALUES (?, ?)",
                    (bet_id, name),
                )
            conn.commit()

            c.execute("SELECT option_id, name FROM bet_options WHERE bet_id=?", (bet_id,))
            options = c.fetchall()
            lines = [f"{idx}. {name}" for idx, (option_id, name) in enumerate(options, start=1)]

            embed = info_embed("🎲 New Bet Created!", "", discord.Color.green())
            embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Outcomes", value="\n".join(lines), inline=False)
            embed.add_field(
                name="How to Bet",
                value="Use `!bet` and follow the prompts to choose this bet and an outcome.",
                inline=False,
            )
            await ctx.send(embed=embed)
            return
```

- [ ] **Step 3: Run the full test suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```

Expected: all tests PASS (existing multi-step tests unaffected since `args` defaults to `""`).

- [ ] **Step 4: Commit**

```bash
git add cogs/betting.py
git commit -m "feat: add instant !createbet mode with pipe syntax"
```

---

### Task 3: Multi-step edit flow

**Files:**
- Modify: `cogs/betting.py` — replace multi-step prompt logic in `create_bet` with edit-based flow

- [ ] **Step 1: Replace the multi-step body in `create_bet`**

Remove everything after the `return` at the end of the instant mode block (i.e. the existing `msg_desc = await get_reply_or_cancel(...)` chain) and replace with:

```python
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        async def ask(prompt_embed):
            """Edit the wizard message with prompt_embed, wait for a reply. Returns content string or None."""
            await wizard_msg.edit(content=None, embed=prompt_embed)
            try:
                msg = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await wizard_msg.edit(
                    embed=error_embed("Timed out. Please run the command again.")
                )
                return None
            if msg.content.strip().lower() == "cancel":
                await wizard_msg.edit(
                    embed=info_embed("❌ Cancelled", "Bet creation cancelled.", discord.Color.orange())
                )
                return None
            return msg.content.strip()

        wizard_msg = await ctx.send(embed=info_embed("🎲 Create a Bet", "Starting…", discord.Color.green()))

        description = await ask(info_embed(
            "🎲 Create a Bet",
            "📝 What is the bet **description**?\nExample: `Who will win the game?`",
            discord.Color.green(),
        ))
        if description is None:
            return

        count_str = await ask(info_embed(
            "🎲 Create a Bet",
            "🔢 How many **outcomes** does this bet have? (minimum 2, maximum 10)",
            discord.Color.green(),
        ))
        if count_str is None:
            return

        try:
            num_outcomes = int(count_str)
        except ValueError:
            await wizard_msg.edit(embed=error_embed("Please enter a valid number (2–10)."))
            return

        if num_outcomes < 2 or num_outcomes > 10:
            await wizard_msg.edit(embed=error_embed("Number of outcomes must be between 2 and 10."))
            return

        option_names = []
        for i in range(1, num_outcomes + 1):
            name = await ask(info_embed(
                "🎲 Create a Bet",
                f"✏️ Enter name for **Outcome #{i}**:",
                discord.Color.green(),
            ))
            if name is None:
                return
            if not name:
                await wizard_msg.edit(embed=error_embed("Outcome name cannot be empty."))
                return
            option_names.append(name)

        c.execute(
            "INSERT INTO bets (guild_id, creator_id, description) VALUES (?, ?, ?)",
            (str(ctx.guild.id), str(ctx.author.id), description),
        )
        conn.commit()
        bet_id = c.lastrowid

        for name in option_names:
            c.execute(
                "INSERT INTO bet_options (bet_id, name) VALUES (?, ?)",
                (bet_id, name),
            )
        conn.commit()

        c.execute("SELECT option_id, name FROM bet_options WHERE bet_id=?", (bet_id,))
        options = c.fetchall()
        lines = [f"{idx}. {name}" for idx, (option_id, name) in enumerate(options, start=1)]

        embed = info_embed("🎲 New Bet Created!", "", discord.Color.green())
        embed.add_field(name="Bet ID", value=f"#{bet_id}", inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Outcomes", value="\n".join(lines), inline=False)
        embed.add_field(
            name="How to Bet",
            value="Use `!bet` and follow the prompts to choose this bet and an outcome.",
            inline=False,
        )
        await wizard_msg.edit(embed=embed)
```

Also add `import asyncio` at the top of `cogs/betting.py` if not already present.

- [ ] **Step 2: Run the full test suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add cogs/betting.py
git commit -m "feat: multi-step !createbet edits a single message instead of sending new ones"
```
