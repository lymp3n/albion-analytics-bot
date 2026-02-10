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
    """Generates charts for statistics"""
    
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
        """Generates a line chart for score trends"""
        plt.figure(figsize=(7, 4))
        plt.plot(weeks, scores, marker='o', linewidth=2.5, markersize=8, 
                color=self.colors['primary'], label='Average Score')
        plt.fill_between(range(len(weeks)), scores, alpha=0.25, color=self.colors['primary'])
        
        plt.title(f'Score Trend: {player_name}', fontsize=12, pad=10)
        plt.xlabel('Week (YYYY-WW)', fontsize=9)
        plt.ylabel('Average Score', fontsize=9)
        plt.ylim(0, 10.5)
        
        # Improvement for single-point cases
        if len(weeks) == 1:
            plt.xlim(-0.5, 0.5)
            plt.xticks([0], [weeks[0]], rotation=45, ha='right', fontsize=8)
        else:
            plt.xticks(rotation=45, ha='right', fontsize=8)
            
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.legend()
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def generate_role_scores(self, roles: List[str], scores: List[float], player_name: str) -> io.BytesIO:
        """Generates a bar chart for scores by role"""
        plt.figure(figsize=(7, 4))
        bars = plt.bar(roles, scores, color=self.colors['primary'], edgecolor='white', linewidth=1.5)
        
        # Add values above the bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9)
        
        plt.title(f'Average Score by Role: {player_name}', fontsize=12, pad=10)
        plt.ylabel('Average Score', fontsize=9)
        plt.ylim(0, 10.5)
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def generate_top_players(self, players: List[str], scores: List[float]) -> io.BytesIO:
        """Generates a top-10 players chart"""
        plt.figure(figsize=(10, 6))
        y_pos = range(len(players))
        bars = plt.barh(y_pos, scores, color=self.colors['primary'], edgecolor='white', linewidth=1.5)
        
        # Add names and scores
        for i, (bar, player, score) in enumerate(zip(bars, players, scores)):
            plt.text(score + 0.15, i, f'{score:.2f}', va='center', fontsize=9)
            plt.text(0.15, i, f'#{i+1} {player}', va='center', fontsize=10, fontweight='bold')
        
        plt.title('Top 10 Alliance Players (Last 30 Days)', fontsize=16, pad=15)
        plt.xlabel('Average Score', fontsize=12)
        plt.xlim(0, max(scores) + 1 if scores else 11)
        plt.yticks([])  # Hide standard Y-axis labels
        plt.grid(axis='x', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    
    def generate_content_performance(self, contents: List[str], scores: List[float], player_name: str) -> io.BytesIO:
        """Generation of a bar chart for content performance"""
        plt.figure(figsize=(7, 4))
        bars = plt.barh(contents, scores, color=self.colors['secondary'], edgecolor='white', linewidth=1.2)
        
        for i, (bar, score) in enumerate(zip(bars, scores)):
            plt.text(score + 0.1, i, f'{score:.1f}', va='center', fontsize=9)
            
        plt.title(f'Performance by Content: {player_name}', fontsize=12, pad=10)
        plt.xlabel('Average Score', fontsize=9)
        plt.xlim(0, 11)
        plt.grid(axis='x', alpha=0.3, linestyle='--')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf

    def generate_error_distribution(self, error_types: List[str], counts: List[int], player_name: str) -> io.BytesIO:
        """Generation of a horizontal bar chart for error distribution"""
        plt.figure(figsize=(7, 4))
        y_pos = range(len(error_types))
        plt.barh(y_pos, counts, color=self.colors['danger'], alpha=0.8)
        
        plt.yticks(y_pos, error_types, fontsize=8)
        plt.title(f'Common Errors: {player_name}', fontsize=12, pad=10)
        plt.xlabel('Occurrences', fontsize=9)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=90, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf

    def cleanup_temp_files(self):
        """Cleans up temporary files older than 1 hour"""
        import time
        now = time.time()
        for filename in os.listdir('temp/charts'):
            filepath = os.path.join('temp/charts', filename)
            if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 3600:
                os.remove(filepath)