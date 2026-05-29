import streamlit as st
import pandas as pd
import numpy as np
import datetime
import base64
from modules import DataTools, ChartBuilder, get_numeric_columns, OriginBridge
from modules.project_manager import ProjectManager

def render_workspace(container):
    """
    Renders the Analysis Workspace (List Mode).
    """
    # ---------------------------------------------------------
    # 0. HOISTED STATE & CALLBACKS
    # ---------------------------------------------------------
    
    # Pre-fetch data info for UI
    all_samples = list(st.session_state.get('data_repo', {}).keys())
    
    # 1. Direct Render
    render_list_mode(container, all_samples)


def render_list_mode(container, all_samples):
    """
    Original UI Logic.
    """

    # 1. ACTUAL RENDERING (UI Structure)
    # --- Pre-calculate Common Columns & Anchors ---
    if not all_samples:
        with container:
             st.info("💡 请先在「数据加载」页面导入数据。")
        return

    # [New Feature] Auto-Select All on Data Change
    # If the inventory of samples (keys) changes, we default to selecting ALL.
    # This solves the issue where entering the page shows an empty chart.
    curr_keys = set(all_samples)
    last_keys = set(st.session_state.get('wb_known_keys', []))
    
    if curr_keys != last_keys:
        st.session_state['p_sel_samples'] = list(all_samples)
        # Force widget update by clearing the specific widget key if it exists, 
        # or setting the shadow key which will be picked up below.
        # Ideally, we set the widget key if possible, or let the shadow recovery do it.
        # But shadow recovery only works if "selected_samples_wb" is NOT in state.
        # So we update the widget key directly if it exists.
        st.session_state['selected_samples_wb'] = list(all_samples)
        
        st.session_state['wb_known_keys'] = list(all_samples)
        st.rerun()

    # ── Shadow State Recovery ──
    # Restore widget-bound keys from persistent shadow keys.
    # This runs every time the page renders, covering the case where
    # Streamlit purged the widget keys during a tab switch.
    p_sel = st.session_state.get("p_sel_samples", [])
    if p_sel:
        # Only restore if the widget key was purged (i.e. not currently set)
        if "selected_samples_wb" not in st.session_state:
            st.session_state["selected_samples_wb"] = [s for s in p_sel if s in all_samples]
    
    if st.session_state.get("p_x_wb") is not None and "x_wb" not in st.session_state:
        st.session_state["x_wb"] = st.session_state["p_x_wb"]
    if st.session_state.get("p_y_wb") is not None and "y_wb" not in st.session_state:
        st.session_state["y_wb"] = st.session_state["p_y_wb"]
    if "plot_mode_wb" not in st.session_state:
        st.session_state["plot_mode_wb"] = st.session_state.get("p_plot_mode", "叠加")
    if "display_option_wb" not in st.session_state:
        st.session_state["display_option_wb"] = st.session_state.get("p_display_opt", "折线")
    if "waterfall_offset_pct_wb" not in st.session_state:
        st.session_state["waterfall_offset_pct_wb"] = st.session_state.get("p_waterfall_offset", 10)

    selected_samples = st.session_state.get("selected_samples_wb", [])
    common_cols = []
    if selected_samples:
        common_cols_set = set()
        for sname in selected_samples:
            if sname in st.session_state['data_repo']:
                cols = set(get_numeric_columns(st.session_state['data_repo'][sname]))
                if not common_cols_set: common_cols_set = cols
                else: common_cols_set = common_cols_set.intersection(cols)
        common_cols = sorted(list(common_cols_set))

    # [FIX] Issue 45: Support single column data plotting by introducing a virtual <自动编号> index
    x_options = ["<自动编号>"] + common_cols

    # Determine stable AXES even if common_cols is empty for the moment (fallback to first sample's cols)
    if not common_cols and all_samples:
        # Just to have a main_key for settings even if nothing is selected or common
        first_df = st.session_state['data_repo'][all_samples[0]]
        all_nums = get_numeric_columns(first_df)
        if all_nums:
            curr_x = st.session_state.get("x_wb", "<自动编号>" if len(all_nums) == 1 else all_nums[0])
            curr_y = st.session_state.get("y_wb", all_nums[min(1, len(all_nums)-1)])
        else:
            curr_x, curr_y = "X", "Y"
    else:
        # Standard logic
        if st.session_state.get("x_wb") not in x_options:
             st.session_state["x_wb"] = "<自动编号>" if len(common_cols) == 1 else common_cols[0]
        if st.session_state.get("y_wb") not in common_cols and common_cols: 
             st.session_state["y_wb"] = common_cols[0] if len(common_cols) == 1 else common_cols[min(1, len(common_cols)-1)]
        curr_x = st.session_state.get("x_wb", "X")
        curr_y = st.session_state.get("y_wb", "Y")

    sel_x = curr_x
    sel_y = curr_y
    
    # [FIX] Stable Key: Tied to AXES, not to a specific file, so settings are "sticky" to the data context
    main_key = f"style_{sel_x}_{sel_y}"
    
    if 'chart_styles' not in st.session_state: st.session_state['chart_styles'] = {}
    if main_key not in st.session_state['chart_styles']:
        st.session_state['chart_styles'][main_key] = {
            'x_label': sel_x, 'y_label': sel_y, 'title': f"{sel_y} vs {sel_x}",
            'x_range': None, 'y_range': None, 'line_color': None, 'line_style': 'solid',
            'show_legend': True, 'invert_x': False, 'invert_y': False, 'x_log': False, 'y_log': False,
            'legend_aliases': {} # {filename: alias}
        }
    style = st.session_state['chart_styles'][main_key]
    style.setdefault('legend_aliases', {}) # [FIX] Ensure field exists even in legacy states


    # --- CALLBACKS for atomic state updates ---
    def sync_style():
        """Helper to sync widget states back to the style dict"""
        style.update({
            'x_label': st.session_state.get(f"in_xl_{main_key}", style['x_label']),
            'y_label': st.session_state.get(f"in_yl_{main_key}", style['y_label']),
            'title': st.session_state.get(f"in_tt_{main_key}", style['title']),
        })

    def on_apply_template(m_key, cfg):
        st.session_state['chart_styles'][m_key].update({
            'x_label': cfg['lx'], 'y_label': cfg['ly'], 'title': cfg['lt']
        })
        # Also update the widget input buffer if it exists
        st.session_state[f"in_xl_{m_key}"] = cfg['lx']
        st.session_state[f"in_yl_{m_key}"] = cfg['ly']
        st.session_state[f"in_tt_{m_key}"] = cfg['lt']

    def on_apply_math(name, func, target_list, sel_x, sel_y, style):
        for s_name in target_list:
            s_key = f"{s_name}_{sel_x}_{sel_y}"
            if s_key not in st.session_state.get('processed_data', {}):
                df_orig = st.session_state['data_repo'][s_name]
                if sel_x == "<自动编号>":
                    if sel_y not in df_orig.columns: continue
                    ys = df_orig[sel_y].values.copy()
                    xs = np.arange(1, len(ys) + 1).astype(float)
                else:
                    xs = df_orig[sel_x].values.copy()
                    ys = df_orig[sel_y].values.copy()
                st.session_state.setdefault('processed_data', {})[s_key] = {
                    'x': xs, 'y': ys, 'operations': []
                }
            entry = st.session_state['processed_data'][s_key]
            if name == "裁剪":
                if style.get('x_range'):
                    nx, ny = DataTools.crop_range(entry['x'], entry['y'], style['x_range'][0], style['x_range'][1])
                    st.session_state['processed_data'][s_key].update({'x': nx, 'y': ny})
                else: 
                    pass
            else:
                st.session_state['processed_data'][s_key]['y'] = func(entry['x'], entry['y'])
            st.session_state['processed_data'][s_key]['operations'].append(name)

    def on_reset_data(target_list, sel_x, sel_y):
        for s_name in target_list:
            s_key = f"{s_name}_{sel_x}_{sel_y}"
            if s_key in st.session_state.get('processed_data', {}):
                del st.session_state['processed_data'][s_key]

    def on_toggle_style(main_key, field):
        st.session_state['chart_styles'][main_key][field] = not st.session_state['chart_styles'][main_key].get(field, False)

    def on_cycle_color(main_key):
        pal = ChartBuilder.COLORS
        style = st.session_state['chart_styles'][main_key]
        curr = style.get('line_color') or pal[0]
        nxt = pal[(pal.index(curr)+1)%len(pal)] if curr in pal else pal[1] # Cycle to next
        st.session_state['chart_styles'][main_key]['line_color'] = nxt
        
    def on_clear_all():
        st.session_state.pop('processed_data', None)
        st.session_state.pop('chart_styles', None)

    # ── Shadow State Sync Callbacks ──
    def _sync_shadow():
        """Write current widget values back to persistent shadow keys."""
        if "selected_samples_wb" in st.session_state:
            st.session_state["p_sel_samples"] = list(st.session_state["selected_samples_wb"])
        if "x_wb" in st.session_state:
            st.session_state["p_x_wb"] = st.session_state["x_wb"]
        if "y_wb" in st.session_state:
            st.session_state["p_y_wb"] = st.session_state["y_wb"]
        if "plot_mode_wb" in st.session_state:
            st.session_state["p_plot_mode"] = st.session_state["plot_mode_wb"]
        if "display_option_wb" in st.session_state:
            st.session_state["p_display_opt"] = st.session_state["display_option_wb"]
        if "waterfall_offset_pct_wb" in st.session_state:
            st.session_state["p_waterfall_offset"] = st.session_state["waterfall_offset_pct_wb"]

    with container:
        st.markdown('<div id="top-anchor"></div>', unsafe_allow_html=True)
        
        col_side, col_chart = st.columns([1, 4])
        
        # --- 工具仓 (Left Sidebar Restructured) ---
        with col_side:
            st.markdown("#### 🛠️ 工具仓")
            
            # (1) 数据选择 - DEFAULT EXPANDED
            with st.expander("📊 数据选择", expanded=True):
                # 1.1 Bulk Actions
                c_bulk1, c_bulk2 = st.columns(2)
                if c_bulk1.button("✅ 全选", use_container_width=True, key="wb_sel_all"):
                    st.session_state["selected_samples_wb"] = all_samples
                    st.session_state["p_sel_samples"] = list(all_samples)
                    st.rerun()
                if c_bulk2.button("❌ 清空", use_container_width=True, key="wb_sel_none"):
                    st.session_state["selected_samples_wb"] = []
                    st.session_state["p_sel_samples"] = []
                    st.rerun()


                
                # 1.3 Selector
                def _fmt_alias(name):
                    return st.session_state.get('p_global_aliases', {}).get(name, name)

                st.multiselect("样品列表", all_samples, key="selected_samples_wb", on_change=_sync_shadow, format_func=_fmt_alias)
                
                # 1.4 Axes
                st.selectbox("X 轴数据", x_options, index=x_options.index(sel_x) if sel_x in x_options else 0, key="x_wb", on_change=_sync_shadow)
                st.selectbox("Y 轴数据", common_cols, index=common_cols.index(sel_y) if sel_y in common_cols else 1 if len(common_cols)>1 else 0, key="y_wb", on_change=_sync_shadow)
                st.markdown("---")
                st.radio("绘图切换", ["叠加", "瀑布"], horizontal=True, key="plot_mode_wb", on_change=_sync_shadow)
                if st.session_state.get('plot_mode_wb') == "瀑布":
                    st.slider("瀑布间距 (%)", 0, 200, value=10, step=5, format="%d%%", key="waterfall_offset_pct_wb", on_change=_sync_shadow)
                st.radio("曲线样式", ["折线", "散点", "折线+散点"], horizontal=True, key="display_option_wb", on_change=_sync_shadow)

            # (2) 快速模板
            with st.expander("📋 快速模板", expanded=False):
                TEMPLATES = {
                    "XRD 衍射": {"lx": "2θ (°)", "ly": "Intensity (a.u.)", "lt": "XRD Pattern"},
                    "FTIR 红外": {"lx": "Wavenumber (cm⁻¹)", "ly": "Transmittance (%)", "lt": "FTIR Spectra"},
                    "Raman 拉曼": {"lx": "Raman Shift (cm⁻¹)", "ly": "Intensity (a.u.)", "lt": "Raman Spectra"},
                    "UV-Vis 紫外": {"lx": "Wavelength (nm)", "ly": "Absorbance (a.u.)", "lt": "Absorption Study"},
                    "TG 热重": {"lx": "Temperature (°C)", "ly": "Weight (%)", "lt": "TGA Profile"},
                    "DSC 差示扫描": {"lx": "Temperature (°C)", "ly": "Heat Flow (mW/mg)", "lt": "DSC Profile"},
                    "应力应变": {"lx": "Strain (%)", "ly": "Stress (MPa)", "lt": "Tensile Curve"},
                    "电化学 CV": {"lx": "Potential (V)", "ly": "Current (A)", "lt": "CV Curve"},
                    "EIS 阻抗谱": {"lx": "Z' (Ohm)", "ly": "Z'' (Ohm)", "lt": "Nyquist Plot"}
                }
                for i, (name, cfg) in enumerate(TEMPLATES.items()):
                    st.button(name, use_container_width=True, key=f"v53_tmpl_{i}", on_click=on_apply_template, args=(main_key, cfg))

            # (3) 曲线变换
            with st.expander("🧪 曲线变换", expanded=False):
                st.checkbox("🔗 同步处理", value=False, key="sync_proc_v53")
                
                # Guard against empty selection
                if not st.session_state.get('selected_samples_wb'):
                    st.info("💡 请先选择样品再进行处理。")
                    t_list = []
                else:
                    t_list = st.session_state['selected_samples_wb'] if st.session_state.get("sync_proc_v53") else [st.session_state['selected_samples_wb'][0]]
                
                if t_list:
                    p_c1, p_c2 = st.columns(2)
                    p_c1.button("🌊 平滑", use_container_width=True, on_click=on_apply_math, args=("平滑", lambda x, y: DataTools.smooth(y), t_list, sel_x, sel_y, style))
                    p_c2.button("📏 归一", use_container_width=True, on_click=on_apply_math, args=("归一化", lambda x, y: DataTools.normalize(y), t_list, sel_x, sel_y, style))
                    p_c1.button("🧹 去底", use_container_width=True, on_click=on_apply_math, args=("去基线", lambda x, y: DataTools.baseline_correct(x, y), t_list, sel_x, sel_y, style))
                    p_c2.button("📈 求导", use_container_width=True, on_click=on_apply_math, args=("求导", lambda x, y: DataTools.derivative(x, y), t_list, sel_x, sel_y, style))
                    st.button("✂️ 按视图裁剪点", use_container_width=True, on_click=on_apply_math, args=("裁剪", None, t_list, sel_x, sel_y, style))
                    st.button("🔄 重置当前数据", use_container_width=True, type="secondary", on_click=on_reset_data, args=(t_list, sel_x, sel_y))

            # (4) 导出
            with st.expander("🚀 导出发送", expanded=False):
                # [Sprint 6] Template Selection
                bridge = OriginBridge()
                avail_templates = bridge.get_available_templates()
                options = ["默认"] + avail_templates
                selected_tmpl = st.selectbox("Origin 模板", options, index=0)

                if st.button("🚀 发送至 OriginPro", use_container_width=True, type="primary"):
                    if not selected_samples:
                        st.error("❌ 请先选择至少一个样品。")
                    else:
                        # Resolve Template logic
                        final_tmpl = "LINE"
                        if selected_tmpl == "默认": final_tmpl = "LINE"
                        else:
                             path = bridge.get_template_path(selected_tmpl)
                             if path: final_tmpl = path

                        export_data = {}
                        for name in selected_samples:
                            s_key = f"{name}_{sel_x}_{sel_y}"
                            if s_key in st.session_state.get('processed_data', {}):
                                xs, ys = st.session_state['processed_data'][s_key]['x'], st.session_state['processed_data'][s_key]['y']
                            else:
                                df_tmp = st.session_state['data_repo'][name]
                                if sel_x == "<自动编号>":
                                    if sel_y not in df_tmp.columns: continue
                                    ys = df_tmp[sel_y].values
                                    xs = np.arange(1, len(ys) + 1)
                                else:
                                    xs, ys = df_tmp[sel_x].values, df_tmp[sel_y].values
                            
                            # [Naming Inheritance: Local -> Global -> Raw]
                            g_aliases = st.session_state.get("p_global_aliases", {})
                            alias = style['legend_aliases'].get(name) or g_aliases.get(name, name)
                            export_data[f"{alias}_X"] = pd.Series(xs); export_data[f"{alias}_Y"] = pd.Series(ys)
                        
                        df_exp = pd.DataFrame(export_data)
                        # Build colors list matching ChartBuilder's palette assignment
                        _palette = ChartBuilder.COLORS
                        if len(selected_samples) == 1 and style.get('line_color'):
                            _colors = [style['line_color']]
                        else:
                            _colors = [_palette[i % len(_palette)] for i in range(len(selected_samples))]
                        style_cfg = {
                            "x_range": style.get("x_range"), "y_range": style.get("y_range"),
                            "x_log": style.get("x_log", False), "y_log": style.get("y_log", False),
                            "invert_x": style.get("invert_x", False), "invert_y": style.get("invert_y", False),
                            "x_label": style['x_label'], "y_label": style['y_label'], "title": style['title'],
                            "colors": _colors,
                            "template": final_tmpl
                        }
                        msg = bridge.send_to_origin_direct(df_exp, f"Plot_{selected_samples[0]}", style_cfg)
                        if "SUCCESS" in msg: st.success("✅ 发送成功")
                        else: st.warning(msg)


        # --- 图表区 (Right) ---
        with col_chart:
            curves = []
            y_range_val = 1.0 # Default fallback
            
            if not selected_samples:
                st.info("💡 请在左侧勾选需要分析的样品。")
            elif not common_cols:
                st.warning("⚠️ 选中的样品没有共同的数值列（无法同 X/Y 轴绘图）。")
            else:
                for name in selected_samples:
                    df = st.session_state['data_repo'][name]
                    s_key = f"{name}_{sel_x}_{sel_y}"
                    if s_key in st.session_state.get('processed_data', {}):
                        xv, yv = st.session_state['processed_data'][s_key]['x'], st.session_state['processed_data'][s_key]['y']
                    else: 
                        if sel_x == "<自动编号>":
                            if sel_y not in df.columns: continue
                            yv = df[sel_y].values
                            xv = np.arange(1, len(yv) + 1)
                        else:
                            if sel_x not in df.columns or sel_y not in df.columns: continue 
                            xv, yv = df[sel_x].values, df[sel_y].values
                    
                    # [Naming Inheritance: Local -> Global -> Raw]
                    g_aliases = st.session_state.get("p_global_aliases", {})
                    display_name = style['legend_aliases'].get(name) or g_aliases.get(name, name)
                    curves.append({'name': display_name, 'x': xv, 'y': yv})
                
                # [FIX] Dynamic Waterfall Offset
                y_range_val = 1.0 
                try:
                    y_max = max([np.max(c['y']) for c in curves])
                    y_min = min([np.min(c['y']) for c in curves])
                    if y_max != y_min: y_range_val = y_max - y_min
                except: pass
            
            offset_pct = st.session_state.get('waterfall_offset_pct_wb', 10)
            real_offset = y_range_val * (offset_pct / 100.0)

            chart = ChartBuilder()
            p_mode = st.session_state.get('plot_mode_wb', "叠加")
            fig, config = chart.plot_multi_curves(
                curves=curves, x_label=style['x_label'], y_label=style['y_label'],
                title=style['title'], mode="waterfall" if "瀑布" in p_mode else "overlay", 
                offset=real_offset, 
                display_mode={"折线": "lines", "散点": "markers", "折线+散点": "lines+markers"}.get(st.session_state.get('display_option_wb', "折线"), "lines")
            )
            
            # Apply Style
            if style.get('x_range'): fig.update_xaxes(range=style['x_range'])
            if style.get('y_range'): fig.update_yaxes(range=style['y_range'])
            if style.get('invert_x'): fig.update_xaxes(autorange='reversed')
            if style.get('invert_y'): fig.update_yaxes(autorange='reversed')
            if style.get('x_log'): fig.update_xaxes(type='log')
            if style.get('y_log'): fig.update_yaxes(type='log')
            fig.update_layout(showlegend=style.get('show_legend', True))
            
            # [FIX] Apply Palette Shift if line_color is set (Works for one or many curves)
            if style.get('line_color'):
                pal = ChartBuilder.COLORS
                c_offset = pal.index(style['line_color']) if style['line_color'] in pal else 0
                for i, trace in enumerate(fig.data):
                    new_color = pal[(i + c_offset) % len(pal)]
                    trace.line.color = new_color
                    if hasattr(trace, 'marker') and trace.marker and trace.marker.color:
                        trace.marker.color = new_color

            st.plotly_chart(fig, use_container_width=True, config=config)

        # --- 底部基础格式配置 (Formatting Hub Restructured) ---
        st.markdown("---")
        st.markdown("#### 🔘 基础格式配置")
        
        db_c1, db_c2, db_c3, db_c4 = st.columns([1.5, 1.2, 1, 1])
        
        with db_c1:
            st.caption("🏷️ **文本设定**")
            # [FIX] Bind keys directly to session state with on_change for auto-save
            st.text_input("X 轴标题", value=style['x_label'], label_visibility="collapsed", key=f"in_xl_{main_key}", on_change=sync_style)
            st.text_input("Y 轴标题", value=style['y_label'], label_visibility="collapsed", key=f"in_yl_{main_key}", on_change=sync_style)
            st.text_input("主标题", value=style['title'], label_visibility="collapsed", key=f"in_tt_{main_key}", on_change=sync_style)
            if st.button("🖊️ 强制刷新", use_container_width=True, help="如果自动保存未反应，点击此按钮手动同步"):
                sync_style()
                st.rerun()

        with db_c2:
            st.caption("📐 **轴范围锁定**")
            # Need numeric data to calculate fallback ranges
            x_min_r = float(np.min(curves[0]['x'])) if curves else 0.0
            x_max_r = float(np.max(curves[0]['x'])) if curves else 1.0
            y_min_r = float(np.min(curves[0]['y'])) if curves else 0.0
            y_max_r = float(np.max(curves[0]['y'])) if curves else 1.0
            
            r_c1, r_c2 = st.columns(2)
            # [FIX] Explicit keys for range inputs to persist after view mode switch
            x_min_i = r_c1.number_input("X Min", value=style['x_range'][0] if style['x_range'] else x_min_r, format="%.4f", label_visibility="collapsed", key=f"ir_xmin_{main_key}")
            y_min_i = r_c1.number_input("Y Min", value=style['y_range'][0] if style['y_range'] else y_min_r, format="%.4f", label_visibility="collapsed", key=f"ir_ymin_{main_key}")
            x_max_i = r_c2.number_input("X Max", value=style['x_range'][1] if style['x_range'] else x_max_r, format="%.4f", label_visibility="collapsed", key=f"ir_xmax_{main_key}")
            y_max_i = r_c2.number_input("Y Max", value=style['y_range'][1] if style['y_range'] else y_max_r, format="%.4f", label_visibility="collapsed", key=f"ir_ymax_{main_key}")
            
            b_c1, b_c2 = st.columns(2)
            if b_c1.button("📌 锁定", use_container_width=True):
                st.session_state['chart_styles'][main_key]['x_range'] = [x_min_i, x_max_i]
                st.session_state['chart_styles'][main_key]['y_range'] = [y_min_i, y_max_i]; st.rerun()
            if b_c2.button("🔓 自动", use_container_width=True):
                st.session_state['chart_styles'][main_key]['x_range'] = None
                st.session_state['chart_styles'][main_key]['y_range'] = None; st.rerun()

        with db_c3:
            st.caption("🔄 **轴向与变换**")
            f1, f2 = st.columns(2)
            f1.button("↔️ 反转 X", use_container_width=True, on_click=on_toggle_style, args=(main_key, 'invert_x'))
            f2.button("↕️ 反转 Y", use_container_width=True, on_click=on_toggle_style, args=(main_key, 'invert_y'))
            f1.button("📊 对数 X", use_container_width=True, on_click=on_toggle_style, args=(main_key, 'x_log'))
            f2.button("📊 对数 Y", use_container_width=True, on_click=on_toggle_style, args=(main_key, 'y_log'))

        with db_c4:
            st.caption("🎨 **视觉修饰**")
            v_c1, v_c2 = st.columns(2)
            v_c1.button("🌈 调色", use_container_width=True, on_click=on_cycle_color, args=(main_key,))
            v_c2.button("📝 图例", use_container_width=True, on_click=on_toggle_style, args=(main_key, 'show_legend'))
            
            with st.expander("📝 局部重命名"):
                st.caption("以下修改仅对当前坐标轴视图生效：")
                g_aliases = st.session_state.get("p_global_aliases", {})
                for sname in selected_samples:
                    # Logic: If local exists, show it. Otherwise show global as base.
                    placeholder_name = g_aliases.get(sname, sname)
                    curr_local = style['legend_aliases'].get(sname, "")
                    
                    # Label shows raw name
                    st.markdown(f"<p style='font-size:0.75rem; margin-bottom:0; opacity:0.5;'>源文件: {sname}</p>", unsafe_allow_html=True)
                    new_val = st.text_input(
                        f"Override {sname}", 
                        value=curr_local, 
                        placeholder=f"继承自全局: {placeholder_name}",
                        key=f"leg_in_{sname}_{main_key}", 
                        label_visibility="collapsed"
                    )
                    if new_val != curr_local:
                        style['legend_aliases'][sname] = new_val
                        st.rerun()
                
                if st.button("🔄 重置局部重命名", use_container_width=True):
                    style['legend_aliases'] = {}
                    st.rerun()

            def go_to_ai_stable():
                st.session_state["nav_radio"] = "💬 AI 智能分析"
                st.session_state["current_page"] = "💬 AI 智能分析"
            st.button("🚀 开启AI分析", use_container_width=True, type="primary", on_click=go_to_ai_stable)
            st.button("🚮 清除所有配置", use_container_width=True, type="secondary", on_click=on_clear_all)
