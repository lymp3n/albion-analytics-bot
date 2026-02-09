from typing import Optional
import discord
import yaml
import os

class Permissions:
    """Система проверки прав доступа на основе ролей Discord"""
    
    def __init__(self, bot):
        self.bot = bot
        # Load config directly or access via bot if available. 
        # Accessing via bot.config is safer if it's already loaded there.
        # Assuming bot has config attribute as seen in other files.
        self.config = bot.config
        self.member_role_id = int(self.config['roles']['member_id'])
        self.mentor_role_id = int(self.config['roles']['mentor_id'])
        self.founder_role_id = int(self.config['roles']['founder_id'])
    
    def has_role_id(self, member: discord.Member, role_id: int) -> bool:
        """Проверка наличия конкретной роли по ID"""
        return any(role.id == role_id for role in member.roles)

    async def require_member(self, member: discord.Member) -> bool:
        """
        Проверка: является ли пользователь мембером.
        Иерархия: Founder > Mentor > Member.
        """
        if self.has_role_id(member, self.founder_role_id):
            return True
        if self.has_role_id(member, self.mentor_role_id):
            return True
        return self.has_role_id(member, self.member_role_id)
    
    async def require_mentor(self, member: discord.Member) -> bool:
        """
        Проверка: является ли пользователь ментором.
        Иерархия: Founder > Mentor.
        """
        if self.has_role_id(member, self.founder_role_id):
            return True
        return self.has_role_id(member, self.mentor_role_id)
    
    async def require_founder(self, member: discord.Member) -> bool:
        """Проверка: является ли пользователь фаундером"""
        return self.has_role_id(member, self.founder_role_id)
    
    async def get_guild_id(self, member: discord.Member) -> Optional[int]:
        """Получение ID гильдии игрока из БД"""
        player = await self.bot.db.get_player_by_discord_id(member.id)
        return player['guild_id'] if player else None