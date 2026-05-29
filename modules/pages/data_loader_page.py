import streamlit as st
import pandas as pd
from io import BytesIO
from modules.data_loader import DataLoader, DataAnalyzer
from modules.rule_manager import RuleManager
from modules.utils import settings_to_rule, rule_to_settings

def render_page():
    """
    Renders the Data Loading / Analysis Setup Tab.
    """
    st.markdown("### 📥 数据导入工作流")
    st.info("请按照以下步骤清洗并加载您的实验数据。")

    # --- [Feature] 明确显示已加载的数据 (Persistence Check) ---
    if st.session_state['data_repo']:
        with st.expander(f"📚 已加载数据仓库 (共 {len(st.session_state['data_repo'])} 个文件)", expanded=False):
            st.dataframe(
                pd.DataFrame([
                    {"File Name": k, "Rows": v.shape[0], "Cols": v.shape[1], "Columns": ", ".join(map(str, v.columns))}
                    for k, v in st.session_state['data_repo'].items()
                ]),
                use_container_width=True,
                hide_index=True
            )
            if st.button("🗑️ 清空所有数据", key="clear_all_top"):
                st.session_state['data_repo'] = {}
                st.session_state['analysis_repo'] = {}
                st.session_state['settings_repo'] = {}
                st.rerun()
            st.markdown("---")
    
    # [FIX] Uploader Key Rotation to force clear
    if 'uploader_key' not in st.session_state:
        st.session_state['uploader_key'] = 0

    # 1. 批量上传
    uploaded_files = st.file_uploader(
        "选择数据文件 (支持多选)", 
        type=['csv', 'txt', 'xlsx', 'xls', 'dat', 'xy', 'asc'],
        accept_multiple_files=True,
        # Key 动态化，改变 key 会强制重置控件
        key=f"main_file_uploader_{st.session_state['uploader_key']}" 
    )

    # [Persistence] Cache uploaded files
    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state["file_buffers"]:
                # Copy content to memory to persist across reruns
                f.seek(0)
                file_content = f.read()
                buf = BytesIO(file_content)
                buf.name = f.name # Essential for file type detection
                st.session_state["file_buffers"][f.name] = buf

    # Use cached buffers as source of truth
    if st.session_state["file_buffers"]:
        # 1.1 Clear Button
        # [FIX] 彻底清空逻辑
        if st.button("🗑️ 清空所有源文件", help="清除缓存的原始文件，重新上传"):
            st.session_state["file_buffers"] = {}
            st.session_state["settings_repo"] = {}
            st.session_state["analysis_repo"] = {}
            st.session_state["data_repo"] = {} # Also clear processed data? Yes.
            
            # Rotate key to reset uploader widget
            st.session_state['uploader_key'] += 1
            st.rerun()

        # Reconstruct file_map from buffers
        file_map = st.session_state["file_buffers"]
        file_names = list(file_map.keys())
        
        # 2. 选择当前要配置的文件
        col_sel, col_act = st.columns([3, 1])
        with col_sel:
            # 2.1 Quick Filter
            filter_query = st.text_input("🔍 筛选文件名", placeholder="输入关键字查找文件...", label_visibility="collapsed")
            
            # 2.2 Apply Filter
            if filter_query:
                filtered_names = [f for f in file_names if filter_query.lower() in f.lower()]
                if not filtered_names:
                    st.warning("⚠️ 无匹配文件")
                    filtered_names = file_names # Fallback
            else:
                filtered_names = file_names
                
            selected_fname = st.selectbox("🛠️ 选择要配置的文件:", filtered_names)
        
        current_file = file_map[selected_fname]
        
        # 3. 逐个分析逻辑
        # 检查是否已分析过
        if selected_fname not in st.session_state['analysis_repo']:
            with st.spinner(f"正在嗅探 {selected_fname}..."):
                try:
                    current_file.seek(0)
                    analysis = DataAnalyzer().analyze(current_file)
                    st.session_state['analysis_repo'][selected_fname] = analysis
                    # 初始化默认参数
                    default_params = {
                        'file_type': analysis.file_type, 'encoding': analysis.encoding,
                        'use_header': analysis.has_header, 'header_row': analysis.header_row,
                        'skip_rows': analysis.skip_rows,
                        'delimiter': analysis.delimiter if analysis.delimiter else None,
                        'sheet_name': analysis.sheet_names[0] if analysis.sheet_names else 0,
                        'column_aliases': {c: c for c in analysis.suggested_columns}, # Initialize with suggested
                        'transformations': []
                    }
                    st.session_state['settings_repo'][selected_fname] = default_params
                except Exception as e:
                    st.error(f"分析失败: {e}")
                    st.stop()
        
        analysis = st.session_state['analysis_repo'][selected_fname]
        current_settings = st.session_state['settings_repo'][selected_fname]
        
        # --- 🧩 规则管理 (Sidebar) ---
        with st.sidebar:
            st.markdown("---")
            st.markdown("### ⚙️ 规则管理")
            
            rm = RuleManager()
            
            # 1. Load Rule
            rule_list = rm.list_rules()
            if rule_list:
                st.caption("加载已有规则:")
                selected_rule_name = st.selectbox("选择模板", rule_list, key="rule_sel_sb", label_visibility="collapsed")
                
                # Actions action
                col_load, col_del = st.columns([1, 1])
                if col_load.button("📂 加载", use_container_width=True):
                    rule_obj = rm.load_rule(selected_rule_name)
                    if rule_obj:
                        new_settings = rule_to_settings(rule_obj)
                        # Update current settings (keeping dict reference same if possible, or update keys)
                        # We must ensure 'transformations' objects are clean
                        st.session_state['settings_repo'][selected_fname] = new_settings
                        
                        # [FIX] Force update widget keys to prevent stale state from overwriting settings
                        # Strategy: Aggressively clear ALL widget states related to this file.
                        # Any key containing "_{selected_fname}" is considered a widget key for this file.
                        keys_to_del = [k for k in st.session_state.keys() if f"_{selected_fname}" in k]
                        
                        count = 0
                        for k in keys_to_del:
                            del st.session_state[k]
                            count += 1

                        st.toast(f"✅ 已应用规则: {selected_rule_name} (重置了 {count} 个控件状态)")
                        st.rerun()
                
                if col_del.button("🗑️", help="删除此规则"):
                    rm.delete_rule(selected_rule_name)
                    st.rerun()
            
            st.markdown("---")
            
            # 2. Save Rule
            st.caption("保存当前配置:")
            save_name = st.text_input("规则名称", placeholder="e.g. MyProcess_A", key="rule_save_name")
            
            # Save Action
            if st.button("💾 保存到库", use_container_width=True):
                if save_name:
                    rule_obj = settings_to_rule(save_name, current_settings)
                    rm.save_rule(rule_obj)
                    st.toast(f"💾 规则已保存: {save_name}")
                    st.rerun() # To update the list above
                else:
                    st.warning("⚠️ 请输入名称")

            st.markdown("---")
            
            # [NEW] Global Alias - Global "Artistic" Name
            with st.expander("🏷️ 批量重命名", expanded=False):
                st.caption("为加载的文件设置全局显示名称：")
                g_aliases = st.session_state.get('p_global_aliases', {})
                current_fnames = list(st.session_state['file_buffers'].keys())
                
                if not current_fnames:
                    st.info("💡 请先上传文件")
                else:
                    for f_name in current_fnames:
                        # Display raw name then input
                        st.markdown(f"<p style='font-size:0.8rem; margin-bottom:0; opacity:0.6;'>原始名: {f_name}</p>", unsafe_allow_html=True)
                        new_alias = st.text_input("Alias", value=g_aliases.get(f_name, f_name), key=f"g_alias_in_{f_name}", label_visibility="collapsed")
                        if new_alias != g_aliases.get(f_name, f_name):
                            g_aliases[f_name] = new_alias
                            st.session_state['p_global_aliases'] = g_aliases
                            # We don't necessarily need rerun here, but good for immediate persistence
                    
                    if st.button("🔄 同步别名到本地", use_container_width=True, help="点击可强制同步一次别名库"):
                        st.rerun()

            st.markdown("---")
            with st.expander("📤 导入/导出", expanded=False):
                # 3.1 Export Current Settings directly
                if save_name: # If user typed a name, allow direct download 
                    # This is for "Save As File" without saving to library first
                    rule_direct = settings_to_rule(save_name, current_settings)
                    st.download_button(
                        label="📤 导出当前配置",
                        data=rule_direct.model_dump_json(indent=2),
                        file_name=f"{save_name}.nbr",
                        mime="application/json",
                        help="直接下载当前配置为规则文件（不存入库）"
                    )

                # 3.2 Export Selected Library Rule
                if rule_list and selected_rule_name:
                     rule_out = rm.load_rule(selected_rule_name)
                     if rule_out:
                        st.download_button(
                            label=f"📥 导出规则 '{selected_rule_name}'",
                            data=rule_out.model_dump_json(indent=2),
                            file_name=f"{selected_rule_name}.nbr",
                            mime="application/json"
                        )
                
                st.divider()
                
                # 3.3 Import
                uploaded_rule = st.file_uploader("导入规则文件", type=['nbr'], key="rule_import_up")
                if uploaded_rule:
                    try:
                        content = uploaded_rule.read().decode('utf-8')
                        from modules.schemas import CleaningRule
                        rule_in = CleaningRule.model_validate_json(content)
                        
                        col_imp_load, col_imp_save = st.columns(2)
                        
                        # A. Direct Load
                        if col_imp_load.button("⚡ 仅加载", help="仅应用到当前界面，不保存到库"):
                             new_settings = rule_to_settings(rule_in)
                             st.session_state['settings_repo'][selected_fname] = new_settings
                             st.toast(f"✅ 已应用外部规则: {rule_in.name}")
                             st.rerun()

                        # B. Save to Lib
                        if col_imp_save.button("💾 存入库"):
                             rm.save_rule(rule_in)
                             st.success(f"已存入: {rule_in.name}")
                             st.rerun()
                             
                    except Exception as e:
                        st.error(f"无效文件: {e}")


        
        loader = DataLoader()
        
        # 3. Dry run to get available columns (without aliases/transforms)
        # 提前获取列列表，以便配置区和预览区都能使用
        try:
            dry_settings = current_settings.copy()
            dry_settings['column_aliases'] = {}
            dry_settings['transformations'] = []
            current_file.seek(0)
            df_raw_clean = loader.load(current_file, dry_settings)
            available_cols = list(df_raw_clean.columns)
        except Exception as e:
            st.error(f"解析原始列失败: {e}")
            st.stop()

        # 4. 全宽信息展示 (File Identity Card)
        st.markdown(f"""
        <div style="background-color:rgba(128,128,128,0.05); padding:15px; border-radius:12px; border:1px solid rgba(128,128,128,0.1); margin-bottom:25px;">
            <p style="margin:0; font-size:0.9rem; opacity:0.7;">当前配置对象:</p>
            <h4 style="margin:5px 0 0 0;">📄 {selected_fname}</h4>
            <p style="margin:5px 0 0 0; font-size:0.85rem;">
                <span style="background: rgba(46, 134, 193, 0.2); padding:2px 8px; border-radius:4px;">类型: {analysis.file_type.upper()}</span>
                &nbsp;
                <span style="background: rgba(128,128,128, 0.2); padding:2px 8px; border-radius:4px;">编码: {analysis.encoding}</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 5. 分层工作流 (Layered Workflow)
        
        # --- Step 1: 结构嗅探与解析 (Parsing Rules + Raw Preview) ---
        st.markdown("""
        <div class="step-container">
            <div class="step-circle">1</div>
            <div class="step-title">数据解析与结构识别</div>
        </div>
        """, unsafe_allow_html=True)
        
        c_parse_rules, c_raw_preview = st.columns([1, 2.5])
        
        with c_parse_rules:
            st.markdown("##### ⚙️ 解析参数")
            
            # [FIX] Explicit control over header usage
            has_header_default = current_settings.get('use_header', True)
            use_hdr = st.checkbox("有表头", value=has_header_default, key=f"uh_v_{selected_fname}")
            
            hdr_val = st.number_input("表头行号", min_value=0, value=current_settings['header_row'], key=f"hr_v_{selected_fname}", disabled=not use_hdr)
            skip_val = st.number_input("跳过行数", min_value=0, value=current_settings['skip_rows'], key=f"sr_v_{selected_fname}")
            
            if analysis.file_type == 'txt':
                delims = [',', '\\t', ';', ' ', '|', 'auto']
                d_idx = 5
                if current_settings['delimiter'] == '\t': d_idx = 1
                elif current_settings['delimiter'] == ',': d_idx = 0
                d_sel = st.selectbox("分隔符", delims, index=d_idx, key=f"dl_v_{selected_fname}")
                new_delim = '\t' if d_sel == '\\t' else (None if d_sel == 'auto' else d_sel)
            else:
                st.caption("Excel 自动识别结构")
                new_delim = current_settings['delimiter']
                if analysis.sheet_names:
                    current_settings['sheet_name'] = st.selectbox("选择工作表 (Sheet)", analysis.sheet_names, 
                        index=analysis.sheet_names.index(current_settings['sheet_name']) if current_settings['sheet_name'] in analysis.sheet_names else 0)

            # Sync logic
            if use_hdr != current_settings.get('use_header', True) or hdr_val != current_settings['header_row'] or skip_val != current_settings['skip_rows'] or (analysis.file_type == 'txt' and new_delim != current_settings['delimiter']):
                current_settings['use_header'] = use_hdr
                current_settings['header_row'] = hdr_val
                current_settings['skip_rows'] = skip_val
                current_settings['delimiter'] = new_delim
                current_settings['column_aliases'] = {} # Reset columns on structure change
                st.rerun()

        with c_raw_preview:
            st.markdown("##### 🔍 原始数据参考")
            current_file.seek(0)
            df_raw_ref = loader.load(current_file, {
                'file_type': current_settings['file_type'],
                'encoding': current_settings['encoding'],
                'raw_mode': True 
            }).head(50) # Show first 50 lines
            st.dataframe(df_raw_ref, use_container_width=True, height=260)
            st.caption("💡 请对比参考上表来确认表头所在的行号。")

        st.markdown("---")

        # --- Step 2: 列管理与重命名 (Column Cleanup) ---
        st.markdown("""
        <div class="step-container">
            <div class="step-circle">2</div>
            <div class="step-title">列清洗与重命名</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Dry run for current config
        current_file.seek(0)
        try:
            df_preview = loader.load(current_file, current_settings)
        except Exception as e:
            current_settings['column_aliases'] = {}
            current_settings['transformations'] = []
            st.warning("⚠️ 结构变动已重置列配置。")
            st.rerun()

        with st.container():
            st.markdown("通过下方管理器批量配置需要保留的列。")
            
            # --- Global Controls ---
            ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([2, 1, 1])
            search_query = ctrl_c1.text_input("🔍 搜索列名", placeholder="输入关键字快速过滤...", key=f"col_search_{selected_fname}")
            
            # Filter columns based on search
            filtered_cols = [c for c in available_cols if search_query.lower() in c.lower()] if search_query else available_cols
            
            if ctrl_c2.button("✅ 全选 (保留)", use_container_width=True, key=f"sel_all_{selected_fname}"):
                for c in filtered_cols: st.session_state[f"k_v_{selected_fname}_{c}"] = True
                st.rerun()
            if ctrl_c3.button("❌ 全不选 (剔除)", use_container_width=True, key=f"sel_none_{selected_fname}"):
                for c in filtered_cols: st.session_state[f"k_v_{selected_fname}_{c}"] = False
                st.rerun()

            # --- Column List (Scrollable Area) ---
            st.markdown(f"显示: {len(filtered_cols)} / 总计: {len(available_cols)} 列")
            
            # Table-like Header
            h_c1, h_c2, h_c3, h_c4 = st.columns([0.5, 2, 2, 3])
            h_c1.caption("保留")
            h_c2.caption("原始列名")
            h_c3.caption("设置别名")
            h_c4.caption("数据预览 (Top 3)")

            new_aliases = {}
            existing_aliases = current_settings.get('column_aliases', {})
            
            # Scrollable Container with Max Height
            with st.container(height=400, border=True):
                for c_orig in filtered_cols:
                    r_c1, r_c2, r_c3, r_c4 = st.columns([0.5, 2, 2, 3])
                    
                    is_kept = r_c1.checkbox(" ", value=(c_orig in existing_aliases), label_visibility="collapsed", key=f"k_v_{selected_fname}_{c_orig}")
                    r_c2.markdown(f"`{c_orig}`")
                    
                    sample_vals = df_raw_clean[c_orig].head(3).tolist()
                    sample_str = ", ".join([str(v) for v in sample_vals])
                    
                    if is_kept:
                        alias = r_c3.text_input(
                            "Alias", label_visibility="collapsed",
                            value=existing_aliases.get(c_orig, c_orig), 
                            key=f"a_v_{selected_fname}_{c_orig}",
                            placeholder="不填则保持原名"
                        )
                        new_aliases[c_orig] = alias or c_orig
                        r_c4.caption(f"`{sample_str}...`")
                    else:
                        r_c3.markdown("<span style='opacity:0.3;'>已剔除</span>", unsafe_allow_html=True)
                        r_c4.markdown(f"<span style='opacity:0.3; font-size:0.8rem;'>{sample_str}...</span>", unsafe_allow_html=True)

            # Sync aliases to settings (handle unshown columns too)
            # Only update aliases for columns currently handled (newly set or previously set)
            # This logic needs to be careful not to drop aliases of columns NOT in filtered list if they were already set
            final_aliases = existing_aliases.copy()
            # Update from current interaction
            for c in filtered_cols:
                is_checked = st.session_state.get(f"k_v_{selected_fname}_{c}", False)
                if is_checked:
                    final_aliases[c] = st.session_state.get(f"a_v_{selected_fname}_{c}", c)
                else:
                    if c in final_aliases: del final_aliases[c]

            if final_aliases != existing_aliases:
                current_settings['column_aliases'] = final_aliases
                st.rerun()

        st.markdown("---")

        # --- Step 3: 高级处理与最终加载 (Advanced & Action) ---
        st.markdown("""
        <div class="step-container">
            <div class="step-circle">3</div>
            <div class="step-title">高级处理与入库</div>
        </div>
        """, unsafe_allow_html=True)

            
        with st.expander("展开/折叠 数学处理", expanded=False):
            managed_cols = list(current_settings['column_aliases'].values())
            rules = current_settings.get('transformations', [])
            if not managed_cols:
                st.warning("在此之前，请先在 Step 2 中勾选需要保留的列。")
            else:
                for idx, rule in enumerate(rules):
                    r_c1, r_c2, r_c3, r_c4, r_c5 = st.columns([3, 1.5, 2.5, 2, 1])
                    rule['column'] = r_c1.selectbox(f"目标", managed_cols, index=managed_cols.index(rule['column']) if rule['column'] in managed_cols else 0, key=f"r_col_{selected_fname}_{idx}")
                    rule['op'] = r_c2.selectbox(f"算", ["+", "-", "*", "/"], index=["+", "-", "*", "/"].index(rule['op']), key=f"r_op_{selected_fname}_{idx}")
                    
                    # 选择取值方式
                    source_options = ["手动输入", "首行数值", "此列最大值", "此列最小值"]
                    source_map = {"手动输入": "fixed", "首行数值": "__COL_FIRST__", "此列最大值": "__COL_MAX__", "此列最小值": "__COL_MIN__"}
                    inv_source_map = {v: k for k, v in source_map.items()}
                    
                    # 确定当前源
                    current_val = rule.get('val', 0.0)
                    current_source_key = current_val if isinstance(current_val, str) and current_val in inv_source_map else "fixed"
                    current_source_name = inv_source_map.get(current_source_key, "手动输入")
                    
                    selected_source = r_c3.selectbox("数值来源", source_options, index=source_options.index(current_source_name), key=f"r_src_{selected_fname}_{idx}")
                    
                    if selected_source == "手动输入":
                        # 如果之前是动态的，切换回来时默认给 1.0
                        init_num = float(current_val) if not isinstance(current_val, str) else 1.0
                        rule['val'] = r_c4.number_input("数值", value=init_num, key=f"r_v_{selected_fname}_{idx}")
                    else:
                        rule['val'] = source_map[selected_source]
                        r_c4.text_input("动态值", value=selected_source, disabled=True, key=f"r_v_dis_{selected_fname}_{idx}")
                        
                    if r_c5.button("🗑️", key=f"r_del_{selected_fname}_{idx}"):
                        rules.pop(idx)
                        st.rerun()
                if st.button("➕ 添加计算规则", use_container_width=True, key=f"add_rule_{selected_fname}"):
                    rules.append({"column": managed_cols[0], "op": "*", "val": 1.0})
                    st.rerun()
            current_settings['transformations'] = rules

        st.markdown("---")

        # --- 新版放置：批量应用策略 (Batch Utility) ---
        # 放置在所有配置完成后，确保公式也能同步
        with st.expander("📂 批量同步配置", expanded=True):
            tab_current, tab_rule = st.tabs(["⚡ 同步当前配置", "📚 应用保存的规则"])
            
            # --- Tab 1: Sync Current ---
            with tab_current:
                st.info("将**当前文件**的配置应用到所有加载的文件。")
                c_msg, c_btn = st.columns([2, 1])
                with c_msg:
                    match_by_index = st.checkbox("🧩 按列顺序同步", value=True, 
                        help="【推荐】不看原始列名，只看顺序。适合同一仪器导出的批量数据。", key="chk_match_idx_current")
                with c_btn:
                    if st.button("🚀 同步 (From Current)", use_container_width=True, key=f"apply_all_final_{selected_fname}"):
                        for fname in file_names:
                            if fname != selected_fname:
                                # 深度复制当前配置
                                tgt_settings = current_settings.copy()
                                # [FIX] Ensure use_header is explicitly present (handle missing key case)
                                tgt_settings['use_header'] = current_settings.get('use_header', True)
                                
                                # 显式复制 transformations 避免引用问题
                                tgt_settings['transformations'] = [r.copy() for r in current_settings.get('transformations', [])]
                                
                                if match_by_index:
                                    try:
                                        f_obj = file_map[fname]
                                        f_obj.seek(0)
                                        # 获取目标文件的原始列名
                                        dry_tgt = tgt_settings.copy()
                                        dry_tgt['column_aliases'] = {}; dry_tgt['transformations'] = []
                                        df_tgt_raw = loader.load(f_obj, dry_tgt)
                                        tgt_cols = list(df_tgt_raw.columns)
                                        
                                        new_tgt_aliases = {}
                                        for idx, s_col in enumerate(available_cols):
                                            if s_col in current_settings['column_aliases']:
                                                if idx < len(tgt_cols):
                                                    new_tgt_aliases[tgt_cols[idx]] = current_settings['column_aliases'][s_col]
                                        tgt_settings['column_aliases'] = new_tgt_aliases
                                    except: pass
                                
                                st.session_state['settings_repo'][fname] = tgt_settings
                        st.toast(f"✅ 全套配置（含计算公式）已同步至 {len(file_names)-1} 个文件！")

            # --- Tab 2: Apply Rule ---
            with tab_rule:
                rm_batch = RuleManager()
                rules_batch = rm_batch.list_rules()
                if not rules_batch:
                    st.warning("暂无保存的规则，请先在侧边栏保存规则。")
                else:
                    c_r_sel, c_r_btn = st.columns([2, 1])
                    with c_r_sel:
                        sel_rule_batch = st.selectbox("选择要应用的规则", rules_batch, key="batch_rule_sel")
                    with c_r_btn:
                        if st.button("🚀 应用规则 (From Rule)", use_container_width=True, key="app_rule_all"):
                            rule_obj = rm_batch.load_rule(sel_rule_batch)
                            if rule_obj:
                                rule_settings = rule_to_settings(rule_obj)
                                for fname in file_names:
                                    # Copy to avoid ref issues
                                    f_settings = rule_settings.copy()
                                    f_settings['transformations'] = [t.copy() for t in rule_settings.get('transformations', [])]
                                    # TODO: Maybe implement match_by_index for Rules too?
                                    # For now, strict name matching (since Rule has specific column names)
                                    # But Rule.columns keys are "Expected Original Names".
                                    # If user wants "Match by Index", it's complex for Rules derived from strict Schema.
                                    # We stick to Name Matching for Rules for simplicity/safety.
                                    st.session_state['settings_repo'][fname] = f_settings
                                
                                # [FIX] Aggressively clear widget keys for the CURRENT file so UI reflects change
                                keys_to_del = [k for k in st.session_state.keys() if f"_{selected_fname}" in k]
                                for k in keys_to_del: del st.session_state[k]

                                st.toast(f"✅ 规则 '{sel_rule_batch}' 已应用到 {len(file_names)} 个文件")
                                st.rerun()

        st.markdown("---")
        st.success(f"✅ 处理后预览: {len(df_preview.columns)} 列 | {df_preview.shape[0]} 行")
        st.dataframe(df_preview, use_container_width=True, height=300, hide_index=True)
        

        # 5. 聚合操作区 (Centered Action Area)
        # 使用列布局来控制宽度，避免铺满全屏
        _, center_col, _ = st.columns([1, 1.5, 1])
        
        with center_col:
            st.markdown("<div style='text-align:center; margin-bottom:15px;' id='final-import-area'>", unsafe_allow_html=True)
            st.markdown("<h5 style='opacity:0.8;'>准备就绪?</h5>", unsafe_allow_html=True)
            
            if st.button("🚀 确认配置并导入所有数据", type="primary", use_container_width=True):
                 progress_bar = st.progress(0)
                 success_count = 0
                 with st.empty():
                     for i, fname in enumerate(file_names):
                         st.write(f"正在处理 {fname}...")
                         try:
                             # 确保有配置，没有就分析
                             if fname not in st.session_state['settings_repo']:
                                 # 补漏逻辑...
                                 pass 
                             
                             settings = st.session_state['settings_repo'].get(fname)
                             if settings:
                                 f_obj = file_map[fname]
                                 f_obj.seek(0)
                                 df = DataLoader().load(f_obj, settings)
                                 st.session_state['data_repo'][fname] = df
                                 success_count += 1
                         except Exception as e:
                             st.error(f"{fname} 加载失败: {e}")
                         progress_bar.progress((i + 1) / len(file_names))
                 
                 st.success(f"成功导入 {success_count} 个文件")
                 @st.dialog("✅ 加载成功")
                 def show_success_dialog():
                     st.write(f"成功加载 {success_count} 个文件到数据仓库。")
                     st.write("您可以前往工作台进行绘图，或继续留在本页配置其他文件。")
                     col_go, col_stay = st.columns(2)
                     if col_go.button("📊 去分析数据", type="primary", use_container_width=True):
                         st.session_state["nav_radio"] = "📊 分析工作台" 
                         st.session_state["current_page"] = "📊 分析工作台"
                         st.rerun()
                     if col_stay.button("📂 留在本页", type="secondary", use_container_width=True):
                         st.rerun()
                 show_success_dialog()
            st.markdown("</div>", unsafe_allow_html=True)
