import os
import sqlite3
import asyncio
import discord
from discord.ext import commands

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing!")

# ── Database setup ───────────────────────────────────────────────────────────
conn = sqlite3.connect("tags.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        created_by TEXT NOT NULL,
        UNIQUE(guild_id, name)
    )
""")

conn.commit()

# ── Bot setup ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ── Events ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Connected to {len(bot.guilds)} servers")


# ── TAG COMMANDS ─────────────────────────────────────────────────────────────
@bot.group(name="tag", invoke_without_command=True)
async def tag(ctx, *, name: str = None):

    if name is None:
        embed = discord.Embed(
            title="🏷️ Tag Commands",
            description=(
                f"`{PREFIX}tag <name>` → Show a tag\n"
                f"`{PREFIX}tag setup <name> | <description>` → Create/update tag\n"
                f"`{PREFIX}tag list` → List tags\n"
                f"`{PREFIX}tag delete <name>` → Delete tag"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)
        return

    row = cursor.execute(
        "SELECT description FROM tags WHERE guild_id = ? AND name = ?",
        (str(ctx.guild.id), name.lower())
    ).fetchone()

    if not row:
        await ctx.send(f"❌ Tag `{name}` not found.")
        return

    embed = discord.Embed(
        title=f"🏷️ {name}",
        description=row[0],
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed)


@tag.command(name="setup")
@commands.has_permissions(manage_guild=True)
async def tag_setup(ctx, *, args: str = None):

    if not args or "|" not in args:
        await ctx.send(
            f"❌ Usage:\n`{PREFIX}tag setup rules | Follow the rules.`"
        )
        return

    name, description = map(str.strip, args.split("|", 1))

    if not name or not description:
        await ctx.send("❌ Name and description required.")
        return

    name = name.lower()

    cursor.execute("""
        INSERT INTO tags (guild_id, name, description, created_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, name)
        DO UPDATE SET description = excluded.description
    """, (
        str(ctx.guild.id),
        name,
        description,
        str(ctx.author.id)
    ))

    conn.commit()

    embed = discord.Embed(
        title="✅ Tag Saved",
        description=f"**{name}** → {description}",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed)


@tag.command(name="list")
async def tag_list(ctx):

    rows = cursor.execute(
        "SELECT name FROM tags WHERE guild_id = ? ORDER BY name",
        (str(ctx.guild.id),)
    ).fetchall()

    if not rows:
        await ctx.send("❌ No tags found.")
        return

    tags = "\n".join(f"• `{r[0]}`" for r in rows)

    embed = discord.Embed(
        title=f"🏷️ Tags in {ctx.guild.name}",
        description=tags,
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed)


@tag.command(name="delete")
@commands.has_permissions(manage_guild=True)
async def tag_delete(ctx, *, name: str):

    deleted = cursor.execute(
        "DELETE FROM tags WHERE guild_id = ? AND name = ?",
        (str(ctx.guild.id), name.lower())
    ).rowcount

    conn.commit()

    if deleted:
        await ctx.send(f"✅ Deleted tag `{name}`")
    else:
        await ctx.send(f"❌ Tag `{name}` not found.")


# ── ADD COMMAND ──────────────────────────────────────────────────────────────
@bot.command(name="add")
async def add(ctx, member: discord.Member = None):

    if member is None:
        await ctx.send(f"❌ Usage: `{PREFIX}add @user`")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ You must be in a voice channel.")
        return

    target_channel = ctx.author.voice.channel

    if member.voice and member.voice.channel == target_channel:
        await ctx.send(f"❌ {member.display_name} is already in your VC.")
        return

    # FIXED
    if not target_channel.permissions_for(ctx.me).move_members:
        await ctx.send("❌ I need Move Members permission.")
        return

    if not member.voice:
        await ctx.send(f"❌ {member.display_name} is not in a VC.")
        return

    try:
        await member.move_to(target_channel)

        embed = discord.Embed(
            description=f"✅ Moved {member.mention} to **{target_channel.name}**",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to move that user.")

    except Exception as e:
        await ctx.send(f"❌ Error: {e}")


# ── HELP ─────────────────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):

    embed = discord.Embed(
        title="📖 Commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🏷️ Tags",
        value=(
            f"`{PREFIX}tag <name>`\n"
            f"`{PREFIX}tag setup <name> | <desc>`\n"
            f"`{PREFIX}tag list`\n"
            f"`{PREFIX}tag delete <name>`"
        ),
        inline=False
    )

    embed.add_field(
        name="🔊 Voice",
        value=f"`{PREFIX}add @user`",
        inline=False
    )

    await ctx.send(embed=embed)


# ── ERROR HANDLER ────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission.")

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found.")

    elif isinstance(error, commands.CommandNotFound):
        return

    else:
        print(error)
        await ctx.send(f"❌ Error: {error}")


# ── RUN ──────────────────────────────────────────────────────────────────────
if os.name == "nt":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

bot.run(TOKEN)
