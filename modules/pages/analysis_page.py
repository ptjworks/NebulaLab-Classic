import streamlit as st
from modules.ui_workspace import render_workspace

def render_page():
    """
    Renders the Analysis Workspace Page.
    """
    # --- Dashboard Header (Minimal Whitespace) ---
    st.subheader("📊 分析工作台")
    
    # 核心工作台渲染 (Refactored to ui_workspace.py)
    render_workspace(st.container())
