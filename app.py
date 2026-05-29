"""
Nebula Lab Classic (Streamlit Edition)
======================================
核心特性：
1. [NEW] 多文件批量处理 (Multi-file Batch Processing)
2. [NEW] 瀑布图/堆叠图 (Waterfall/Overlay Plots)
3. [NEW] 多样板 AI 对比分析 (Multi-sample AI Analysis)

Upgrade: Architecture shift from single df to dictionary-based data repo.
Refactored into Modular Pages (v0.2.0 Architecture).
"""

import streamlit as st
import os
import datetime

# 从模块导入
from modules.project_manager import ProjectManager
from modules.user_manual import show_manual
from modules.state_manager import init_session_state
from modules.utils import load_config, save_config, load_chat_sessions, save_chat_sessions
# Pages
from modules.pages import data_loader_page, analysis_page, copilot_page

# ==================== Header & Global Settings ====================
st.set_page_config(
    page_title="Nebula Lab Classic",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Global Style & Protection ---
ProjectManager.inject_unload_protection()


# --- CSS Injection ---
def local_css(file_name):
    # Try basic path
    if not os.path.exists(file_name):
        # Try adjusting for different CWD (e.g. inside modules)
        # But app.py is root, so it should be fine.
        pass
    
    try:
        with open(file_name, encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"⚠️ Style file not found: {file_name}")

local_css("assets/style.css")

# [UI TWEAK] Minimal Safe Mode
st.markdown("""
    <style>
        [data-testid="stDecoration"] {display: none;}
    </style>
""", unsafe_allow_html=True)


# ==================== Config Persistence ====================
CONFIG_FILE = "ai_config.json"
HISTORY_FILE = "chat_history.json"

# Initialize Session State (Centralized)
init_session_state()

# Initialize from Config if not already set
if "config_loaded" not in st.session_state:
    cfg = load_config()
    if cfg:
        st.session_state["ai_provider"] = cfg.get("ai_provider", "Custom")
        st.session_state["ai_base_url"] = cfg.get("ai_base_url", "")
        st.session_state["ai_api_key"] = cfg.get("ai_api_key", "")
        st.session_state["ai_model_name"] = cfg.get("ai_model_name", "")
        st.toast("✅ 已加载保存的 API 配置")
    st.session_state["config_loaded"] = True

# --- Scroll-to-Top Trigger ---
if st.session_state['current_page'] != st.session_state['prev_page']:
    st.components.v1.html("""
        <script>
            window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>
    """, height=0)
    st.session_state['prev_page'] = st.session_state['current_page']

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("🌌 Nebula Lab Classic")
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
            <span style="color: #6B7280; font-size: 0.9rem; font-weight: 500;">Scientific Data Assistant</span>
            <span style="background-color: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; padding: 2px 8px; border-radius: 99px; font-size: 0.7rem; font-weight: 600;">Classic</span>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("---")
    
    # 导航栏 (Styled)
    nav_options = {
        "📁 数据加载": "数据加载", 
        "📊 分析工作台": "分析工作台", 
        "💬 AI 智能分析": "AI 智能分析"
    }
    
    current_selection = st.session_state.get("current_page", list(nav_options.keys())[0])

    if "nav_radio" not in st.session_state:
        st.session_state["nav_radio"] = current_selection
    
    st.markdown("### 🛠️ 功能导航")
    page = st.radio("", list(nav_options.keys()), 
        key="nav_radio",
        label_visibility="collapsed"
    )
    # Sync state back to current_page
    st.session_state["current_page"] = page
    
    st.markdown("---")
    
    # 全局数据看板 (Card Style)
    st.markdown("### 📚 数据仓库")
    if st.session_state['data_repo']:
        st.success(f"已加载 {len(st.session_state['data_repo'])} 个文件")
        with st.expander("查看文件列表"):
             for name in st.session_state['data_repo']:
                 st.markdown(f"📄 `{name}`")
            
        if st.button("🗑️ 清空所有数据", type="secondary", use_container_width=True):
            st.session_state['data_repo'] = {}
            st.session_state['analysis_repo'] = {}
            st.rerun()
    else:
        st.info("暂无数据")

    # ==================== 项目存取与存档 (Global Manager) ====================
    st.markdown("---")
    with st.sidebar.expander("💾 工程存档与恢复", expanded=False):
        st.caption("全域存读档：保存当前所有进度。")
        
        # --- Export ---
        if st.session_state.get('data_repo'):
            # Pre-calculate content for download button
            try:
                proj_bytes = ProjectManager.export_project()
                timestamp = datetime.datetime.now().strftime('%m%d_%H%M%S')
                filename = f"NebulaProject_{timestamp}.nbp"
                
                st.download_button(
                    label="📂 另存为工程文件",
                    data=proj_bytes,
                    file_name=filename,
                    mime="application/octet-stream",
                    use_container_width=True,
                    help="下载 .nbp 工程文件。浏览器会询问保存位置（取决于浏览器设置）。"
                )
            except Exception as e:
                st.error(f"准备存档失败: {e}")
        else:
            st.info("💡 加载数据后即可保存工程。")
        
        st.markdown("---")
        
        # --- Import ---
        uploaded_proj = st.file_uploader("📥 载入旧工程", type=['nbp'], label_visibility="collapsed", key="global_load_uploader")
        if uploaded_proj is not None:
            if st.button("🔄 确认恢复现场", use_container_width=True, type="primary", key="global_restore_btn"):
                success, g_msg = ProjectManager.import_project(uploaded_proj.read())
                if success:
                    st.success(g_msg)
                    st.rerun()
                else:
                    st.error(g_msg)
        st.markdown("---")

    # ==================== User Manual ====================
    st.markdown("---")
    if st.button("📘 使用说明书", use_container_width=True):
        show_manual()
    
    # Toggle switch for Copilot (Global toggle if needed, or just navigation)
    # The 'show_copilot' state is not heavily used in new nav structure but kept for compatibility

# ==================== 主界面 - Page Router ====================
if st.session_state["current_page"] == "📁 数据加载":
    data_loader_page.render_page()
    
elif st.session_state["current_page"] == "📊 分析工作台":
    analysis_page.render_page()
    
elif st.session_state["current_page"] == "💬 AI 智能分析":
    copilot_page.render_page()
