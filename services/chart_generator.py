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
            'dark': '#1A1C23',  # Darker background for dashboard
            'light': '#F6F8FA',
            'card': '#2D303E'   # Card background color
        }
        self.font_path = 'assets/fonts/Montserrat-Regular.ttf'
        self.font_bold_path = 'assets/fonts/Montserrat-Bold.ttf'
        
        # Configure Matplotlib fonts if available
        if os.path.exists(self.font_path):
            fm.fontManager.addfont(self.font_path)
            fm.fontManager.addfont(self.font_bold_path)
            plt.rcParams['font.family'] = 'Montserrat'
            
        os.makedirs('temp/charts', exist_ok=True)
    
    def create_player_dashboard(self, stats: dict, player_name: str, rank: str) -> io.BytesIO:
        """Generates a comprehensive single-image player dashboard"""
        # Set dark theme for the whole figure
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(10, 12), facecolor=self.colors['dark'])
        
        # Grid specification: 3 rows, 2 columns
        # Row 0: Header (merged)
        # Row 1-2: Charts
        gs = fig.add_gridspec(4, 2, height_ratios=[0.6, 1, 1, 1], hspace=0.4, wspace=0.3)
        
        # 1. Header Area (Manual Text using fig.text)
        fig.text(0.5, 0.95, player_name, fontsize=32, fontweight='bold', color='white', ha='center')
        fig.text(0.5, 0.92, f"Global Rank: #{rank} | Avg Score: {stats['avg_score']:.2f}/10 | Sessions: {stats['session_count']}", 
                 fontsize=14, color=self.colors['secondary'], ha='center')

        # 2. Score Trend (Top Left)
        ax1 = fig.add_subplot(gs[1, 0])
        ax1.plot(stats['trend_weeks'], stats['trend_scores'], marker='o', linewidth=2, color=self.colors['primary'])
        ax1.fill_between(range(len(stats['trend_weeks'])), stats['trend_scores'], alpha=0.2, color=self.colors['primary'])
        ax1.set_title('Score Trend', fontsize=12, pad=10, color=self.colors['light'])
        ax1.set_ylim(0, 10.5)
        ax1.grid(True, alpha=0.1)
        if len(stats['trend_weeks']) == 1: ax1.set_xlim(-0.5, 0.5)
        plt.setp(ax1.get_xticklabels(), rotation=45, fontsize=8)

        # 3. Role Mastery (Top Right)
        ax2 = fig.add_subplot(gs[1, 1])
        bars = ax2.bar(stats['role_names'], stats['role_scores'], color=self.colors['success'], alpha=0.8)
        ax2.set_title('Role Performance', fontsize=12, pad=10, color=self.colors['light'])
        ax2.set_ylim(0, 10.5)
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height(), f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=8)

        # 4. Content Performance (Bottom Left)
        ax3 = fig.add_subplot(gs[2, 0])
        ax3.barh(stats['content_names'], stats['content_scores'], color=self.colors['secondary'], alpha=0.8)
        ax3.set_title('Content Mastery', fontsize=12, pad=10, color=self.colors['light'])
        ax3.set_xlim(0, 10.5)
        ax3.invert_yaxis()

        # 5. Error Distribution (Bottom Right)
        ax4 = fig.add_subplot(gs[2, 1])
        if stats['error_names']:
            ax4.barh(stats['error_names'], stats['error_counts'], color=self.colors['danger'], alpha=0.8)
            ax4.set_title('Common Errors', fontsize=12, pad=10, color=self.colors['light'])
            ax4.invert_yaxis()
        else:
            ax4.text(0.5, 0.5, 'No error data yet', ha='center', va='center', color='gray')
            ax4.set_title('Common Errors', fontsize=12, pad=10, color=self.colors['light'])

        # 6. Footer
        fig.text(0.5, 0.05, f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | Albion Analytics", 
                 fontsize=10, color='gray', ha='center', alpha=0.6)

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=self.colors['dark'])
        plt.close(fig)
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