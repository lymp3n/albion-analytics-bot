from typing import Optional
import discord
import yaml
import os

# Additional role IDs requested for another server.
EXTRA_MEMBER_ROLE_IDS = {
    1466898167940251822,
    1467204817389617247,
    1466898064840331285,
    1466898222411812944,
}
EXTRA_MENTOR_ROLE_IDS = {
    1488845309567303750,
}
EXTRA_FOUNDER_ROLE_IDS = {
    1467545128897089699,
}

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
        self.member_role_ids = {self.member_role_id, *EXTRA_MEMBER_ROLE_IDS}
        self.mentor_role_ids = {self.mentor_role_id, *EXTRA_MENTOR_ROLE_IDS}
        self.founder_role_ids = {self.founder_role_id, *EXTRA_FOUNDER_ROLE_IDS}
    
    def has_role_id(self, member: discord.Member, role_id: int) -> bool:
        """Check if a member has a specific role by ID"""
        return any(role.id == role_id for role in member.roles)

    def has_any_role_id(self, member: discord.Member, role_ids: set[int]) -> bool:
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids.intersection(role_ids))

    def is_server_admin(self, member: discord.Member) -> bool:
        """Allow Discord server administrators to pass bot permission checks."""
        perms = getattr(member, "guild_permissions", None)
        return bool(perms and perms.administrator)

    async def require_member(self, member: discord.Member) -> bool:
        """
        Check: if the user is a member.
        Hierarchy: Founder > Mentor > Member.
        """
        if self.is_server_admin(member):
            return True
        if self.has_any_role_id(member, self.founder_role_ids):
            return True
        if self.has_any_role_id(member, self.mentor_role_ids):
            return True
        return self.has_any_role_id(member, self.member_role_ids)
    
    async def require_mentor(self, member: discord.Member) -> bool:
        """
        Check: if the user is a mentor.
        Hierarchy: Founder > Mentor.
        """
        if self.is_server_admin(member):
            return True
        if self.has_any_role_id(member, self.founder_role_ids):
            return True
        return self.has_any_role_id(member, self.mentor_role_ids)
    
    async def require_founder(self, member: discord.Member) -> bool:
        """Check: if the user is a founder"""
        if self.is_server_admin(member):
            return True
        return self.has_any_role_id(member, self.founder_role_ids)
    
    async def get_guild_id(self, member: discord.Member) -> Optional[int]:
        """Gets player's guild ID from DB"""
        player = await self.bot.db.get_player_by_discord_id(member.id)
        return player['guild_id'] if player else None