"""
Origin Worker - 子进程执行器
==============================
在独立进程中执行 Origin 操作，避免 COM 连接状态污染问题。

使用方法：
    python origin_worker.py <csv_file_path> <graph_name>
"""


import sys
import pandas as pd
import json
import os

ORIGIN_DEFAULTS = {
    "font_name": "Arial",  # 默认字体
    "axis_font": 28,       # 轴刻度字号
    "axis_line_width": 3,  # 轴线宽度 (pts)
    "data_line_width": 3,  # 数据线宽度
    "label_font": 30,      # 轴标签字号
}

def hex_to_rgb(hex_color):
    """Hex to RGB tuple"""
    try:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except:
        return (0, 0, 0)

def apply_styles(gl, config):
    """应用高级配置 (范围、颜色、对数等)"""
    def log(msg):
        try:
            print(f"[ORIGIN_STYLE] {msg}")
        except UnicodeEncodeError:
            # 防止 GBK 编码错误导致程序崩溃
            try:
                safe_msg = msg.encode('gbk', 'ignore').decode('gbk')
                print(f"[ORIGIN_STYLE] {safe_msg} (safe-encoded)")
            except:
                print(f"[ORIGIN_STYLE] <Encoding Error in Log Message>")
        sys.stdout.flush()
    
    try:
        # Import inside function to avoid heavy load if not needed
        import originpro as op
        
        log("开始应用样式配置...")
        
        # 1. 轴范围和类型
        lt_cmds = ""
        
        # X Axis
        if config.get('x_log'):
            lt_cmds += "layer.x.type = 2;"  # Log10
            log("  X轴: 对数刻度")
            
        ranges = config.get('x_range')
        if ranges and len(ranges) == 2:
            lt_cmds += f"layer.x.from = {ranges[0]}; layer.x.to = {ranges[1]};"
            log(f"  X轴范围: [{ranges[0]}, {ranges[1]}]")
        
        # X轴反转
        if config.get('invert_x'):
            lt_cmds += "layer.x.reverse = 1;"
            log("  X轴: 反转")
            
        # Y Axis
        if config.get('y_log'):
            lt_cmds += "layer.y.type = 2;"
            log("  Y轴: 对数刻度")
            
        ranges = config.get('y_range')
        if ranges and len(ranges) == 2:
            lt_cmds += f"layer.y.from = {ranges[0]}; layer.y.to = {ranges[1]};"
            log(f"  Y轴范围: [{ranges[0]}, {ranges[1]}]")
        
        # Y轴反转
        if config.get('invert_y'):
            lt_cmds += "layer.y.reverse = 1;"
            log("  Y轴: 反转")
            
        if lt_cmds:
            try:
                gl.lt_exec(lt_cmds)
                log("  轴设置已应用")
            except Exception as e:
                log(f"  轴设置失败: {e}")
            
        # 2. 曲线颜色和线宽
        colors = config.get('colors', [])
        
        if colors:
            log(f"  应用 {len(colors)} 个曲线颜色...")
            
            # 重新应用一次默认线宽和字体，确保不被覆盖
            apply_default_defaults(gl)
            
            for i, color_hex in enumerate(colors):
                plot_idx = i + 1  # 1-based index for LabTalk
                r, g, b = hex_to_rgb(color_hex)
                
                # 为每一条曲线设置颜色和线宽
                cmd = f"""
                range rPlot = !{plot_idx}; 
                set rPlot -c color({r}, {g}, {b});
                set rPlot -w {ORIGIN_DEFAULTS['data_line_width']};
                """
                try:
                    gl.lt_exec(cmd)
                    log(f"    曲线 {plot_idx}: 颜色={color_hex}, 线宽={ORIGIN_DEFAULTS['data_line_width']}")
                except Exception as e:
                    log(f"    曲线 {plot_idx} 样式设置失败: {e}")
        

        # 3. 设置轴标签和标题
        if config.get('x_label'):
            try:
                # LabTalk: label -xb "Text" (X Bottom Title)
                gl.lt_exec(f'label -xb "{config["x_label"]}";')
                log(f"  设置X轴标题: {config['x_label']}")
            except Exception as e:
                log(f"  X轴标题设置失败: {e}")

        if config.get('y_label'):
            try:
                gl.lt_exec(f'label -yl "{config["y_label"]}";')
                log(f"  设置Y轴标题: {config['y_label']}")
            except Exception as e:
                log(f"  Y轴标题设置失败: {e}")
                
        if config.get('title'):
            try:
                gl.lt_exec(f'label -s "{config["title"]}";') 
                log(f"  设置图表标题: {config['title']}")
            except:
                pass

        log("样式配置完成")
                
    except Exception as e:
        log(f"样式应用错误: {str(e)}")
        import traceback
        log(traceback.format_exc())

def apply_default_defaults(gl):
    """应用全局默认字体和轴线宽"""
    # 注意：font$ 需要引号，pt 不需要
    lt_cmds = f"""
    layer.x.label.font$ = "{ORIGIN_DEFAULTS['font_name']}";
    layer.y.label.font$ = "{ORIGIN_DEFAULTS['font_name']}";
    layer.x.title.font$ = "{ORIGIN_DEFAULTS['font_name']}";
    layer.y.title.font$ = "{ORIGIN_DEFAULTS['font_name']}";
    layer.x.label.pt = {ORIGIN_DEFAULTS['label_font']};
    layer.y.label.pt = {ORIGIN_DEFAULTS['label_font']};
    layer.x.title.pt = {ORIGIN_DEFAULTS['axis_font']};
    layer.y.title.pt = {ORIGIN_DEFAULTS['axis_font']};
    """
    try:
        gl.lt_exec(lt_cmds)
        # 单独设置线宽，避免长脚本执行失败
        gl.lt_exec(f"layer.x.line.width = {ORIGIN_DEFAULTS['axis_line_width']};")
        gl.lt_exec(f"layer.y.line.width = {ORIGIN_DEFAULTS['axis_line_width']};")
    except Exception as e:
        print(f"[ORIGIN] Defaults Error: {e}", file=sys.stderr)


