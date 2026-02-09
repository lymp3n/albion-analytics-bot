import os
import io
from datetime import datetime, timedelta
from typing import List, Tuple
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from PIL import Image, ImageDraw, ImageFont

class ChartGenerator:
    """Генерация графиков для статистики"""
    
    def __init__(self):
        self.colors = {
            'primary': '#4F7CAC',
            'secondary': '#82C0CC',
            'success': '#97D8C4',
            'danger': '#F47C7C',
            'warning': '#F7D6A0',
            'info': '#A1B0BC',
            'dark': '#333D47',
            'light': '#F6F8FA'
        }
        os.makedirs('temp/charts', exist_ok=True)
    
    def generate_score_trend(self, weeks: List[str], scores: List[float], player_name: str) -> io.BytesIO:
        """Генерация линейного графика тренда очков"""
        plt.figure(figsize=(10, 6))
        plt.plot(weeks, scores, marker='o', linewidth=2.5, markersize=8, 
                color=self.colors['primary'], label='Average Score')
        plt.fill_between(range(len(weeks)), scores, alpha=0.25, color=self.colors['primary'])
        
        plt.title(f'Score Trend: {player_name}', fontsize=16, pad=20)
        plt.xlabel('Week (YYYY-WW)', fontsize=12)
        plt.ylabel('Average Score', fontsize=12)
        plt.ylim(0, 10.5)
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.legend()
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def generate_role_scores(self, roles: List[str], scores: List[float], player_name: str) -> io.BytesIO:
        """Генерация столбчатой диаграммы по ролям"""
        plt.figure(figsize=(10, 6))
        bars = plt.bar(roles, scores, color=self.colors['primary'], edgecolor='white', linewidth=1.5)
        
        # Добавление значений над столбцами
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=11)
        
        plt.title(f'Average Score by Role: {player_name}', fontsize=16, pad=20)
        plt.ylabel('Average Score', fontsize=12)
        plt.ylim(0, 10.5)
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def generate_top_players(self, players: List[str], scores: List[float]) -> io.BytesIO:
        """Генерация топ-10 игроков"""
        plt.figure(figsize=(12, 8))
        y_pos = range(len(players))
        bars = plt.barh(y_pos, scores, color=self.colors['primary'], edgecolor='white', linewidth=1.5)
        
        # Добавление имён и очков
        for i, (bar, player, score) in enumerate(zip(bars, players, scores)):
            plt.text(score + 0.15, i, f'{score:.2f}', va='center', fontsize=10)
            plt.text(0.15, i, f'#{i+1} {player}', va='center', fontsize=11, fontweight='bold')
        
        plt.title('Top 10 Alliance Players (Last 30 Days)', fontsize=18, pad=20)
        plt.xlabel('Average Score', fontsize=14)
        plt.xlim(0, max(scores) + 1)
        plt.yticks([])  # Скрываем стандартные метки оси Y
        plt.grid(axis='x', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def cleanup_temp_files(self):
        """Очистка временных файлов старше 1 часа"""
        import time
        now = time.time()
        for filename in os.listdir('temp/charts'):
            filepath = os.path.join('temp/charts', filename)
            if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 3600:
                os.remove(filepath)