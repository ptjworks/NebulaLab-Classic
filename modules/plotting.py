"""
绘图模块 (Enhanced Plotting Module)
===================================
负责使用 Plotly 创建交互式科研风格图表
支持：
- 动态坐标轴标签
- 多曲线对比 (Overlay / Waterfall)
- 独立 X 轴支持 (Flexible X-Axis)
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from typing import Tuple, Optional, Dict, Any, List

class ChartBuilder:
    """
    科研图表构建器 (Theme Adaptive)
    """
    
    # Define schemes
    THEME_DARK = {
        "axis": "#bdc3c7", "grid": "rgba(255, 255, 255, 0.1)", "bg": "rgba(0,0,0,0)", "text": "white", "template": "plotly_dark"
    }
    THEME_LIGHT = {
        "axis": "black", "grid": "rgba(0, 0, 0, 0.1)", "bg": "white", "text": "black", "template": "simple_white"
    }

    COLORS = [
        "#2E86C1", "#00D4BD", "#E74C3C", "#F1C40F", "#9B59B6", 
        "#34495E", "#1ABC9C", "#E67E22", "#ECF0F1", "#95A5A6"
    ]
    
    def __init__(self, theme: str = 'auto'):
        # Detect Theme (Heuristic or Config or Explicit)
        
        target_base = "dark" # Default
        
        if theme != 'auto':
            target_base = theme
        else:
            try:
                 base = st.get_option("theme.base")
                 target_base = base if base else "dark"
            except:
                 target_base = "dark"
             
        self.theme = self.THEME_LIGHT if target_base == "light" else self.THEME_DARK
        
        self._config = {
            'displayModeBar': True,
            'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'displaylogo': False,
            'scrollZoom': True,
            'toImageButtonOptions': {
                'format': 'png', 'filename': 'nebula_plot', 'height': 600, 'width': 800, 'scale': 2
            }
        }
    
    def _get_base_layout(self, title: str, x_label: str, y_label: str, height: int = 550) -> Dict[str, Any]:
        """获取标准科研风格布局 (Medium Neutral Design)"""
        # Mac Font Stack
        mac_font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        
        # 使用中性色调 (Neutral Gray) 以同时适配深浅背景
        c_text = "#888888"  # 中灰色，在白底显深，黑底显浅
        c_axis = "#666666"  # 深灰色轴线
        c_grid = "rgba(128, 128, 128, 0.2)" # 淡灰色网格
        
        return dict(
            title=dict(
                text=title,
                font=dict(family=mac_font, size=20, color=c_text),
                x=0.5,
                xanchor='center',
                y=0.95
            ),
            xaxis=dict(
                title=dict(text=x_label, font=dict(family=mac_font, size=16, color=c_text)),
                tickfont=dict(family=mac_font, size=14, color=c_text),
                linecolor=c_axis,
                linewidth=1.2,
                mirror=True,
                showgrid=True,
                gridcolor=c_grid,
                zeroline=False,
                ticks='outside'
            ),
            yaxis=dict(
                title=dict(text=y_label, font=dict(family=mac_font, size=16, color=c_text)),
                tickfont=dict(family=mac_font, size=14, color=c_text),
                linecolor=c_axis,
                linewidth=1.2,
                mirror=True,
                showgrid=True,
                gridcolor=c_grid,
                zeroline=False,
                ticks='outside'
            ),
            plot_bgcolor="rgba(0,0,0,0)", # 透明背景允许穿透
            paper_bgcolor="rgba(0,0,0,0)", # 透明背景允许穿透
            legend=dict(
                font=dict(family=mac_font, size=14, color=c_text),
                bgcolor='rgba(0, 0, 0, 0)', 
                bordercolor=c_grid,
                borderwidth=1,
                x=0.98, y=0.98,
                xanchor='right', yanchor='top'
            ),
            hovermode='closest',
            margin=dict(l=80, r=40, t=80, b=80),
            height=height,
            template="none" # 避免模板强制覆盖颜色
        )

    def plot_raw(self, x_data: np.ndarray, y_data: np.ndarray, 
                 x_label: str, y_label: str, label_name: str = "原始数据",
                 title: Optional[str] = None) -> Tuple[go.Figure, Dict]:
        """绘制单条曲线"""
        if title is None: title = f"{y_label} vs {x_label}"
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_data, y=y_data,
            mode='lines',
            name=label_name,
            line=dict(color=self.COLORS[0], width=2)
        ))
        
        fig.update_layout(**self._get_base_layout(title, x_label, y_label))
        return fig, self._config

    def plot_multi_curves(self, curves: List[Dict[str, Any]],
                          x_label: str, y_label: str,
                          title: Optional[str] = None,
                          mode: str = 'overlay', # 'overlay' or 'waterfall'
                          offset: float = 0.0,
                          display_mode: str = 'lines', # 'lines', 'markers', 'lines+markers'
                          marker_size: int = 6) -> Tuple[go.Figure, Dict]:
        """
        绘制多条曲线对比 (支持独立 X 轴)
        
        参数:
            curves: List of dicts
            mode: overlay (重叠) / waterfall (瀑布)
            offset: 瀑布模式下的垂直偏移量
            display_mode: 显示模式 ('lines', 'markers', 'lines+markers')
            marker_size: 散点大小
        """
        if title is None: title = "数据对比"
        
        # Map the legacy Streamlit display mode to a Plotly trace mode.
        plotly_mode = 'lines'
        d_mode = display_mode.lower()
        
        if 'markers' in d_mode and 'lines' in d_mode:
            plotly_mode = 'lines+markers'
        elif 'markers' in d_mode:
            plotly_mode = 'markers'
        elif 'lines' in d_mode:
            plotly_mode = 'lines'
        
        fig = go.Figure()
        
        for i, curve in enumerate(curves):
            name = curve['name']
            x_vals = curve['x']
            y_vals = curve['y']
            
            # 瀑布图偏移处理
            plot_y = y_vals.copy()
            if mode == 'waterfall':
                current_offset = i * offset
                plot_y = plot_y + current_offset
            
            # 样式处理
            color = self.COLORS[i % len(self.COLORS)]
            width = 2
            dash_style = 'solid'
            
            if 'style' in curve: # 支持自定义样式覆盖
                if curve['style'] == 'dot': dash_style = 'dot'
            elif 'Derivative' in name: 
                dash_style = 'dot'
            
            fig.add_trace(go.Scatter(
                x=x_vals, y=plot_y,
                mode=plotly_mode,
                name=name,
                line=dict(color=color, width=width, dash=dash_style),
                marker=dict(size=marker_size, color=color),
                hovertemplate=f'<b>{name}</b><br>{x_label}: %{{x:.4f}}<br>{y_label}: %{{y:.4f}}<extra></extra>'
            ))
            
        layout = self._get_base_layout(title, x_label, y_label)
        fig.update_layout(**layout)
        return fig, self._config
