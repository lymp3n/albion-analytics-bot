from typing import Optional
import discord
import yaml
import os

class Permissions:
    """Permissions checking system based on Discord roles"""
    
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
        """Check if a member has a specific role by ID"""
        return any(role.id == role_id for role in member.roles)

    async def require_member(self, member: discord.Member) -> bool:
        """
        Check: if the user is a member.
        Hierarchy: Founder > Mentor > Member.
        """
        if self.has_role_id(member, self.founder_role_id):
            return True
        if self.has_role_id(member, self.mentor_role_id):
            return True
        return self.has_role_id(member, self.member_role_id)
    
    async def require_mentor(self, member: discord.Member) -> bool:
        """
        Check: if the user is a mentor.
        Hierarchy: Founder > Mentor.
        """
        if self.has_role_id(member, self.founder_role_id):
            return True
        return self.has_role_id(member, self.mentor_role_id)
    
    async def require_founder(self, member: discord.Member) -> bool:
        """Check: if the user is a founder"""
        return self.has_role_id(member, self.founder_role_id)
    
    async def get_guild_id(self, member: discord.Member) -> Optional[int]:
        """Gets player's guild ID from DB"""
        player = await self.bot.db.get_player_by_discord_id(member.id)
        return player['guild_id'] if player else None