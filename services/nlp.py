import re
from typing import List

class ErrorCategorizer:
    """
    Simple rule-based error categorization without machine learning.
    Uses keywords and has no dependencies on scikit-learn/nltk.
    """
    
    CATEGORIES = {
        'Positioning': [
            'position', 'pos', 'behind', 'front', 'flank', 'backline', 'frontline',
            'out of position', 'bad position', 'too far', 'too close', 'exposed',
            'overextended', 'split push', 'peel', 'protect', 'distance', 'range'
        ],
        'Rotation': [
            'rotation', 'rot', 'rotate', 'rotating', 'slow rot', 'fast rot',
            'wrong rotation', 'missed rot', 'rot timing', 'zerg rot', 'group rot',
            'skill', 'combo', 'sequence', 'order', 'priority'
        ],
        'Target Priority': [
            'target', 'priority', 'tp', 'focus', 'focus fire', 'wrong target',
            'squishy', 'tank', 'healer', 'dps', 'kill priority', 'cc target',
            'peel', 'dive', 'engage'
        ],
        'Ability Usage': [
            'ability', 'skill', 'cooldown', 'cd', 'cc', 'stun', 'root', 'slow',
            'heal', 'shield', 'damage', 'ult', 'ultimate', 'wasted cd', 'saved cd',
            'interrupt', 'break', 'purge'
        ],
        'Map Awareness': [
            'map', 'awareness', 'vision', 'ward', 'scout', 'enemy', 'missing',
            'mia', 'gank', 'ambush', 'bush', 'fog', 'minimap', 'tracking',
            'objective', 'capture', 'defend'
        ],
        'Communication': [
            'comms', 'ping', 'call', 'voice', 'chat', 'mute', 'no comms',
            'bad call', 'wrong ping', 'spam', 'silent', 'coordination',
            'collab', 'teamwork', 'voice'
        ],
        'Mechanics': [
            'mechanic', 'dodge', 'block', 'parry', 'interrupt', 'cc break',
            'animation cancel', 'kiting', 'juking', 'movement', 'pathing',
            'timer', 'press', 'reaction', 'input'
        ],
        'Build/Itemization': [
            'build', 'items', 'gear', 'enchants', 'food', 'potion', 'wrong build',
            'bad item', 'respec', 'talents', 'mastery', 'offspec', 'gear',
            'weapon', 'armor', 'artifact'
        ],
        'Teamfighting': [
            'teamfight', 'tf', 'engage', 'disengage', 'peel', 'dive', 'front',
            'back', 'split', 'group', 'coordination', 'follow up', 'chain cc',
            'positioning', 'formation', 'group'
        ],
        'Objective Play': [
            'objective', 'obj', 'capture', 'hold', 'push', 'defend', 'turret',
            'keep', 'farm', 'gather', 'resources', 'boss', 'mob', 'camp',
            'crystal', 'castle', 'avalon', 'league'
        ]
    }
    
    @classmethod
    def categorize(cls, text: str) -> List[str]:
        """
        Categorizes error text based on keywords.
        Returns a list of categories (maximum 3 most relevant).
        """
        if not text or not text.strip():
            return []
        
        text_lower = text.lower()
        category_scores = {}
        
        # Count keyword matches per category
        for category, keywords in cls.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                category_scores[category] = score
        
        # Sort by relevance and select top-3
        sorted_categories = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [cat for cat, _ in sorted_categories[:3]]
    
    @classmethod
    def get_all_categories(cls) -> List[str]:
        """Get the list of all categories for selection in the modal window"""
        return list(cls.CATEGORIES.keys())