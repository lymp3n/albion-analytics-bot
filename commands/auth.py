import hashlib
import discord
from discord import option
from discord.ext import commands
from models import PlayerStatus
from utils.permissions import Permissions

class AuthCommands(commands.Cog):
    """Команды регистрации и управления гильдией"""
    
    def __init__(self, bot):
        self.bot = bot
        print("✓ AuthCommands initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Автоматическое обновление Discord ID гильдии при запуске"""
        # Ждем подключения к БД, если оно еще не произошло (в bot.py)
        import asyncio
        for _ in range(10):
            if self.bot.db.is_sqlite or (self.bot.db.pool is not None):
                break
            await asyncio.sleep(1)
        
        if not self.bot.db.is_sqlite and self.bot.db.pool is None:
            print("⚠️ AuthCommands: Database not connected after wait, skipping on_ready sync")
            return

        guild_id = self.bot.guild_id or int(self.bot.config.get('GUILD_ID', 0))
        if not guild_id:
            return
            
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if guild:
            # Обновляем Discord ID для всех гильдий в БД
            for db_guild in await self.bot.db.fetch("SELECT id, name FROM guilds WHERE discord_id = 0"):
                await self.bot.db.update_guild_discord_id(db_guild['name'], guild.id)
                print(f"✓ Обновлён Discord ID для гильдии '{db_guild['name']}' -> {guild.id}")
    
    @discord.slash_command(name="register", description="Register in the guild using invite code")
    @option("code", description="Guild invitation code")
    async def register(self, ctx: discord.ApplicationContext, code: str):
        """Регистрация нового игрока в гильдии"""
        # Хешируем код для сравнения с БД
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Ищем гильдию по коду
        guild = await self.bot.db.get_guild_by_code(code_hash)
        if not guild:
            await ctx.respond("❌ Invalid guild code. Please check and try again.", ephemeral=True)
            return
        
        # Проверяем, не зарегистрирован ли уже игрок
        existing_player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        if existing_player:
            if existing_player['status'] == 'pending':
                await ctx.respond("⏳ Your registration is pending approval by guild founder.", ephemeral=True)
            else:
                await ctx.respond(f"✅ You are already registered in guild **{existing_player['guild_name']}**", ephemeral=True)
            return
        
        # Определяем статус на основе кода
        if code_hash == guild['founder_code']:
            status = PlayerStatus.FOUNDER.value
        elif code_hash == guild['mentor_code']:
            status = PlayerStatus.MENTOR.value
        else:
            status = PlayerStatus.PENDING.value  # Обычные игроки требуют одобрения
        
        # Создаём запись игрока
        try:
            await self.bot.db.execute("""
                INSERT INTO players (discord_id, discord_username, nickname, guild_id, status)
                VALUES ($1, $2, $3, $4, $5)
            """, 
                ctx.author.id,
                str(ctx.author),
                ctx.author.display_name,
                guild['id'],
                status
            )
            
            if status == PlayerStatus.PENDING.value:
                # Уведомляем фаундеров гильдии
                founders = await self.bot.db.fetch("""
                    SELECT discord_id FROM players 
                    WHERE guild_id = $1 AND status = 'founder'
                """, guild['id'])
                
                founder_mentions = " ".join([f"<@{f['discord_id']}>" for f in founders]) if founders else "@here"
                
                await ctx.respond(
                    f"✅ Registration submitted! Your application is pending approval.\n"
                    f"Guild founders have been notified: {founder_mentions}",
                    ephemeral=True
                )
                
                # Отправляем уведомление в канал #регистрация (если существует)
                registration_channel = discord.utils.get(ctx.guild.channels, name="регистрация")
                if registration_channel:
                    await registration_channel.send(
                        f"🆕 New registration pending approval:\n"
                        f"Player: {ctx.author.mention} (`{ctx.author.display_name}`)\n"
                        f"Guild: **{guild['name']}**\n"
                        f"Use `/guild approve {ctx.author.id}` to approve"
                    )
            else:
                # Для фаундеров/менторов — автоматическое одобрение
                role_name = "Founder" if status == PlayerStatus.FOUNDER.value else "Mentor"
                await ctx.respond(
                    f"✅ Welcome {role_name}! You have been registered in guild **{guild['name']}** with full permissions.",
                    ephemeral=True
                )
                
        except Exception as e:
            await ctx.respond(f"❌ Registration failed: {str(e)}", ephemeral=True)
    
    @discord.slash_command(name="guild", description="Guild management commands")
    @option("action", choices=["approve", "promote", "demote", "info"])
    @option("user", required=False, description="Target user (for approve/promote/demote)")
    async def guild_management(self, ctx: discord.ApplicationContext, action: str, user: discord.Member = None):
        """Управление гильдией (только для фаундеров)"""
        # Проверка прав фаундера
        if not await self.bot.permissions.require_founder(ctx.author):
            await ctx.respond("❌ Only guild founders can use this command.", ephemeral=True)
            return
        
        if action == "info":
            # Информация о гильдии
            guild_id = await self.bot.permissions.get_guild_id(ctx.author)
            if not guild_id:
                await ctx.respond("❌ Unable to determine your guild.", ephemeral=True)
                return
            
            stats = await self.bot.db.fetchrow("""
                SELECT 
                    g.name as guild_name,
                    COUNT(CASE WHEN p.status != 'pending' THEN 1 END) as active_members,
                    COUNT(CASE WHEN p.status = 'mentor' THEN 1 END) as mentors,
                    COUNT(CASE WHEN p.status = 'founder' THEN 1 END) as founders,
                    COUNT(s.id) as total_sessions,
                    AVG(s.score) as avg_score
                FROM guilds g
                LEFT JOIN players p ON p.guild_id = g.id
                LEFT JOIN sessions s ON s.player_id = p.id AND s.session_date >= NOW() - INTERVAL '30 days'
                WHERE g.id = $1
                GROUP BY g.id, g.name
            """, guild_id)
            
            embed = discord.Embed(
                title=f"Guild Statistics: {stats['guild_name']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Active Members", value=stats['active_members'] or 0, inline=True)
            embed.add_field(name="Mentors", value=stats['mentors'] or 0, inline=True)
            embed.add_field(name="Founders", value=stats['founders'] or 0, inline=True)
            embed.add_field(name="Sessions (30d)", value=stats['total_sessions'] or 0, inline=True)
            embed.add_field(name="Avg Score (30d)", value=f"{stats['avg_score']:.2f}" if stats['avg_score'] else "N/A", inline=True)
            embed.set_footer(text="Use /guild approve @user to approve pending registrations")
            
            await ctx.respond(embed=embed)
            return
        
        if not user:
            await ctx.respond(f"❌ Please specify a user for action '{action}'.", ephemeral=True)
            return
        
        # Получаем данные игрока
        target_player = await self.bot.db.get_player_by_discord_id(user.id)
        if not target_player:
            await ctx.respond(f"❌ User {user.mention} is not registered in the system.", ephemeral=True)
            return
        
        # Проверяем, что игрок из той же гильдии
        if target_player['guild_id'] != await self.bot.permissions.get_guild_id(ctx.author):
            await ctx.respond(f"❌ User {user.mention} belongs to a different guild.", ephemeral=True)
            return
        
        if action == "approve":
            if target_player['status'] != PlayerStatus.PENDING.value:
                await ctx.respond(f"❌ User {user.mention} is not pending approval.", ephemeral=True)
                return
            
            await self.bot.db.execute(
                "UPDATE players SET status = 'active' WHERE id = $1",
                target_player['id']
            )
            
            # Выдаём роль Member на сервере Discord
            member_role = discord.utils.get(ctx.guild.roles, name="Member")
            if member_role and member_role not in user.roles:
                await user.add_roles(member_role)
            
            await ctx.respond(f"✅ User {user.mention} has been approved and granted Member role.")
            await user.send(f"🎉 Congratulations! Your registration in **{target_player['guild_name']}** has been approved. You now have access to all member features.")
        
        elif action == "promote":
            if target_player['status'] not in [PlayerStatus.ACTIVE.value, PlayerStatus.MENTOR.value]:
                await ctx.respond(f"❌ Cannot promote user {user.mention} with status '{target_player['status']}'.", ephemeral=True)
                return
            
            new_status = PlayerStatus.MENTOR.value if target_player['status'] == PlayerStatus.ACTIVE.value else PlayerStatus.FOUNDER.value
            await self.bot.db.execute(
                "UPDATE players SET status = $1 WHERE id = $2",
                new_status,
                target_player['id']
            )
            
            # Выдаём роль на сервере
            role_name = "Mentor" if new_status == PlayerStatus.MENTOR.value else "Founder"
            discord_role = discord.utils.get(ctx.guild.roles, name=role_name)
            if discord_role and discord_role not in user.roles:
                await user.add_roles(discord_role)
            
            await ctx.respond(f"✅ User {user.mention} has been promoted to **{role_name}**.")
            await user.send(f"🌟 You have been promoted to **{role_name}** in **{target_player['guild_name']}**!")
        
        elif action == "demote":
            if target_player['status'] not in [PlayerStatus.MENTOR.value, PlayerStatus.FOUNDER.value]:
                await ctx.respond(f"❌ Cannot demote user {user.mention} with status '{target_player['status']}'.", ephemeral=True)
                return
            
            if target_player['status'] == PlayerStatus.FOUNDER.value and ctx.author.id != user.id:
                await ctx.respond("❌ Only founders can demote other founders (and only themselves).", ephemeral=True)
                return
            
            new_status = PlayerStatus.ACTIVE.value if target_player['status'] == PlayerStatus.MENTOR.value else PlayerStatus.MENTOR.value
            await self.bot.db.execute(
                "UPDATE players SET status = $1 WHERE id = $2",
                new_status,
                target_player['id']
            )
            
            # Убираем роль на сервере
            old_role_name = "Founder" if target_player['status'] == PlayerStatus.FOUNDER.value else "Mentor"
            new_role_name = "Mentor" if new_status == PlayerStatus.MENTOR.value else "Member"
            old_role = discord.utils.get(ctx.guild.roles, name=old_role_name)
            new_role = discord.utils.get(ctx.guild.roles, name=new_role_name)
            
            if old_role and old_role in user.roles:
                await user.remove_roles(old_role)
            if new_role and new_role not in user.roles:
                await user.add_roles(new_role)
            
            await ctx.respond(f"✅ User {user.mention} has been demoted to **{new_role_name}**.")
            await user.send(f"⬇️ Your role in **{target_player['guild_name']}** has been changed to **{new_role_name}**.")

def setup(bot):
    bot.add_cog(AuthCommands(bot))