from enum import Enum
from typing import Optional

class PlayerStatus(str, Enum):
    """Статусы игроков в системе"""
    PENDING = "pending"    # Ожидает одобрения
    ACTIVE = "active"      # Обычный мембер
    MENTOR = "mentor"      # Ментор
    FOUNDER = "founder"    # Основатель гильдии

class TicketStatus(str, Enum):
    """Статусы тикетов"""
    AVAILABLE = "available"   # Доступен для оценки
    IN_PROGRESS = "in_progress"  # В работе у ментора
    CLOSED = "closed"         # Закрыт и оценён

class ContentTypes:
    """Типы контента в Albion Online"""
    CASTLES = "Castles"
    CRYSTAL_LEAGUE = "Crystal League"
    OPEN_WORLD = "Open World"
    HG_5V5 = "HG 5v5"
    AVALON = "Avalon"
    SCRIMS = "Scrims"
    
    @classmethod
    def all(cls) -> list:
        return [cls.CASTLES, cls.CRYSTAL_LEAGUE, cls.OPEN_WORLD, 
                cls.HG_5V5, cls.AVALON, cls.SCRIMS]

class PlayerRoles:
    """Роли в игре"""
    DTANK = "D-Tank"
    ETANK = "E-Tank"
    HEALER = "Healer"
    SUPPORT = "Support"
    DPS = "DPS"
    BATTLEMOUNT = "Battlemount"
    
    @classmethod
    def all(cls) -> list:
        return [cls.DTANK, cls.ETANK, cls.HEALER, cls.SUPPORT, cls.DPS, cls.BATTLEMOUNT]