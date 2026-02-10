from enum import Enum
from typing import Optional

class PlayerStatus(str, Enum):
    """Player statuses in the system"""
    PENDING = "pending"    # Awaiting approval
    ACTIVE = "active"      # Regular member
    MENTOR = "mentor"      # Mentor
    FOUNDER = "founder"    # Guild founder

class TicketStatus(str, Enum):
    """Ticket statuses"""
    AVAILABLE = "available"   # Available for evaluation
    IN_PROGRESS = "in_progress"  # In review by a mentor
    CLOSED = "closed"         # Closed and evaluated

class ContentTypes:
    """Content types in Albion Online"""
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
    """In-game roles"""
    DTANK = "D-Tank"
    ETANK = "E-Tank"
    HEALER = "Healer"
    SUPPORT = "Support"
    DPS = "DPS"
    BATTLEMOUNT = "Battlemount"
    
    @classmethod
    def all(cls) -> list:
        return [cls.DTANK, cls.ETANK, cls.HEALER, cls.SUPPORT, cls.DPS, cls.BATTLEMOUNT]