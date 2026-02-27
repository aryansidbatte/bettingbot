import discord
import asyncio

def info_embed(title: str, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

def error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Error",
        description=message,
        color=discord.Color.red()
    )

async def get_reply_or_cancel(bot, ctx, prompt: str, timeout: float = 60.0):
    """Send a prompt, wait for reply from same user/channel, support 'cancel'."""
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send(prompt + "\n\nType `cancel` to cancel.")
    try:
        msg = await bot.wait_for("message", timeout=timeout, check=check)
    except asyncio.TimeoutError:
        await ctx.send(embed=error_embed("Timed out. Please run the command again."))
        return None

    content = msg.content.strip()
    if content.lower() == "cancel":
        await ctx.send(
            embed=info_embed("❌ Cancelled", "Command has been cancelled.", discord.Color.orange())
        )
        return None

    return msg
