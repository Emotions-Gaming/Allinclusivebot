import discord
from discord.ext import commands
from discord import app_commands

from utils import load_json, save_json, is_admin, has_role, has_any_role

SCHICHT_CONFIG_FILE = "schicht_config.json"
SCHICHT_RIGHTS_FILE = "schicht_rights.json"

def get_schicht_cfg():
    return load_json(SCHICHT_CONFIG_FILE, {
        "text_channel_id": None,
        "voice_channel_id": None,
        "log_channel_id": None,
        "rollen": []
    })

def save_schicht_cfg(data):
    save_json(SCHICHT_CONFIG_FILE, data)

def get_rights():
    return set(load_json(SCHICHT_RIGHTS_FILE, []))

def save_rights(s):
    save_json(SCHICHT_RIGHTS_FILE, list(s))

class SchichtCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Setze Schicht-Voice/Log/Role-Konfig
    @app_commands.command(name="schichtsetvoice", description="Setzt den Voice-Kanal für Schichtübergaben")
    @app_commands.describe(channel="Voice-Kanal")
    async def schichtsetvoice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        cfg["voice_channel_id"] = channel.id
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Voice-Kanal gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetlog", description="Setzt den Log-Channel für Schichtübergaben")
    @app_commands.describe(channel="Log-Channel")
    async def schichtsetlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        cfg["log_channel_id"] = channel.id
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Log-Channel gesetzt: {channel.mention}", ephemeral=True)

    @app_commands.command(name="schichtsetrolle", description="Fügt eine berechtigte Rolle für Schichtübergaben hinzu")
    @app_commands.describe(role="Rolle, die Schichtübergabe machen darf")
    async def schichtsetrolle(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        rollen = set(cfg.get("rollen", []))
        rollen.add(role.id)
        cfg["rollen"] = list(rollen)
        save_schicht_cfg(cfg)
        await interaction.response.send_message(f"Rolle {role.mention} darf jetzt Schichtübergaben machen.", ephemeral=True)

    @app_commands.command(name="schichtremoverolle", description="Entfernt eine berechtigte Rolle für Schichtübergaben")
    @app_commands.describe(role="Rolle entfernen")
    async def schichtremoverolle(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)
        cfg = get_schicht_cfg()
        rollen = set(cfg.get("rollen", []))
        if role.id in rollen:
            rollen.remove(role.id)
            cfg["rollen"] = list(rollen)
            save_schicht_cfg(cfg)
            await interaction.response.send_message(f"Rolle {role.mention} kann jetzt **nicht mehr** Schichtübergaben machen.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Rolle {role.mention} war nicht berechtigt.", ephemeral=True)

    @app_commands.command(name="schichtinfo", description="Infos & Anleitung zum Schichtsystem")
    async def schichtinfo(self, interaction: discord.Interaction):
        cfg = get_schicht_cfg()
        rollen = cfg.get("rollen", [])
        guild = interaction.guild
        rollen_txt = " / ".join([guild.get_role(rid).mention for rid in rollen if guild.get_role(rid)]) if rollen else "_Keine Rollen festgelegt_"
        log_channel = guild.get_channel(cfg.get("log_channel_id")) if cfg.get("log_channel_id") else None
        voice_channel = guild.get_channel(cfg.get("voice_channel_id")) if cfg.get("voice_channel_id") else None
        emb = discord.Embed(
            title="👥 Schichtübergabe-System",
            description="Hier können berechtigte Nutzer Schichtübergaben direkt im Voice durchführen.",
            color=discord.Color.blurple()
        )
        emb.add_field(name="Wer darf Übergaben machen?", value=rollen_txt, inline=False)
        emb.add_field(name="Voice-Kanal", value=voice_channel.mention if voice_channel else "_Nicht gesetzt_", inline=True)
        emb.add_field(name="Log-Channel", value=log_channel.mention if log_channel else "_Nicht gesetzt_", inline=True)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    # --- Schichtübergabe Mainpost (optional) ---
    @app_commands.command(name="schichtmain", description="Postet das Schichtübergabe-Panel im aktuellen Channel")
    async def schichtmain(self, interaction: discord.Interaction):
        cfg = get_schicht_cfg()
        rollen = cfg.get("rollen", [])
        guild = interaction.guild
        rollen_txt = " / ".join([guild.get_role(rid).mention for rid in rollen if guild.get_role(rid)]) if rollen else "_Keine Rollen festgelegt_"
        emb = discord.Embed(
            title="🔄 Schichtübergabe-System",
            description="Drücke auf **Schichtübergabe starten**, um eine Schichtübergabe mit Voice-Move zu machen.\n\n"
                        f"Berechtigte Rollen: {rollen_txt}\n\n"
                        "Die Übergabe wird im Log vermerkt.",
            color=discord.Color.green()
        )
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="Schichtübergabe starten", style=discord.ButtonStyle.primary)
        async def btn_cb(inter):
            # User muss Rolle haben
            rollen = set(get_schicht_cfg().get("rollen", []))
            if not any(r.id in rollen for r in inter.user.roles) and not is_admin(inter.user):
                return await inter.response.send_message("Du bist nicht berechtigt!", ephemeral=True)
            # Öffne Modal mit User-Dropdown
            options = []
            for m in inter.guild.members:
                if m.bot: continue
                if any(r.id in rollen for r in m.roles):
                    options.append(discord.SelectOption(label=m.display_name, value=str(m.id)))
            if not options:
                return await inter.response.send_message("Kein berechtigter Nutzer online.", ephemeral=True)
            view2 = discord.ui.View(timeout=60)
            select = discord.ui.Select(placeholder="Wen übergeben?", options=options, min_values=1, max_values=1)
            async def sel_cb(sel_inter):
                target_id = int(sel_inter.data["values"][0])
                target = inter.guild.get_member(target_id)
                if not target:
                    return await sel_inter.response.send_message("Nutzer nicht gefunden!", ephemeral=True)
                # Beide müssen im Voice sein
                if not inter.user.voice or not inter.user.voice.channel:
                    return await sel_inter.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
                if not target.voice or not target.voice.channel:
                    try:
                        await target.send(f"{inter.user.display_name} möchte dir die Schicht übergeben, aber du bist nicht im Sprachkanal!")
                    except Exception:
                        pass
                    return await sel_inter.response.send_message(f"{target.mention} ist nicht im Sprachkanal! (DM wurde versucht)", ephemeral=True)
                # Beide moven
                v_id = get_schicht_cfg().get("voice_channel_id")
                log_id = get_schicht_cfg().get("log_channel_id")
                if not v_id:
                    return await sel_inter.response.send_message("VoiceMaster-Kanal nicht gesetzt!", ephemeral=True)
                voice_ch = inter.guild.get_channel(v_id)
                await inter.user.move_to(voice_ch)
                await target.move_to(voice_ch)
                if log_id:
                    log_ch = inter.guild.get_channel(log_id)
                    if log_ch:
                        await log_ch.send(
                            f"✅ **Schichtübergabe:** {inter.user.mention} → {target.mention} | Voice: {voice_ch.mention}")
                await sel_inter.response.send_message(f"{target.mention} wurde verschoben. Übergabe eingetragen!", ephemeral=True)
            select.callback = sel_cb
            view2.add_item(select)
            await inter.response.send_message("Wähle den Ziel-Nutzer:", view=view2, ephemeral=True)
        btn.callback = btn_cb
        view.add_item(btn)
        await interaction.channel.send(embed=emb, view=view)
        await interaction.response.send_message("Schicht-Panel gepostet!", ephemeral=True)

    # --- Schichtübergabe klassisch per Command mit Autocomplete ---
    async def schicht_user_autocomplete(self, interaction: discord.Interaction, current: str):
        cfg = get_schicht_cfg()
        rollen = set(cfg.get("rollen", []))
        allowed = []
        for m in interaction.guild.members:
            if m.bot:
                continue
            if any(r.id in rollen for r in m.roles):
                name_match = current.lower() in m.display_name.lower() or current.lower() in m.name.lower()
                if name_match:
                    allowed.append(app_commands.Choice(name=m.display_name, value=str(m.id)))
            if len(allowed) >= 20: break
        return allowed

    @app_commands.command(name="schichtuebergabe", description="Starte die Schichtübergabe an einen Nutzer")
    @app_commands.describe(nutzer="Nutzer für Übergabe")
    @app_commands.autocomplete(nutzer=schicht_user_autocomplete)
    async def schichtuebergabe(self, interaction: discord.Interaction, nutzer: str):
        rollen = set(get_schicht_cfg().get("rollen", []))
        if not any(r.id in rollen for r in interaction.user.roles) and not is_admin(interaction.user):
            return await interaction.response.send_message("Du bist nicht berechtigt!", ephemeral=True)
        target = interaction.guild.get_member(int(nutzer))
        if not target or not any(r.id in rollen for r in target.roles):
            return await interaction.response.send_message("Nutzer hat keine passende Rolle.", ephemeral=True)
        # Voice-Checks
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("Du musst in einem Sprachkanal sein!", ephemeral=True)
        if not target.voice or not target.voice.channel:
            try:
                await target.send(f"{interaction.user.display_name} möchte dir die Schicht übergeben, aber du bist nicht im Sprachkanal!")
            except Exception:
                pass
            return await interaction.response.send_message(f"{target.mention} ist nicht im Sprachkanal! (DM versucht)", ephemeral=True)
        v_id = get_schicht_cfg().get("voice_channel_id")
        log_id = get_schicht_cfg().get("log_channel_id")
        if not v_id:
            return await interaction.response.send_message("VoiceMaster-Kanal nicht gesetzt!", ephemeral=True)
        voice_ch = interaction.guild.get_channel(v_id)
        await interaction.user.move_to(voice_ch)
        await target.move_to(voice_ch)
        if log_id:
            log_ch = interaction.guild.get_channel(log_id)
            if log_ch:
                await log_ch.send(
                    f"✅ **Schichtübergabe:** {interaction.user.mention} → {target.mention} | Voice: {voice_ch.mention}")
        await interaction.response.send_message(f"{target.mention} wurde verschoben. Übergabe eingetragen!", ephemeral=True)

# ... dein SchichtCog-Code ...

async def reload_menu(self, config=None):
    if config is None:
        from utils import load_json
        config = load_json("setup_config.json", {})
    channel_id = config.get("schicht_log_channel")
    if not channel_id:
        return
    channel = self.bot.get_channel(channel_id)
    if not channel:
        return
    async for msg in channel.history(limit=50):
        if msg.author == self.bot.user:
            try:
                await msg.delete()
            except:
                pass
    # Schicht-Hauptmenü neu posten (wie in deinem /schichtinfo-Befehl!)
    await self.post_schichtinfo(channel)

SchichtCog.reload_menu = reload_menu

async def setup(bot):
    await bot.add_cog(SchichtCog(bot))