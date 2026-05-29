try:
    import streamlit as st
except Exception:
    st = None

def init_session_state():
    """
    Centralized initialization of all session state variables.
    Call this at the beginning of the legacy Streamlit entrypoint.
    """
    if st is None:
        raise RuntimeError("init_session_state requires Streamlit to be installed")
    
    # 1. Core Navigation & State
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "📁 数据加载"
    if "prev_page" not in st.session_state:
        st.session_state["prev_page"] = "📁 数据加载"
        
    # 2. Data Repositories
    if "data_repo" not in st.session_state:
        st.session_state['data_repo'] = {}  # {filename: df}
    if "analysis_repo" not in st.session_state:
        st.session_state['analysis_repo'] = {}  # {filename: FileAnalysisResult}
    if "settings_repo" not in st.session_state:
        st.session_state['settings_repo'] = {}  # {filename: {header, skip, ...}}
    if "file_buffers" not in st.session_state:
        st.session_state['file_buffers'] = {}   # {filename: BytesIO} for persistence
        
    # 3. Charting & Visualization
    if 'chart_styles' not in st.session_state:
        st.session_state['chart_styles'] = {}
    if "show_copilot" not in st.session_state:
        st.session_state["show_copilot"] = False
        
    # 4. AI & Chat
    if 'chat_data' not in st.session_state:
        # Check for legacy key to clean up
        if 'chat_history' in st.session_state:
            del st.session_state['chat_history']
            
        st.session_state['chat_data'] = {
            "sessions": {},
            "active_session_id": None
        }
        
    if "ai_provider" not in st.session_state:
        st.session_state["ai_provider"] = "Custom" # Default
    if 'copilot_focus_mode' not in st.session_state:
        st.session_state['copilot_focus_mode'] = False
    
    # Selection State for Analysis
    if "ai_selected_samples" not in st.session_state:
        st.session_state["ai_selected_samples"] = []

    # 5. Workspace Persistent Shadow Keys
    #    These are NEVER bound to widgets directly, so Streamlit won't purge them on tab switch.
    for pkey, default in [
        ("p_sel_samples", []),   # selected samples
        ("p_x_wb", None),       # X axis column
        ("p_y_wb", None),       # Y axis column
        ("p_plot_mode", "叠加"),  # overlay vs waterfall
        ("p_display_opt", "折线"), # line vs scatter
        ("p_waterfall_offset", 10), # waterfall offset %
        ("p_global_aliases", {}),   # Global filename aliases
    ]:
        if pkey not in st.session_state:
            st.session_state[pkey] = default
