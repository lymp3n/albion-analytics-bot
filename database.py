import os
import asyncio
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import aiosqlite
import asyncpg
import yaml
from enum import Enum

class PlayerStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    MENTOR = "mentor"
    FOUNDER = "founder"

class TicketStatus(str, Enum):
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self.conn = None
        self.is_sqlite = database_url.startswith('sqlite://')
        
    async def connect(self):
        if self.is_sqlite:
            db_path = self.database_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            self.conn = await aiosqlite.connect(db_path)
            await self.conn.execute("PRAGMA foreign_keys = ON")
            await self.conn.execute("PRAGMA journal_mode = WAL")
        else:
            if self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
            
            import ssl
            ctx = ssl.create_default_context(cafile='')
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60,
                ssl=ctx
            )
        
        await self.initialize_schema()
        await self.seed_initial_data()
    
    async def close(self):
        if self.is_sqlite and self.conn:
            await self.conn.close()
        elif self.pool:
            await self.pool.close()
    
    async def execute(self, query: str, *args) -> Optional[int]:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            clean_args = args[0]
        else:
            clean_args = args

        if self.is_sqlite:
            placeholders = query.count('$')
            for i in range(placeholders, 0, -1):
                query = query.replace(f'${i}', '?')
            cursor = await self.conn.execute(query, clean_args)
            await self.conn.commit()
            return cursor.lastrowid
        else:
            async with self.pool.acquire() as conn:
                query_trimmed = query.strip()
                query_upper = query_trimmed.upper()
                
                if query_upper.startswith("INSERT"):
                    if "RETURNING" not in query_upper:
                        query_trimmed = query_trimmed.rstrip('; \t\n\r')
                        query_trimmed += " RETURNING id"
                    return await conn.fetchval(query_trimmed, *clean_args)
                else:
                    await conn.execute(query, *clean_args)
                    return None
    
    async def fetch(self, query: str, *args) -> list:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            clean_args = args[0]
        else:
            clean_args = args

        if self.is_sqlite:
            placeholders = query.count('$')
            for i in range(placeholders, 0, -1):
                query = query.replace(f'${i}', '?')
            cursor = await self.conn.execute(query, clean_args)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        else:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *clean_args)
                return [dict(row) for row in rows]
    
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            clean_args = args[0]
        else:
            clean_args = args

        if self.is_sqlite:
            placeholders = query.count('$')
            for i in range(placeholders, 0, -1):
                query = query.replace(f'${i}', '?')
            cursor = await self.conn.execute(query, clean_args)
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        else:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *clean_args)
                return dict(row) if row else None
    
    async def initialize_schema(self):
        if self.is_sqlite:
            pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
            bigint_type = "BIGINT"
            timestamp_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            cta_type = "INTEGER"
            cta_default = "0"
        else:
            pk_type = "SERIAL PRIMARY KEY"
            bigint_type = "BIGINT"
            timestamp_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            cta_type = "BOOLEAN"
            cta_default = "FALSE"
        
        # Guilds table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS guilds (
                id {pk_type},
                discord_id {bigint_type} NOT NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                founder_code TEXT NOT NULL UNIQUE,
                mentor_code TEXT NOT NULL UNIQUE,
                kill_fame INTEGER DEFAULT 0,
                death_fame INTEGER DEFAULT 0,
                created_at {timestamp_default}
            )
        """)
        try:
            await self.execute("ALTER TABLE guilds ADD COLUMN dashboard_label TEXT")
        except Exception:
            pass
        
        if not self.is_sqlite:
            try:
                await self.execute("ALTER TABLE guilds DROP CONSTRAINT IF EXISTS guilds_discord_id_key")
            except:
                pass
        
        # Players table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS players (
                id {pk_type},
                discord_id {bigint_type} UNIQUE NOT NULL,
                discord_username TEXT NOT NULL,
                nickname TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                avatar_url TEXT,
                description TEXT,
                specialization TEXT,
                balance INTEGER DEFAULT 0,
                created_at {timestamp_default},
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
        """)
        
        # Content table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS content (
                id {pk_type},
                name TEXT UNIQUE NOT NULL
            )
        """)
        
        # Tickets table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS tickets (
                id {pk_type},
                discord_channel_id {bigint_type} UNIQUE,
                discord_message_id {bigint_type},
                player_id INTEGER NOT NULL,
                mentor_id INTEGER,
                replay_link TEXT NOT NULL,
                session_date DATE NOT NULL,
                role TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                created_at {timestamp_default},
                updated_at {timestamp_default},
                closed_at TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                FOREIGN KEY (mentor_id) REFERENCES players(id) ON DELETE SET NULL
            )
        """)
        
        # Sessions table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS sessions (
                id {pk_type},
                ticket_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                content_id INTEGER NOT NULL,
                score REAL NOT NULL CHECK (score >= 0 AND score <= 10),
                role TEXT NOT NULL,
                error_types TEXT,
                work_on TEXT,
                comments TEXT,
                mentor_id INTEGER NOT NULL,
                session_date {timestamp_default},
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE,
                FOREIGN KEY (mentor_id) REFERENCES players(id) ON DELETE CASCADE
            )
        """)
        
        # Goals table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS goals (
                id {pk_type},
                player_id INTEGER NOT NULL,
                created_by_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'in_progress',
                due_date TIMESTAMP,
                created_at {timestamp_default},
                metric TEXT,
                metric_target REAL,
                metric_start_value REAL,
                metric_content_id INTEGER,
                metric_role TEXT,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_id) REFERENCES players(id) ON DELETE SET NULL,
                FOREIGN KEY (metric_content_id) REFERENCES content(id) ON DELETE SET NULL
            )
        """)

        # Events table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS events (
                id {pk_type},
                discord_message_id {bigint_type} UNIQUE,
                discord_channel_id {bigint_type},
                guild_id INTEGER,
                content_name TEXT NOT NULL,
                event_time TEXT NOT NULL,
                created_by INTEGER,
                template_name TEXT,
                is_cta {cta_type} DEFAULT {cta_default},
                status TEXT DEFAULT 'open',
                created_at {timestamp_default}
            )
        """)

        # Add `status` column to events if it doesn't exist (backward compatibility migration)
        try:
            await self.execute("ALTER TABLE events ADD COLUMN status TEXT DEFAULT 'open'")
        except Exception:
            # Column already exists
            pass
        try:
            await self.execute("ALTER TABLE events ADD COLUMN template_name TEXT")
        except Exception:
            pass
        try:
            if self.is_sqlite:
                await self.execute("ALTER TABLE events ADD COLUMN is_cta INTEGER DEFAULT 0")
            else:
                await self.execute("ALTER TABLE events ADD COLUMN is_cta BOOLEAN DEFAULT FALSE")
        except Exception:
            pass


        # Event Signups table
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS event_signups (
                id {pk_type},
                event_id INTEGER NOT NULL,
                slot_number INTEGER NOT NULL,
                role_name TEXT NOT NULL,
                player_id INTEGER,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
            )
        """)
        # Integrity for roster operations under reconnect/race conditions.
        await self.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_event_signups_unique_slot ON event_signups(event_id, slot_number)"
        )
        try:
            await self.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_event_signups_unique_player ON event_signups(event_id, player_id) WHERE player_id IS NOT NULL"
            )
        except Exception:
            pass
        
        # Per-guild Discord role overrides (dashboard); NULL/blank column = inherit config.yaml + extras
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS guild_role_overrides (
                guild_id INTEGER PRIMARY KEY,
                member_role_ids TEXT,
                mentor_role_ids TEXT,
                founder_role_ids TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
        """)

        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS guild_role_assignments (
                guild_id INTEGER NOT NULL,
                discord_role_id TEXT NOT NULL,
                tier TEXT NOT NULL,
                role_label TEXT,
                PRIMARY KEY (guild_id, discord_role_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
        """)
        try:
            await self.execute("ALTER TABLE guild_role_assignments ADD COLUMN role_label TEXT")
        except Exception:
            pass

        await self._migrate_guild_role_assignments_discord_id_to_text()

        await self.execute("""
            CREATE TABLE IF NOT EXISTS bot_kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Indices
        await self.execute("CREATE INDEX IF NOT EXISTS idx_players_guild_status ON players(guild_id, status)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_sessions_player_date ON sessions(player_id, session_date)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_events_message ON events(discord_message_id)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_events_status_created_guild ON events(status, created_at, guild_id)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_event_signups_event_player ON event_signups(event_id, player_id)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_event_signups_player_event ON event_signups(player_id, event_id)")
        
        if self.is_sqlite:
            await self.execute("""
                CREATE TRIGGER IF NOT EXISTS update_tickets_updated_at
                AFTER UPDATE ON tickets
                FOR EACH ROW
                BEGIN
                    UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;
            """)

    async def _migrate_guild_role_assignments_discord_id_to_text(self) -> None:
        """INTEGER/BIGINT cannot store all Discord snowflakes; use TEXT for exact decimal strings."""
        try:
            if self.is_sqlite:
                cursor = await self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_role_assignments'"
                )
                if not await cursor.fetchone():
                    return
                cursor = await self.conn.execute("PRAGMA table_info(guild_role_assignments)")
                rows = await cursor.fetchall()
                for row in rows:
                    col_name = row[1]
                    col_type = str(row[2] or "").upper()
                    if col_name == "discord_role_id" and "INT" in col_type:
                        await self.conn.execute("BEGIN")
                        await self.conn.execute(
                            """
                            CREATE TABLE guild_role_assignments__new (
                                guild_id INTEGER NOT NULL,
                                discord_role_id TEXT NOT NULL,
                                tier TEXT NOT NULL,
                                role_label TEXT,
                                PRIMARY KEY (guild_id, discord_role_id),
                                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
                            )
                            """
                        )
                        await self.conn.execute(
                            """
                            INSERT INTO guild_role_assignments__new (guild_id, discord_role_id, tier, role_label)
                            SELECT guild_id, CAST(discord_role_id AS TEXT), tier, role_label FROM guild_role_assignments
                            """
                        )
                        await self.conn.execute("DROP TABLE guild_role_assignments")
                        await self.conn.execute(
                            "ALTER TABLE guild_role_assignments__new RENAME TO guild_role_assignments"
                        )
                        await self.conn.commit()
                        break
            else:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT data_type FROM information_schema.columns
                        WHERE table_name = 'guild_role_assignments'
                          AND column_name = 'discord_role_id'
                        LIMIT 1
                        """
                    )
                    if not row:
                        return
                    dt = (row["data_type"] or "").lower()
                    if dt in ("bigint", "integer", "smallint"):
                        await conn.execute(
                            """
                            ALTER TABLE guild_role_assignments
                            ALTER COLUMN discord_role_id TYPE TEXT USING TRIM(discord_role_id::text)
                            """
                        )
        except Exception:
            pass

    async def seed_initial_data(self):
        guilds_count = await self.fetch("SELECT COUNT(*) as count FROM guilds")
        if guilds_count[0]['count'] > 0:
            return
        
        config_path = 'config.yaml'
        if not os.path.exists(config_path):
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        for guild_data in config.get('guilds', []):
            hashed_code = hashlib.sha256(guild_data['code'].encode()).hexdigest()
            hashed_founder = hashlib.sha256(guild_data['founder_code'].encode()).hexdigest()
            hashed_mentor = hashlib.sha256(guild_data['mentor_code'].encode()).hexdigest()
            
            await self.execute("""
                INSERT INTO guilds (discord_id, name, code, founder_code, mentor_code)
                VALUES ($1, $2, $3, $4, $5)
            """, 
                0, guild_data['name'], hashed_code, hashed_founder, hashed_mentor
            )
    
        content_types = ['Castles', 'Crystal League', 'Open World', 'HG 5v5', 'Avalon', 'Scrims']
        for content in content_types:
            await self.execute(
                "INSERT INTO content (name) VALUES ($1)",
                content
            )
    
    async def update_guild_discord_id(self, guild_name: str, discord_guild_id: int):
        await self.execute(
            "UPDATE guilds SET discord_id = $1 WHERE name = $2 AND discord_id = 0",
            discord_guild_id, guild_name
        )

    async def update_guild_discord_id_by_id(self, guild_db_id: int, discord_guild_id: int) -> None:
        await self.execute(
            "UPDATE guilds SET discord_id = $1 WHERE id = $2",
            discord_guild_id,
            guild_db_id,
        )

    async def update_guild_dashboard_label(self, guild_db_id: int, label: Optional[str]) -> None:
        await self.execute(
            "UPDATE guilds SET dashboard_label = $1 WHERE id = $2",
            label,
            guild_db_id,
        )

    async def fetch_guild_role_assignments(self, guild_db_id: int) -> list:
        return await self.fetch(
            """
            SELECT guild_id, discord_role_id, tier, role_label
            FROM guild_role_assignments
            WHERE guild_id = $1
            ORDER BY discord_role_id
            """,
            guild_db_id,
        )

    async def replace_guild_role_assignments(self, guild_db_id: int, pairs: List[tuple]) -> None:
        """pairs: list of (discord_role_id: str, tier: str, role_label: Optional[str]). Replaces all rows for guild."""
        await self.execute("DELETE FROM guild_role_assignments WHERE guild_id = $1", guild_db_id)
        for item in pairs:
            if len(item) >= 3:
                role_id, tier, label = item[0], item[1], item[2]
            else:
                role_id, tier, label = item[0], item[1], None
            await self.execute(
                """
                INSERT INTO guild_role_assignments (guild_id, discord_role_id, tier, role_label)
                VALUES ($1, $2, $3, $4)
                """,
                guild_db_id,
                role_id,
                tier,
                label,
            )
    
    async def get_player_by_discord_id(self, discord_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow(
            "SELECT * FROM players WHERE discord_id = $1", 
            discord_id
        )
    
    async def get_player_by_id(self, player_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow(
            "SELECT * FROM players WHERE id = $1", 
            player_id
        )
    
    async def get_guild_by_code(self, code_hash: str) -> Optional[Dict[str, Any]]:
        return await self.fetchrow("""
            SELECT * FROM guilds 
            WHERE code = $1 OR founder_code = $2 OR mentor_code = $3
        """, code_hash, code_hash, code_hash)
    
    async def get_guild_by_discord_id(self, discord_guild_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow(
            "SELECT * FROM guilds WHERE discord_id = $1", 
            discord_guild_id
        )

    async def fetch_guild_role_overrides(self, guild_db_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow(
            "SELECT * FROM guild_role_overrides WHERE guild_id = $1",
            guild_db_id,
        )

    async def delete_guild_role_overrides(self, guild_db_id: int) -> None:
        await self.execute("DELETE FROM guild_role_overrides WHERE guild_id = $1", guild_db_id)

    async def upsert_guild_role_overrides(
        self,
        guild_db_id: int,
        member_role_ids: Optional[str],
        mentor_role_ids: Optional[str],
        founder_role_ids: Optional[str],
    ) -> None:
        if self.is_sqlite:
            await self.execute(
                """
                INSERT INTO guild_role_overrides (guild_id, member_role_ids, mentor_role_ids, founder_role_ids)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(guild_id) DO UPDATE SET
                    member_role_ids = excluded.member_role_ids,
                    mentor_role_ids = excluded.mentor_role_ids,
                    founder_role_ids = excluded.founder_role_ids
                """,
                guild_db_id,
                member_role_ids,
                mentor_role_ids,
                founder_role_ids,
            )
        else:
            await self.execute(
                """
                INSERT INTO guild_role_overrides (guild_id, member_role_ids, mentor_role_ids, founder_role_ids)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id) DO UPDATE SET
                    member_role_ids = EXCLUDED.member_role_ids,
                    mentor_role_ids = EXCLUDED.mentor_role_ids,
                    founder_role_ids = EXCLUDED.founder_role_ids
                """,
                guild_db_id,
                member_role_ids,
                mentor_role_ids,
                founder_role_ids,
            )

    async def get_bot_kv(self, key: str) -> Optional[str]:
        row = await self.fetchrow("SELECT value FROM bot_kv WHERE key = $1", key)
        if not row:
            return None
        return row.get("value")

    async def set_bot_kv(self, key: str, value: str) -> None:
        """Upsert key/value; bypasses execute() INSERT RETURNING id behavior (no id column)."""
        if self.is_sqlite:
            await self.conn.execute(
                "INSERT OR REPLACE INTO bot_kv (key, value) VALUES (?, ?)",
                (key, value),
            )
            await self.conn.commit()
        else:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bot_kv (key, value) VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    key,
                    value,
                )
