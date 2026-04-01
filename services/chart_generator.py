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
        """Generates an expanded player dashboard card with player + guild charts."""
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(18, 19), facecolor=self.colors['dark'])
        
        # Grid: header + 4 chart rows, 2 charts per row
        gs = fig.add_gridspec(5, 2, height_ratios=[0.85, 1, 1, 1, 1], hspace=0.4, wspace=0.24)
        
        # 1. Header Area & Metric Cards
        ax_header = fig.add_subplot(gs[0, :])
        ax_header.set_axis_off()
        ax_header.set_xlim(0, 1)
        ax_header.set_ylim(-0.1, 1.1)
        
        # Title
        ax_header.text(0.5, 0.97, player_name, fontsize=32, fontweight='bold', color='white', ha='center', va='center')
        ax_header.text(0.5, 0.78, f"G L O B A L   R A N K :  #{rank}", fontsize=14, color=self.colors['warning'], ha='center', va='center', fontweight='bold')
        
        import matplotlib.patches as mpatches
        def draw_metric_card(ax, x, y, width, height, title1, val1, title2, val2, color):
            box = mpatches.FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.03,rounding_size=0.03", 
                                          facecolor=self.colors['card'], edgecolor=color, linewidth=1.5)
            ax.add_patch(box)
            ax.text(x + width/2, y + height*0.82, title1, fontsize=11, color=self.colors['info'], ha='center', va='center')
            ax.text(x + width/2, y + height*0.55, str(val1), fontsize=20, fontweight='bold', color='white', ha='center', va='center')
            ax.text(x + width/2, y + height*0.28, title2, fontsize=11, color=self.colors['info'], ha='center', va='center')
            ax.text(x + width/2, y + height*0.06, str(val2), fontsize=15, fontweight='bold', color='white', ha='center', va='center')

        # Calculations
        total_ev = stats.get('total_events', 0)
        att_ev = stats.get('attended_events', 0)
        att_pct = (att_ev / total_ev * 100) if total_ev > 0 else 0
        total_errors = sum(stats.get('error_counts', []))
        last_s = stats.get('last_session', 'N/A')
        if hasattr(last_s, 'strftime'): last_s = last_s.strftime('%Y-%m-%d')
        coverage_pct = float(stats.get('content_coverage_pct', 0.0))
        covered_cnt = int(stats.get('distinct_content_count', 0))
        total_cnt = int(stats.get('total_content_count', 0))
        
        # Draw 4 Cards
        card_w, card_h = 0.22, 0.65
        draw_metric_card(ax_header, 0.03, 0.0, card_w, card_h, "TOTAL SESSIONS", stats['session_count'], "AVERAGE SCORE", f"{stats['avg_score']:.2f}", self.colors['primary'])
        draw_metric_card(ax_header, 0.28, 0.0, card_w, card_h, "EVENTS ATTENDED", f"{att_ev} / {total_ev}", "ATTENDANCE RATE", f"{att_pct:.1f}%", self.colors['success'])
        draw_metric_card(ax_header, 0.53, 0.0, card_w, card_h, "BEST ROLE (BY SCORE)", stats['best_role'] or 'N/A', "CONTENT COVERAGE", f"{coverage_pct:.1f}%", self.colors['secondary'])
        draw_metric_card(ax_header, 0.78, 0.0, card_w, card_h, "MISTAKES LOGGED", str(total_errors), "LAST SESSION", str(last_s), self.colors['danger'])
        ax_header.text(0.64, -0.05, f"Covered: {covered_cnt}/{total_cnt} content types", fontsize=10, color=self.colors['info'], ha='center')

        # 1) Trend average score by week
        ax1 = fig.add_subplot(gs[1, 0])
        ax1.plot(stats['trend_weeks'], stats['trend_scores'], marker='o', linewidth=3, color=self.colors['primary'], markersize=8)
        ax1.fill_between(range(len(stats['trend_weeks'])), stats['trend_scores'], alpha=0.2, color=self.colors['primary'])
        ax1.set_title('Trend: Average Score by Week', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
        ax1.set_ylim(0, 10.5)
        ax1.grid(True, alpha=0.1, linestyle='--')
        if len(stats['trend_weeks']) == 1: ax1.set_xlim(-0.5, 0.5)
        plt.setp(ax1.get_xticklabels(), rotation=28, fontsize=9, ha='right')
        ax1.set_ylabel('Score (0-10)', fontsize=11, color=self.colors['info'])

        # 2) Average score by content
        ax2 = fig.add_subplot(gs[1, 1])
        bars2 = ax2.bar(stats['content_names'], stats['content_scores'], color=self.colors['secondary'], edgecolor='white', alpha=0.85, width=0.55)
        ax2.set_title('Average Score by Content', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
        ax2.set_ylim(0, 10.5)
        ax2.grid(axis='y', alpha=0.1, linestyle='--')
        plt.setp(ax2.get_xticklabels(), rotation=28, fontsize=9, ha='right')
        for bar in bars2:
            ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.2, f'{bar.get_height():.1f}', 
                    ha='center', va='bottom', fontsize=9, fontweight='bold', color=self.colors['light'])

        # 3) Player error distribution (pie)
        ax3 = fig.add_subplot(gs[2, 0])
        if stats['error_names'] and stats['error_counts']:
            pie_colors = ['#F47C7C', '#F7A072', '#F2CC8F', '#81B29A', '#6D597A']
            ax3.pie(
                stats['error_counts'],
                labels=stats['error_names'],
                autopct='%1.0f%%',
                startangle=120,
                textprops={'color': 'white', 'fontsize': 9},
                wedgeprops={'linewidth': 1, 'edgecolor': self.colors['dark']},
                colors=pie_colors[:len(stats['error_counts'])]
            )
            ax3.set_title('Error Type Distribution', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
        else:
            ax3.text(0.5, 0.5, 'No errors in selected period', ha='center', va='center', color=self.colors['success'], fontsize=12)
            ax3.set_title('Error Type Distribution', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax3.set_axis_off()

        # 4) Error count vs score correlation (scatter)
        ax4 = fig.add_subplot(gs[2, 1])
        points = stats.get('error_score_points', [])
        if points:
            xs = [p['errors'] for p in points]
            ys = [p['score'] for p in points]
            ax4.scatter(xs, ys, s=50, alpha=0.75, color=self.colors['warning'], edgecolor='white', linewidth=0.8)
            ax4.set_title('Error Count vs Score', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax4.set_xlabel('Errors in Session', fontsize=10, color=self.colors['info'])
            ax4.set_ylabel('Score', fontsize=10, color=self.colors['info'])
            ax4.set_ylim(0, 10.5)
            from matplotlib.ticker import MaxNLocator
            ax4.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax4.grid(alpha=0.12, linestyle='--')
        else:
            ax4.text(0.5, 0.5, 'No session points available', ha='center', va='center', color=self.colors['success'], fontsize=12)
            ax4.set_title('Error Count vs Score', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax4.set_axis_off()

        # 5) Event content attendance frequency (closed events only)
        ax5 = fig.add_subplot(gs[3, 0])
        ev_names = stats.get('event_content_names', [])
        ev_counts = stats.get('event_content_counts', [])
        if ev_names and ev_counts:
            bars5 = ax5.bar(ev_names, ev_counts, color=self.colors['primary'], alpha=0.85)
            ax5.set_title('Event Attendance Frequency by Content', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax5.grid(axis='y', alpha=0.1, linestyle='--')
            plt.setp(ax5.get_xticklabels(), rotation=28, fontsize=9, ha='right')
            for bar in bars5:
                ax5.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05, f"{int(bar.get_height())}", ha='center', va='bottom', fontsize=9, color='white')
        else:
            ax5.text(0.5, 0.5, 'No closed-event attendance yet', ha='center', va='center', color=self.colors['info'], fontsize=12)
            ax5.set_title('Event Attendance Frequency by Content', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax5.set_axis_off()

        # 6) Role performance by score (player)
        ax6 = fig.add_subplot(gs[3, 1])
        role_names = stats.get('role_names', [])
        role_scores = stats.get('role_scores', [])
        if role_names and role_scores:
            bars6 = ax6.bar(role_names, role_scores, color=self.colors['success'], edgecolor='white', alpha=0.85, width=0.55)
            ax6.set_title('Player: Average Score by Role', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax6.set_ylim(0, 10.5)
            ax6.grid(axis='y', alpha=0.1, linestyle='--')
            plt.setp(ax6.get_xticklabels(), rotation=20, fontsize=9, ha='right')
            for bar in bars6:
                ax6.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.15, f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=9, color='white')
        else:
            ax6.text(0.5, 0.5, 'No role stats available', ha='center', va='center', color=self.colors['info'], fontsize=12)
            ax6.set_title('Player: Average Score by Role', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax6.set_axis_off()

        # 7) Guild-wide role distribution
        ax7 = fig.add_subplot(gs[4, 0])
        g_roles = stats.get('guild_role_names', [])
        g_counts = stats.get('guild_role_counts', [])
        if g_roles and g_counts:
            bars7 = ax7.bar(g_roles, g_counts, color='#A78BFA', alpha=0.9)
            ax7.set_title('Guild Overall: Role Distribution', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax7.grid(axis='y', alpha=0.1, linestyle='--')
            plt.setp(ax7.get_xticklabels(), rotation=20, fontsize=9, ha='right')
            for bar in bars7:
                ax7.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1, f"{int(bar.get_height())}", ha='center', va='bottom', fontsize=9, color='white')
        else:
            ax7.text(0.5, 0.5, 'No guild role data', ha='center', va='center', color=self.colors['info'], fontsize=12)
            ax7.set_title('Guild Overall: Role Distribution', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax7.set_axis_off()

        # 8) Guild-wide top error types
        ax8 = fig.add_subplot(gs[4, 1])
        g_err_names = stats.get('guild_error_names', [])
        g_err_counts = stats.get('guild_error_counts', [])
        if g_err_names and g_err_counts:
            bars8 = ax8.bar(g_err_names, g_err_counts, color='#FB7185', alpha=0.9)
            ax8.set_title('Guild Overall: Top 5 Error Types', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax8.grid(axis='y', alpha=0.1, linestyle='--')
            plt.setp(ax8.get_xticklabels(), rotation=24, fontsize=9, ha='right')
            for bar in bars8:
                ax8.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1, f"{int(bar.get_height())}", ha='center', va='bottom', fontsize=9, color='white')
        else:
            ax8.text(0.5, 0.5, 'No guild error data', ha='center', va='center', color=self.colors['info'], fontsize=12)
            ax8.set_title('Guild Overall: Top 5 Error Types', fontsize=14, pad=10, color=self.colors['light'], fontweight='bold')
            ax8.set_axis_off()

        # Footer
        fig.text(0.5, 0.02, f"Dashboard Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | Powered by Albion Analytics", 
                 fontsize=10, color='gray', ha='center', alpha=0.5)

        # Better compact layout algorithm to eliminate empty spacing
        plt.subplots_adjust(top=0.97, bottom=0.05, left=0.05, right=0.97, hspace=0.42, wspace=0.24)
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, facecolor=self.colors['dark'])
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