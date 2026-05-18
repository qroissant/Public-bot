import os
import sqlite3
import discord
from discord.ext import commands

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN  = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
PREFIX = "!"

# ── Database setup ───────────────────────────────────────────────────────────
conn = sqlite3.connect("tags.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id    TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        description TEXT    NOT NULL,
        created_by  TEXT    NOT NULL,
        UNIQUE(guild_id, name)
    )
""")
conn.commit()

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"   Prefix: {PREFIX}")
    print(f"   Guilds: {len(bot.guilds)}")


# ── !tag ─────────────────────────────────────────────────────────────────────
@bot.group(name="tag", invoke_without_command=True)
async def tag(ctx, *, name: str = None):
    """
    !tag <name>  — show a tag's description
    """
    if name is None:
        embed = discord.Embed(
            title="Tag Commands",
            description=(
                f"`{PREFIX}tag <name>` — show a tag\n"
                f"`{PREFIX}tag setup <name> | <description>` — create/update a tag (Manage Server required)\n"
                f"`{PREFIX}tag list` — list all tags\n"
                f"`{PREFIX}tag delete <name>` — delete a tag (Manage Server required)"
            ),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)
        return

    row = cursor.execute(
        "SELECT description FROM tags WHERE guild_id = ? AND name = ?",
        (str(ctx.guild.id), name.lower()),
    ).fetchone()

    if not row:
        await ctx.send(f"❌ No tag named **{name}** found. Use `{PREFIX}tag list` to see all tags.")
        return

    embed = discord.Embed(
        title=f"🏷️ {name}",
        description=row[0],
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@tag.command(name="setup")
@commands.has_permissions(manage_guild=True)
async def tag_setup(ctx, *, args: str = None):
    """
    !tag setup <name> | <description>  — create or update a tag
    Separate the name and description with a pipe  |
    Example: !tag setup rules | Follow the server rules at all times.
    """
    if not args or "|" not in args:
        await ctx.send(
            f"❌ Wrong format. Use: `{PREFIX}tag setup <name> | <description>`\n"
            f"Example: `{PREFIX}tag setup rules | Follow the server rules at all times.`"
        )
        return

    parts = args.split("|", 1)
    name = parts[0].strip().lower()
    description = parts[1].strip()

    if not name or not description:
        await ctx.send("❌ Both a name and a description are required.")
        return

    cursor.execute(
        """
        INSERT INTO tags (guild_id, name, description, created_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, name) DO UPDATE SET description = excluded.description
        """,
        (str(ctx.guild.id), name, description, str(ctx.author.id)),
    )
    conn.commit()

    embed = discord.Embed(
        title="✅ Tag Saved",
        description=f"**{name}** → {description}",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"Use {PREFIX}tag {name} to show it")
    await ctx.send(embed=embed)


@tag.command(name="list")
async def tag_list(ctx):
    """!tag list — list all tags in this server"""
    rows = cursor.execute(
        "SELECT name FROM tags WHERE guild_id = ? ORDER BY name",
        (str(ctx.guild.id),),
    ).fetchall()

    if not rows:
        await ctx.send(f"❌ No tags set up yet. Use `{PREFIX}tag setup` to create one.")
        return

    names = ", ".join(f"`{r[0]}`" for r in rows)
    embed = discord.Embed(
        title=f"🏷️ Tags in {ctx.guild.name}",
        description=names,
        color=discord.Color.blue(),
    )
    await ctx.send(embed=embed)


@tag.command(name="delete")
@commands.has_permissions(manage_guild=True)
async def tag_delete(ctx, *, name: str):
    """!tag delete <name> — delete a tag"""
    deleted = cursor.execute(
        "DELETE FROM tags WHERE guild_id = ? AND name = ?",
        (str(ctx.guild.id), name.lower()),
    ).rowcount
    conn.commit()

    if deleted == 0:
        await ctx.send(f"❌ No tag named **{name}** found.")
    else:
        await ctx.send(f"✅ Tag **{name}** deleted.")


# ── !add ─────────────────────────────────────────────────────────────────────
@bot.command(name="add")
async def add(ctx, member: discord.Member = None):
    """
    !add @user — move a mentioned user into your current voice channel
    """
    if member is None:
        await ctx.send(f"❌ Mention someone to add. Example: `{PREFIX}add @username`")
        return

    # Check the author is in a voice channel
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("❌ You need to be in a voice channel first.")
        return

    target_channel = ctx.author.voice.channel

    # Check the member is already in the same channel
    if member.voice and member.voice.channel == target_channel:
        await ctx.send(f"❌ **{member.display_name}** is already in your channel.")
        return

    # Check bot permissions
    if not target_channel.permissions_for(ctx.guild.me).move_members:
        await ctx.send("❌ I don't have permission to move members (need **Move Members** permission).")
        return

    # Target must already be in a voice channel to be moved
    if member.voice is None:
        await ctx.send(f"❌ **{member.display_name}** is not in any voice channel right now. They need to join one first.")
        return

    await member.move_to(target_channel)
    embed = discord.Embed(
        description=f"✅ Moved **{member.display_name}** to **{target_channel.name}**.",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)


# ── !help ────────────────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="📖 Bot Commands",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="🏷️ Tags",
        value=(
            f"`{PREFIX}tag <name>` — show a tag\n"
            f"`{PREFIX}tag setup <name> | <desc>` — create/update tag *(Manage Server)*\n"
            f"`{PREFIX}tag list` — list all tags\n"
            f"`{PREFIX}tag delete <name>` — delete tag *(Manage Server)*"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔊 Voice",
        value=f"`{PREFIX}add @user` — move someone into your voice channel",
        inline=False,
    )
    embed.add_field(
        name="ℹ️ Other",
        value=f"`{PREFIX}help` — show this message",
        inline=False,
    )
    embed.set_footer(text=f"Prefix: {PREFIX}")
    await ctx.send(embed=embed)


# ── Error handling ───────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found. Make sure you @mention them.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Silently ignore unknown commands
    else:
        await ctx.send(f"❌ An error occurred: {error}")


# ── Run ──────────────────────────────────────────────────────────────────────
bot.run(TOKEN)
