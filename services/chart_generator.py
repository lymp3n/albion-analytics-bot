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
        """Generates a comprehensive single-image player dashboard with vertical layout"""
        # Calculate dynamic height based on content
        num_charts = 4
        base_height = 4  # Header/Footer space
        chart_height = 4
        total_height = base_height + (num_charts * chart_height)
        
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(10, total_height), facecolor=self.colors['dark'])
        
        # Grid specification: vertical stack
        gs = fig.add_gridspec(num_charts + 1, 1, height_ratios=[0.5] + [1]*num_charts, hspace=0.5)
        
        # 1. Header Area
        fig.text(0.5, 0.98, player_name, fontsize=36, fontweight='bold', color='white', ha='center')
        fig.text(0.5, 0.96, f"Global Rank: #{rank} | Avg Score: {stats['avg_score']:.2f}/10 | Sessions: {stats['session_count']}", 
                 fontsize=16, color=self.colors['secondary'], ha='center')

        # 2. Score Trend
        ax1 = fig.add_subplot(gs[1])
        ax1.plot(stats['trend_weeks'], stats['trend_scores'], marker='o', linewidth=3, color=self.colors['primary'], markersize=8)
        ax1.fill_between(range(len(stats['trend_weeks'])), stats['trend_scores'], alpha=0.2, color=self.colors['primary'])
        ax1.set_title('Score Trend (Last 30 Days)', fontsize=16, pad=20, color=self.colors['light'])
        ax1.set_ylim(0, 10.5)
        ax1.grid(True, alpha=0.1, linestyle='--')
        if len(stats['trend_weeks']) == 1: ax1.set_xlim(-0.5, 0.5)
        plt.setp(ax1.get_xticklabels(), rotation=45, fontsize=10)
        ax1.set_ylabel('Score', fontsize=12)

        # 3. Role Mastery
        ax2 = fig.add_subplot(gs[2])
        bars = ax2.bar(stats['role_names'], stats['role_scores'], color=self.colors['success'], edgecolor='white', alpha=0.8, width=0.6)
        ax2.set_title('Performance by Role', fontsize=16, pad=20, color=self.colors['light'])
        ax2.set_ylim(0, 10.5)
        ax2.grid(axis='y', alpha=0.1, linestyle='--')
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1, f'{bar.get_height():.1f}', 
                    ha='center', va='bottom', fontsize=12, fontweight='bold', color=self.colors['light'])

        # 4. Content Performance
        ax3 = fig.add_subplot(gs[3])
        bars3 = ax3.barh(stats['content_names'], stats['content_scores'], color=self.colors['secondary'], alpha=0.8)
        ax3.set_title('Content Mastery', fontsize=16, pad=20, color=self.colors['light'])
        ax3.set_xlim(0, 10.5)
        ax3.grid(axis='x', alpha=0.1, linestyle='--')
        for i, bar in enumerate(bars3):
            ax3.text(bar.get_width() + 0.1, i, f'{bar.get_width():.1f}', va='center', fontsize=12, color=self.colors['light'])

        # 5. Error Distribution
        ax4 = fig.add_subplot(gs[4])
        if stats['error_names']:
            # Adjust bar colors for errors
            bars4 = ax4.barh(stats['error_names'], stats['error_counts'], color=self.colors['danger'], alpha=0.8)
            ax4.set_title('Most Common Mistakes', fontsize=16, pad=20, color=self.colors['light'])
            ax4.grid(axis='x', alpha=0.1, linestyle='--')
            # Set integer ticks for counts
            from matplotlib.ticker import MaxNLocator
            ax4.xaxis.set_major_locator(MaxNLocator(integer=True))
            for i, bar in enumerate(bars4):
                ax4.text(bar.get_width() + 0.1, i, f' {int(bar.get_width())}', va='center', fontsize=12, color=self.colors['light'])
        else:
            ax4.text(0.5, 0.5, 'No error data recorded for this period', ha='center', va='center', color='gray', fontsize=14)
            ax4.set_title('Common Errors', fontsize=16, pad=20, color=self.colors['light'])
            ax4.set_axis_off()

        # 6. Footer
        fig.text(0.5, 0.02, f"Dashboard Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | Powered by Albion Analytics", 
                 fontsize=12, color='gray', ha='center', alpha=0.6)

        # Final adjustments
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=self.colors['dark'])
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_top_players(self, players: List[str], scores: List[float]) -> io.BytesIO:
        """Generates a modern top-10 players chart"""
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 8), facecolor=self.colors['dark'])
        
        y_pos = range(len(players))
        bars = ax.barh(y_pos, scores, color=self.colors['primary'], alpha=0.8, edgecolor='white', linewidth=1)
        
        # Add names and scores inside/beside bars
        for i, (bar, player, score) in enumerate(zip(bars, players, scores)):
            # Ranking label
            rank_text = f"#{len(players)-i}"
            ax.text(0.2, i, f"{rank_text} {player}", va='center', fontsize=14, fontweight='bold', color='white')
            # Score label
            ax.text(score + 0.1, i, f'{score:.2f}', va='center', fontsize=14, color=self.colors['secondary'])
        
        ax.set_title('Top 10 Players (Total Score + Quality)', fontsize=22, pad=30, fontweight='bold', color='white')
        ax.set_xlabel('Average Score', fontsize=14, color=self.colors['light'], labelpad=20)
        ax.set_xlim(0, max(scores) + 1.5 if scores else 11)
        ax.set_yticks([]) # Hide Y ticks
        ax.grid(axis='x', alpha=0.1, linestyle='--')
        
        # Footer
        fig.text(0.5, 0.01, f"Global Rankings | {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC", 
                 fontsize=10, color='gray', ha='center', alpha=0.6)
        
        plt.tight_layout(rect=[0, 0.05, 1, 1])
        
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