import re
from typing import Optional, Tuple

class ReplayValidator:
    """Валидация ссылок на реплеи Albion Online"""
    
    ALBION_REPLAY_PATTERN = r'https?://(?:www\.)?albiononline\.com/(?:[^/]+/)?replay/([a-f0-9-]+)'
    
    @classmethod
    def validate_replay_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация ссылки на реплей
        Returns: (is_valid, error_message or None)
        """
        if not url or not url.strip():
            return False, "Replay URL cannot be empty"
        
        url = url.strip()
        
        # Проверка базового формата URL
        if not url.startswith(('http://', 'https://')):
            return False, "Invalid URL format (must start with http:// or https://)"
        
        # Проверка домена Albion Online
        if 'albiononline.com' not in url.lower():
            return False, "URL must be from albiononline.com domain"
        
        # Проверка наличия идентификатора реплея
        match = re.search(cls.ALBION_REPLAY_PATTERN, url, re.IGNORECASE)
        if not match:
            return False, "Invalid replay URL format. Must contain replay ID (e.g., https://albiononline.com/en/replay/123e4567-e89b-12d3-a456-426614174000)"
        
        return True, None
    
    @classmethod
    def extract_replay_id(cls, url: str) -> Optional[str]:
        """Извлечение идентификатора реплея из URL"""
        match = re.search(cls.ALBION_REPLAY_PATTERN, url, re.IGNORECASE)
        return match.group(1) if match else None


class RoleValidator:
    """Валидация игровых ролей"""
    
    VALID_ROLES = {
        'D-Tank': ['dtank', 'd-tank', 'dark tank'],
        'E-Tank': ['etank', 'e-tank', 'light tank'],
        'Healer': ['healer', 'heal'],
        'Support': ['support', 'supp'],
        'DPS': ['dps', 'damage'],
        'Battlemount': ['battlemount', 'bm', 'mount']
    }
    
    @classmethod
    def normalize_role(cls, role_input: str) -> Optional[str]:
        """Нормализация названия роли к каноническому виду"""
        if not role_input:
            return None
        
        role_lower = role_input.lower().strip()
        for canonical, aliases in cls.VALID_ROLES.items():
            if role_lower == canonical.lower() or role_lower in aliases:
                return canonical
        
        return None
    
    @classmethod
    def get_role_suggestions(cls, partial: str) -> list:
        """Получение подсказок для ролей"""
        partial = partial.lower()
        suggestions = []
        for canonical in cls.VALID_ROLES.keys():
            if partial in canonical.lower():
                suggestions.append(canonical)
        return suggestions[:5]  # Максимум 5 подсказок