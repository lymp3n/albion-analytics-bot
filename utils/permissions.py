from typing import Optional, Set, Tuple

import discord

from utils.role_config import effective_sets_from_override_row, sets_from_assignment_rows

# Additional role IDs requested for another server (defaults when DB has no override).
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
    """Permissions checking system based on Discord roles (config.yaml + extras + optional per-guild DB overrides)."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.member_role_id = int(self.config["roles"]["member_id"])
        self.mentor_role_id = int(self.config["roles"]["mentor_id"])
        self.founder_role_id = int(self.config["roles"]["founder_id"])
        self._default_member_ids: Set[int] = {self.member_role_id, *EXTRA_MEMBER_ROLE_IDS}
        self._default_mentor_ids: Set[int] = {self.mentor_role_id, *EXTRA_MENTOR_ROLE_IDS}
        self._default_founder_ids: Set[int] = {self.founder_role_id, *EXTRA_FOUNDER_ROLE_IDS}
        # Backward-compatible names (default sets; effective checks use effective_role_sets).
        self.member_role_ids = self._default_member_ids
        self.mentor_role_ids = self._default_mentor_ids
        self.founder_role_ids = self._default_founder_ids

    def default_role_sets(self) -> Tuple[Set[int], Set[int], Set[int]]:
        return (
            set(self._default_member_ids),
            set(self._default_mentor_ids),
            set(self._default_founder_ids),
        )

    async def effective_role_sets(self, member: discord.Member) -> Tuple[Set[int], Set[int], Set[int]]:
        """Role ID sets for permission checks in the member's current Discord guild."""
        defaults = self.default_role_sets()
        if not member.guild:
            return defaults
        g = await self.bot.db.get_guild_by_discord_id(member.guild.id)
        if not g:
            return defaults
        gid = int(g["id"])
        assigns = await self.bot.db.fetch_guild_role_assignments(gid)
        if assigns:
            return sets_from_assignment_rows(assigns)
        row = await self.bot.db.fetch_guild_role_overrides(gid)
        return effective_sets_from_override_row(row, *defaults)

    async def effective_role_sets_for_interaction(
        self, interaction: discord.Interaction
    ) -> Tuple[Set[int], Set[int], Set[int]]:
        if interaction.guild and interaction.user:
            m = interaction.guild.get_member(interaction.user.id)
            if m:
                return await self.effective_role_sets(m)
        return self.default_role_sets()

    def has_role_id(self, member: discord.Member, role_id: int) -> bool:
        return any(role.id == role_id for role in member.roles)

    def has_any_role_id(self, member: discord.Member, role_ids: Set[int]) -> bool:
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids.intersection(role_ids))

    def is_server_admin(self, member: discord.Member) -> bool:
        perms = getattr(member, "guild_permissions", None)
        return bool(perms and perms.administrator)

    async def require_member(self, member: discord.Member) -> bool:
        if self.is_server_admin(member):
            return True
        founders, mentors, members = await self._ordered_effective_sets(member)
        if self.has_any_role_id(member, founders):
            return True
        if self.has_any_role_id(member, mentors):
            return True
        return self.has_any_role_id(member, members)

    async def require_mentor(self, member: discord.Member) -> bool:
        if self.is_server_admin(member):
            return True
        founders, mentors, _ = await self._ordered_effective_sets(member)
        if self.has_any_role_id(member, founders):
            return True
        return self.has_any_role_id(member, mentors)

    async def require_founder(self, member: discord.Member) -> bool:
        if self.is_server_admin(member):
            return True
        founders, _, _ = await self._ordered_effective_sets(member)
        return self.has_any_role_id(member, founders)

    async def require_economy(self, member: discord.Member) -> bool:
        """
        Dedicated economy access tier from guild_role_assignments (tier='economy').
        Founders and server admins are always allowed.
        """
        if self.is_server_admin(member):
            return True
        founders, _, _ = await self._ordered_effective_sets(member)
        if self.has_any_role_id(member, founders):
            return True
        if not member.guild:
            return False
        g = await self.bot.db.get_guild_by_discord_id(member.guild.id)
        if not g:
            return False
        assigns = await self.bot.db.fetch_guild_role_assignments(int(g["id"]))
        econ_ids = {int(str(r["discord_role_id"]).strip()) for r in assigns if str(r.get("tier") or "").strip().lower() == "economy"}
        if not econ_ids:
            return False
        return self.has_any_role_id(member, econ_ids)

    async def _ordered_effective_sets(self, member: discord.Member) -> Tuple[Set[int], Set[int], Set[int]]:
        mset, ment_set, fset = await self.effective_role_sets(member)
        return fset, ment_set, mset

    async def get_guild_id(self, member: discord.Member) -> Optional[int]:
        player = await self.bot.db.get_player_by_discord_id(member.id)
        return player["guild_id"] if player else None
