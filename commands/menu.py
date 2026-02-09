import discord
from discord import ui
from discord.ext import commands


class MainMenuView(ui.View):
    """Главное меню бота с кнопками"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @ui.button(label="📝 Создать тикет", style=discord.ButtonStyle.primary, row=0)
    async def create_ticket(self, button: ui.Button, interaction: discord.Interaction):
        from commands.tickets import TicketModal
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            await interaction.response.send_message("❌ Сначала зарегистрируйтесь: `/register <код>`", ephemeral=True)
            return
        
        modal = TicketModal(self.bot, player['id'], player['guild_id'])
        await interaction.response.send_modal(modal)
    
    @ui.button(label="📊 Моя статистика", style=discord.ButtonStyle.secondary, row=0)
    async def view_stats(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("📊 Используйте команду `/stats` для просмотра статистики.", ephemeral=True)
    
    @ui.button(label="🎫 Мои тикеты", style=discord.ButtonStyle.secondary, row=1)
    async def my_tickets(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("🎫 Используйте команду `/ticket list` для просмотра тикетов.", ephemeral=True)


class MenuCommands(commands.Cog):
    """Команды меню"""
    
    def __init__(self, bot):
        self.bot = bot
        print("✓ MenuCommands initialized")
    
    @discord.slash_command(name="menu", description="Открыть главное меню бота")
    async def menu(self, ctx: discord.ApplicationContext):
        """Показывает главное меню с кнопками"""
        embed = discord.Embed(
            title="🎮 Albion Analytics Bot - Main Menu",
            description="Choose an action below:",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="📝 Create Ticket", value="Submit a session for review", inline=False)
        embed.add_field(name="📊 My Stats", value="View your statistics", inline=False)
        embed.add_field(name="🎫 My Tickets", value="View your active tickets", inline=False)
        
        view = MainMenuView(self.bot)
        await ctx.respond(embed=embed, view=view, ephemeral=True)

def setup(bot):
    bot.add_cog(MenuCommands(bot))
