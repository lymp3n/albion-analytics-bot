import os
import asyncio
import hashlib
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import aiosqlite
import asyncpg
import yaml
from enum import Enum

class PlayerStatus(str, Enum):
    """Статусы игроков в системе"""
    PENDING = "pending"    # Ожидает одобрения
    ACTIVE = "active"      # Обычный мембер
    MENTOR = "mentor"      # Ментор
    FOUNDER = "founder"    # Основатель гильдии

class TicketStatus(str, Enum):
    """Статусы тикетов"""
    AVAILABLE = "available"     # Доступен для оценки
    IN_PROGRESS = "in_progress" # В работе у ментора
    CLOSED = "closed"           # Закрыт и оценён

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self.conn = None
        self.is_sqlite = database_url.startswith('sqlite://')
        
    async def connect(self):
        """Инициализация подключения к БД"""
        if self.is_sqlite:
            # SQLite: создаём папку если не существует
            db_path = self.database_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            self.conn = await aiosqlite.connect(db_path)
            await self.conn.execute("PRAGMA foreign_keys = ON")
            await self.conn.execute("PRAGMA journal_mode = WAL")
        else:
            # PostgreSQL
            # Fix Render's "postgres://" scheme which asyncpg doesn't like
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
        """Закрытие подключения"""
        if self.is_sqlite and self.conn:
            await self.conn.close()
        elif self.pool:
            await self.pool.close()
    
    async def execute(self, query: str, *args) -> Optional[int]:
        """Выполнение запроса"""
        # Если передан кортеж как один аргумент, распаковываем его
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            clean_args = args[0]
        else:
            clean_args = args

        if self.is_sqlite:
            # Для SQLite заменяем $1, $2 на ? и преобразуем типы
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
                    # Обеспечиваем получение ID через RETURNING id
                    if "RETURNING" not in query_upper:
                        # Удаляем возможную точку с запятой в конце и добавляем RETURNING
                        query_trimmed = query_trimmed.rstrip('; \t\n\r')
                        query_trimmed += " RETURNING id"
                    
                    return await conn.fetchval(query_trimmed, *clean_args)
                else:
                    # Для UPDATE/DELETE/CREATE и т.д.
                    await conn.execute(query, *clean_args)
                    return None
    
    async def fetch(self, query: str, *args) -> list:
        """Получение данных"""
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
        """Получение одной строки"""
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
        """Создание таблиц с поддержкой SQLite и PostgreSQL"""
        # Определяем синтаксис в зависимости от типа БД
        if self.is_sqlite:
            pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
            bigint_type = "BIGINT"
            timestamp_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        else:
            pk_type = "SERIAL PRIMARY KEY"
            bigint_type = "BIGINT"
            timestamp_default = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        
        # Таблица гильдий
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
        
        # Если БД PostgreSQL, на всякий случай удаляем UNIQUE ограничение с discord_id, 
        # чтобы можно было иметь несколько гильдий с ID 0 при инициализации
        if not self.is_sqlite:
            try:
                await self.execute("ALTER TABLE guilds DROP CONSTRAINT IF EXISTS guilds_discord_id_key")
            except:
                pass
        
        # Таблица игроков
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
        
        # Таблица контента
        await self.execute(f"""
            CREATE TABLE IF NOT EXISTS content (
                id {pk_type},
                name TEXT UNIQUE NOT NULL
            )
        """)
        
        # Таблица тикетов
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
        
        # Таблица сессий
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
        
        # Таблица целей
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
        
        # Индексы
        await self.execute("CREATE INDEX IF NOT EXISTS idx_players_guild_status ON players(guild_id, status)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        await self.execute("CREATE INDEX IF NOT EXISTS idx_sessions_player_date ON sessions(player_id, session_date)")
        
        # Триггер для обновления updated_at (только для SQLite)
        if self.is_sqlite:
            await self.execute("""
                CREATE TRIGGER IF NOT EXISTS update_tickets_updated_at
                AFTER UPDATE ON tickets
                FOR EACH ROW
                BEGIN
                    UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;
            """)
    
    async def seed_initial_data(self):
        """Заполнение начальными данными"""
        # Проверяем, есть ли уже данные
        guilds_count = await self.fetch("SELECT COUNT(*) as count FROM guilds")
        if guilds_count[0]['count'] > 0:
            return
        
        config_path = 'config.yaml'
        if not os.path.exists(config_path):
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Заполняем гильдии
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
    
        # Заполняем контент
        content_types = ['Castles', 'Crystal League', 'Open World', 'HG 5v5', 'Avalon', 'Scrims']
        for content in content_types:
            await self.execute(
                "INSERT INTO content (name) VALUES ($1)",
                content
            )
    
    async def update_guild_discord_id(self, guild_name: str, discord_guild_id: int):
        """Обновление Discord ID гильдии"""
        await self.execute(
            "UPDATE guilds SET discord_id = $1 WHERE name = $2 AND discord_id = 0",
            discord_guild_id, guild_name
        )
    
    # Утилиты для работы с игроками
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
