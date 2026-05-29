import streamlit as st
import time
from modules.ai_agent import AIAnalyzer, AI_PROVIDERS
from modules.utils import load_config, save_config, save_chat_sessions, estimate_tokens

def render_page():
    """
    Renders the AI Copilot Page.
    """
    st.subheader("💬 AI 智能分析")
    
    # 2-Column Layout for Localized Control
    col_ctrl, col_chat = st.columns([1, 2])
    
    with col_ctrl:
        st.markdown("#### 🛠️ 控制面板")
        
        # 1. AI Model Settings (Moved here)
        with st.expander("🔌 AI 模型配置", expanded=False):
            provider_list = list(AI_PROVIDERS.keys())
            saved_provider = st.session_state.get("ai_provider", provider_list[0])
            try:
                p_index = provider_list.index(saved_provider)
            except ValueError:
                p_index = 0
                
            # [FIX] Auto-update settings when provider changes
            def on_provider_change():
                # This callback runs BEFORE the script rerun
                new_p = st.session_state["ai_p_local"]
                if new_p in AI_PROVIDERS:
                    cfg = AI_PROVIDERS[new_p]
                    # Direct update of widget keys
                    st.session_state["ai_u_local"] = cfg.base_url
                    # Also reset model if possible (handling selectbox vs text input is tricky, 
                    # but usually updating the session state key works for the next render)
                    if cfg.models:
                        st.session_state["ai_m_local"] = cfg.default_model
                    else:
                        st.session_state["ai_m_local_text"] = cfg.default_model

            ai_provider = st.selectbox("服务商", options=provider_list, index=p_index, key="ai_p_local", on_change=on_provider_change)
            p_cfg = AI_PROVIDERS[ai_provider]
            
            # Ensure widget keys are initialized if missing (to avoid KeyErrors on first run)
            if "ai_u_local" not in st.session_state: st.session_state["ai_u_local"] = p_cfg.base_url
            
            ai_base_url = st.text_input("Base URL", key="ai_u_local")
            ai_api_key = st.text_input("API Key", type="password", value=st.session_state.get('ai_api_key', ''))
            
            # Fetch Models
            if st.button("🔄 刷新模型", use_container_width=True):
                if ai_api_key and ai_base_url:
                    with st.spinner("获取中..."):
                        fetched = AIAnalyzer.fetch_available_models(ai_api_key, ai_base_url)
                        if fetched:
                            p_cfg.models = fetched
                            st.rerun()
                
            if p_cfg.models:
                current_model = st.session_state.get('ai_model_name', p_cfg.default_model)
                model_options = p_cfg.models
                try:
                    def_idx = model_options.index(current_model)
                except:
                    def_idx = 0
                ai_model_name = st.selectbox("Model", options=model_options, index=def_idx, key="ai_m_local")
            else:
                ai_model_name = st.text_input("Model", value=st.session_state.get('ai_model_name', p_cfg.default_model), key="ai_m_local_text")

            if st.button("💾 保存配置"):
                new_cfg = {"ai_provider": ai_provider, "ai_base_url": ai_base_url, "ai_api_key": ai_api_key, "ai_model_name": ai_model_name}
                save_config(new_cfg)
                st.success("已保存")

            # Update session state
            st.session_state.update({
                'ai_provider': ai_provider, 'ai_base_url': ai_base_url, 'ai_api_key': ai_api_key, 'ai_model_name': ai_model_name
            })

        # 2. Sample Selection (Multi-select)
        st.markdown("---")
        st.markdown("##### 📁 分析目标")
        all_samples = list(st.session_state['data_repo'].keys())
        
        if not all_samples:
            st.warning("⚠️ 仓库中没有数据，无法分析。")
        else:
            def on_select_all():
                st.session_state["ai_sample_selector"] = all_samples
                st.session_state["ai_selected_samples"] = all_samples
                
            def on_clear_all():
                st.session_state["ai_sample_selector"] = []
                st.session_state["ai_selected_samples"] = []

            col_sel1, col_sel2 = st.columns(2)
            col_sel1.button("✅ 全选", use_container_width=True, on_click=on_select_all)
            col_sel2.button("❌ 清空", use_container_width=True, on_click=on_clear_all)
                
            selected_samples = st.multiselect(
                "选择要分析的样本",
                options=all_samples,
                default=st.session_state.get("ai_selected_samples", []),
                key="ai_sample_selector"
            )
            st.session_state["ai_selected_samples"] = selected_samples

        # 3. Context Toggles
        st.markdown("---")
        st.markdown("##### 📎 上下文配置")
        ctx_summary = st.checkbox("📊 数据摘要", value=True)
        ctx_image = st.checkbox("🖼️ 图表快照", value=True, help="将工作台中最近一次生成的图表发送给 AI (需要 Vision 模型支持)")
        ctx_full = st.checkbox("📄 原始数据", value=False)
        
        # 4. History & Metrics
        st.markdown("---")
        # Use current session messages for token estimation
        current_msgs = st.session_state['chat_data']['sessions'].get(st.session_state['chat_data'].get('active_session_id', 'default'), {}).get('messages', [])
        tokens = estimate_tokens(current_msgs)
        st.metric("预估消耗 Token", tokens)
        
        if st.button("🗑️ 删除此会话", use_container_width=True, help="永久删除当前对话记录"):
            # Delete logic
            sid = st.session_state['chat_data']['active_session_id']
            if sid in st.session_state['chat_data']['sessions']:
                del st.session_state['chat_data']['sessions'][sid]
            
            # Fallback logic
            remaining_ids = list(st.session_state['chat_data']['sessions'].keys())
            if remaining_ids:
                st.session_state['chat_data']['active_session_id'] = remaining_ids[-1]
            else:
                # Create default if empty
                new_id = "default"
                st.session_state['chat_data']['sessions'][new_id] = {
                    "id": new_id, "title": "默认对话", "messages": []
                }
                st.session_state['chat_data']['active_session_id'] = new_id
                
            save_chat_sessions(st.session_state['chat_data'])
            st.rerun()

    with col_chat:
        # Session Management UI
        c_sess_1, c_sess_2 = st.columns([3, 1])
        
        # Ensure state validity
        chat_data = st.session_state['chat_data']
        active_id = chat_data.get('active_session_id', 'default')
        if active_id not in chat_data['sessions']:
            if not chat_data['sessions']:
                # Create default session if none exist
                default_id = "default"
                chat_data['sessions'][default_id] = {
                    "id": default_id, "title": "默认对话", "messages": []
                }
                active_id = default_id
            else:
                active_id = list(chat_data['sessions'].keys())[0]
            chat_data['active_session_id'] = active_id

        current_session = chat_data['sessions'][active_id]
        
        with c_sess_1:
            # Session Selector
            session_options = list(chat_data['sessions'].keys())
            # Format display labels
            def format_func(sid):
                s = chat_data['sessions'][sid]
                return f"{s['title']} ({len(s['messages'])})"
            
            selected_id = st.selectbox(
                "当前会话", 
                session_options, 
                index=session_options.index(active_id),
                format_func=format_func,
                label_visibility="collapsed",
                key="session_selector"
            )
            
            # Switch Logic
            if selected_id != active_id:
                chat_data['active_session_id'] = selected_id
                st.rerun()

        with c_sess_2:
            if st.button("➕ 新对话", use_container_width=True, help="Create New Chat"):
                new_id = f"session_{int(time.time())}"
                chat_data['sessions'][new_id] = {
                    "id": new_id, 
                    "title": f"New Chat {len(chat_data['sessions'])+1}", 
                    "messages": []
                }
                chat_data['active_session_id'] = new_id
                save_chat_sessions(chat_data)
                st.rerun()

        history_container = st.container(height=550)
        with history_container:
            if not current_session['messages']:
                st.chat_message("assistant").write("🔬 您好！我是您的科研数据助手。请先在左侧选择样本并配置模型。")
            else:
                for msg in current_session['messages']:
                    st.chat_message(msg["role"]).write(msg["content"])

        prompt_input = st.chat_input("在此提问 (例如: '对比这几个样品的信噪比' 或 '分析峰值变化趋势')...")
        
        # Unify prompt source
        # prompt = prompt_input or preset_prompt # preset_prompt removed for now or needs to be passed in
        prompt = prompt_input # Simplified for now

        if prompt:
            # Add user msg to current session
            current_session['messages'].append({"role": "user", "content": prompt})
            
            # Auto-rename if first message
            if len(current_session['messages']) == 1:
                current_session['title'] = prompt[:15] + "..."
                
            st.chat_message("user").write(prompt)
            
            # Check requirements
            ai_api_key = st.session_state.get('ai_api_key')
            ai_base_url = st.session_state.get('ai_base_url')
            
            if not ai_api_key or not ai_base_url:
                st.error("🚫 请先配置 API Key 和 Base URL")
            elif not st.session_state.get("ai_selected_samples"):
                st.error("⚠️ 请先选择至少一个样本作为分析对象")
            else:
                try:
                    # Prepare context
                    context_msgs = []
                    # System Prompt
                    sys_prompt = "You are an expert material science assistant. Analyze the user's data."
                    context_msgs.append({"role": "system", "content": sys_prompt})
                    
                    # Data Context Injection
                    target_samples = st.session_state["ai_selected_samples"]
                    
                    # 1. Summary (Always on if checked)
                    if ctx_summary:
                        summary_text = "【数据摘要】\n"
                        for name in target_samples:
                            if name in st.session_state['data_repo']:
                                df = st.session_state['data_repo'][name]
                                summary_text += f"- Sample {name}: {df.shape[0]} rows, Cols: {list(df.columns)}\n"
                        context_msgs.append({"role": "system", "content": summary_text})
                        
                    # 2. Raw Data (Heavy)
                    if ctx_full:
                        raw_text = "【原始数据采样】\n"
                        for name in target_samples:
                            if name in st.session_state['data_repo']:
                                df = st.session_state['data_repo'][name]
                                # Limit to first 20 lines to avoid explosive tokens
                                raw_text += f"File: {name} (Top 20 rows)\n{df.head(20).to_csv(index=False)}\n\n"
                        context_msgs.append({"role": "system", "content": raw_text})

                    # Append Chat History (Limit context window if needed, here taking all for simplicty or last N)
                    # Filter out systems to avoid duplication if we re-inject
                    user_assist_history = [m for m in current_session['messages'] if m['role'] in ['user', 'assistant']]
                    context_msgs.extend(user_assist_history)

                    with history_container:
                        with st.chat_message("assistant"):
                            with st.spinner("Analyzing..."):
                                # If Vision needed (ctx_image), we need a different call path
                                # For now, standard text
                                analyzer = AIAnalyzer(
                                    base_url=ai_base_url,
                                    api_key=ai_api_key, 
                                    model=st.session_state.get('ai_model_name', 'default')
                                )
                                
                                stream = analyzer.chat_stream(context_msgs)
                                full_response = st.write_stream(stream)
                    
                    # Save assistant response
                    current_session['messages'].append({"role": "assistant", "content": full_response})
                    save_chat_sessions(chat_data)
                    
                except Exception as e:
                    st.error(f"AI Error: {str(e)}")