def send_to_origin(csv_path: str, graph_name: str, config_path: str = None) -> str:
    """在干净的进程中发送数据到 Origin"""
    
    def log(msg):
        """调试日志 - 输出到 stderr"""
        try:
            print(f"[ORIGIN] {msg}", file=sys.stderr)
        except:
            pass
        sys.stderr.flush()
    
    try:
        import originpro as op
    except ImportError:
        return "ERROR:OriginPro 库未安装"
    
    # 加载配置
    config = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            log(f"已加载样式配置: {list(config.keys())}")
        except Exception as e:
            log(f"配置加载失败: {e}")
    
    try:
        # 读取数据
        df = pd.read_csv(csv_path)
        log(f"读取数据: {df.shape[0]} 行 x {df.shape[1]} 列")
        
        # 显示 Origin
        try:
            op.set_show(True)
        except:
            pass
        
        # 创建工作簿
        wb_name = graph_name + "_Data"
        wb = op.new_book('w', wb_name)
        wks = wb[0]
        
        # 传输数据
        wks.from_df(df)
        
        # 修正列属性 (XYXYXY...)
        num_cols = len(df.columns)
        for i in range(num_cols):
            try:
                # 4=X, 1=Y
                col_type_lt = 4 if i % 2 == 0 else 1
                wks.lt_exec(f"wks.col{i+1}.type = {col_type_lt};")
            except:
                pass
        
        # 创建图表
        template = config.get('template', 'LINE')
        graph = None
        
        if template == 'WATERFALL':
            log("检测到瀑布图请求，使用默认图表后续应用样式")
            graph = op.new_graph()
        else:
            log(f"尝试加载图表模板: {template}")
            try:
                # 尝试使用模板
                graph = op.new_graph(template=template)
                log(f"✅ 成功加载模板: {template}")
            except Exception as e:
                log(f"⚠️ 模板加载失败 ({template}), 尝试使用默认设置回退: {str(e)}")
                try:
                    # 彻底回退到默认
                    graph = op.new_graph()
                    log("✅ 已回退到默认图表")
                except Exception as e2:
                    log(f"❌ 严重错误: 无法创建图表 (即使在回退模式下): {str(e2)}")
                    return f"ERROR:无法创建 Origin 图表: {str(e2)}"
        
        if not graph:
            return "ERROR:无法创建 Origin 图表 (原因未知)"
            
        gl = graph[0]
        
        # 添加曲线
        plot_count = 0
        for i in range(0, num_cols, 2):
            if i+1 < num_cols:
                try:
                    gl.add_plot(wks, i+1, i, type=200) # type 200 = Line
                    plot_count += 1
                except:
                    pass
        
        if plot_count == 0:
            return "ERROR:未能添加任何曲线"

        # 命名
        try:
            graph.name = graph_name
        except:
            pass

        # === 核心样式应用 ===
        
        # 1. 如果是瀑布图，先执行分组逻辑
        #    必须在设置颜色之前分组，否则分组会重置颜色为系统默认
        if config.get('template') == 'WATERFALL':
            log("应用瀑布图分组策略...")
            try:
                # 强制分组
                gl.lt_exec("layer -g 1;")
                
                # 设置堆叠属性
                cmd_waterfall = """
                layer -s 1; 
                set %C -gm 2;
                set %C -go 20;
                layer -a; 
                """
                gl.lt_exec(cmd_waterfall)
                log("  已启用瀑布模式 (Stack Y Offset)")
            except Exception as e:
                log(f"  瀑布图分组失败: {e}")

        # 2. 应用详细样式 (颜色、线宽、轴范围)
        apply_styles(gl, config)
        
        # 3. 最后应用默认字体 (确保不被覆盖)
        apply_default_defaults(gl)
        
        # 再次强制刷新
        try:
            gl.rescale()
        except:
            pass
            
        log("✅ 导出完成！")
        return "SUCCESS:成功发送至 Origin 并已绑图！"
        
    except Exception as e:
        import traceback
        log(f"❌ 致命错误: {e}\n{traceback.format_exc()}")
        return f"ERROR:{str(e)}"



def send_to_origin_worker_cli():
    """CLI Entry point for --origin-worker mode"""
    if len(sys.argv) < 4: # [script, --origin-worker, csv_path, graph_name]
        print("ERROR:参数不足 (Worker Mode)")
        sys.exit(1)
    
    # argv[0] = exe/script
    # argv[1] = --origin-worker
    csv_path = sys.argv[2]
    graph_name = sys.argv[3]
    config_path = sys.argv[4] if len(sys.argv) > 4 else None

    print(send_to_origin(csv_path, graph_name, config_path))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("ERROR:参数不足")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    graph_name = sys.argv[2]
    config_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    # 结果打印到标准输出
    print(send_to_origin(csv_path, graph_name, config_path))
