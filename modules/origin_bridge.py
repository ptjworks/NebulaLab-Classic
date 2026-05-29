"""
Origin 接口模块
===============
负责与 OriginPro 软件进行交互
注意: 需要安装 originpro 库并运行 Origin 软件
"""

import pandas as pd
import sys
from typing import List, Optional
import subprocess

# Origin 库导入（可选）
# 如果未安装 originpro，将使用模拟模式
try:
    import originpro as op
    ORIGIN_AVAILABLE = True
except ImportError:
    ORIGIN_AVAILABLE = False


class OriginBridge:
    """
    Origin 桥接类
    
    用于将数据传输到 OriginPro 并创建图表
    
    使用示例:
        bridge = OriginBridge()
        if bridge.is_connected():
            bridge.send_dataframe(df, "MyWorkbook")
    """
    
    def __init__(self):
        """初始化 Origin 桥接器"""
        self._connected = False
        
        if ORIGIN_AVAILABLE:
            try:
                self._connected = bool(op.oext)
            except:
                self._connected = False
    
    def is_available(self) -> bool:
        """检查 originpro 库是否可用"""
        return ORIGIN_AVAILABLE
    
    def get_available_templates(self) -> List[str]:
        """Scanning origin_templates directory for .otp/.otpu files"""
        import glob
        import os
        
        # Project Root (Assuming modules/origin_bridge.py)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tpl_dir = os.path.join(root_dir, "origin_templates")
        
        if not os.path.exists(tpl_dir):
            return []
            
        # Scan
        files = glob.glob(os.path.join(tpl_dir, "*.otp")) + glob.glob(os.path.join(tpl_dir, "*.otpu"))
        return [os.path.basename(f) for f in files]

    def get_template_path(self, template_name: str) -> Optional[str]:
        """Resolve template filename to absolute path"""
        import os
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tpl_path = os.path.join(root_dir, "origin_templates", template_name)
        if os.path.exists(tpl_path):
            return tpl_path
        return None

    def send_dataframe(self, df: pd.DataFrame, book_name: str = "ProcessedData",
                       sheet_name: str = "Data") -> bool:
        """
        将 DataFrame 发送到 Origin 工作簿
        
        参数:
            df: 要传输的 DataFrame
            book_name: 工作簿名称
            sheet_name: 工作表名称
            
        返回:
            是否成功
        """
        if not ORIGIN_AVAILABLE:
            print("⚠️ originpro 库未安装")
            return False
        
        if not self._connected:
            print("⚠️ Origin 未连接")
            return False
        
        try:
            # 创建新工作簿
            wb = op.new_book('w', book_name)
            wks = wb[0]
            wks.name = sheet_name
            
            # 设置列标签
            for i, col_name in enumerate(df.columns):
                wks.set_label(i, col_name, 'L')
            
            # 传输数据
            wks.from_df(df)
            
            print(f"✅ 成功将数据传输到 Origin 工作簿: {book_name}")
            return True
            
        except Exception as e:
            print(f"❌ 传输到 Origin 失败: {e}")
            return False
    
    def send_with_plot(self, df: pd.DataFrame, x_col: str, y_cols: List[str],
                       book_name: str = "DataWithPlot",
                       template: str = "Line") -> bool:
        """
        将数据传输到 Origin 并创建图表
        
        参数:
            df: 要传输的 DataFrame
            x_col: X 轴列名
            y_cols: Y 轴列名列表
            book_name: 工作簿名称
            template: 图表模板
            
        返回:
            是否成功
        """
        if not ORIGIN_AVAILABLE:
            print("⚠️ originpro 库未安装")
            return False
        
        if not self._connected:
            print("⚠️ Origin 未连接")
            return False
        
        try:
            # 创建工作簿并传输数据
            wb = op.new_book('w', book_name)
            wks = wb[0]
            wks.from_df(df)
            
            # 创建图表
            graph = op.new_graph(template=template)
            layer = graph[0]
            
            # 添加数据到图表
            x_col_idx = df.columns.get_loc(x_col)
            for y_col in y_cols:
                y_col_idx = df.columns.get_loc(y_col)
                layer.add_plot(wks, x_col_idx, y_col_idx)
            
            # 自动调整坐标轴范围
            layer.rescale()
            
            print(f"✅ 成功创建 Origin 图表")
            return True
            
        except Exception as e:
            print(f"❌ 创建 Origin 图表失败: {e}")
            return False
    
    def send_to_origin_direct(self, df: pd.DataFrame, graph_name: str = "AutoPlot", style_config: dict = None) -> str:
        """
        核武器功能：直接唤醒 Origin 并画图
        
        使用子进程方案：在独立 Python 进程中执行 Origin 操作
        Style Config Support: 通过临时 JSON 文件传递样式配置
        """
        import tempfile
        import os
        import json
        
        if not ORIGIN_AVAILABLE:
            return "❌ OriginPro 库未安装，无法执行直接操作。"
        
        # 获取 worker 脚本路径
        worker_script = os.path.join(os.path.dirname(__file__), "origin_worker.py")
        
        if not os.path.exists(worker_script):
            # 如果 worker 脚本不存在，回退到直接调用 (注意: fallback 暂不支持高级样式)
            return self._send_to_origin_fallback(df, graph_name)
        
        temp_csv = None
        temp_config = None
        
        try:
            # 1. 将 DataFrame 保存为临时 CSV 文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
                temp_csv = f.name
                df.to_csv(f, index=False)
            
            # 2. 保存样式配置 (如果存在)
            config_arg = ""
            if style_config:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                    temp_config = f.name
                    json.dump(style_config, f)
                config_arg = temp_config
            
            # 3. 在子进程中执行 Origin 操作
            # [FIX] PyInstaller Support: Use sys.executable with flag if frozen, else python script
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, '--origin-worker', temp_csv, graph_name]
            else:
                cmd = [sys.executable, worker_script, temp_csv, graph_name]
                
            if config_arg:
                cmd.append(config_arg)
                
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30秒超时
                    cwd=os.path.dirname(worker_script)
                )
                
                output = result.stdout.strip()
                err_output = result.stderr.strip()
                
                if result.returncode != 0 or output.startswith("ERROR:"):
                    # Combine stdout and stderr for full picture
                    full_error = output.replace("ERROR:", "") if output else err_output
                    if not full_error: full_error = f"Return Code: {result.returncode}"
                    
                    # 如果子进程也失败了，给出明确的指示
                    if "CreatePage" in full_error or "exception" in full_error.lower():
                        return "❌ Origin 连接异常。请尝试：1) 完全关闭 Origin  2) 重启本应用  3) 再打开 Origin  4) 重试"
                    
                    return f"❌ Origin 操作失败: {full_error}"
                
                if output.startswith("SUCCESS:"):
                    return "✅ " + output.replace("SUCCESS:", "")
                
                return output if output else "✅ 操作完成"

                
            finally:
                # 清理临时文件
                try:
                    if temp_csv and os.path.exists(temp_csv):
                        os.unlink(temp_csv)
                    if temp_config and os.path.exists(temp_config):
                        os.unlink(temp_config)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return "❌ Origin 操作超时。请确保 Origin 已打开且处于空闲状态。"
        except Exception as e:
            return f"❌ 执行失败: {str(e)}"
    
    def _send_to_origin_fallback(self, df: pd.DataFrame, graph_name: str) -> str:
        """直接调用方式的回退方案"""
        try:
            # 显示 Origin
            try:
                op.set_show(True)
            except:
                pass
            
            # 创建工作簿
            wb = op.new_book('w', graph_name + "_Data")
            wks = wb[0]
            
            # 传输数据
            df_clean = df.dropna()
            wks.from_df(df_clean)
            
            # 创建图表
            try:
                graph = op.new_graph(template="LINE")
            except:
                graph = op.new_graph()
            
            gl = graph[0]
            
            # 添加曲线
            cols = df_clean.columns
            if len(cols) >= 2:
                for i in range(1, len(cols)):
                    try:
                        gl.add_plot(wks, i, 0, type=200)
                    except:
                        try:
                            gl.add_plot(wks, i, 0)
                        except:
                            pass
            
            # 缩放
            try:
                gl.rescale()
            except:
                pass
            
            try:
                graph.name = graph_name
            except:
                pass
            
            return "✅ 成功发送至 Origin 并已绑图！"
            
        except Exception as e:
            error_msg = str(e)
            if "CreatePage" in error_msg:
                return "❌ Origin 连接异常。请完全关闭 Origin 和本应用，然后重新启动两者。"
            return f"❌ Origin 操作失败: {error_msg}"

    def simulate_send(self, df: pd.DataFrame, book_name: str = "ProcessedData") -> dict:
        """
        模拟发送数据（用于演示）
        
        参数:
            df: 要传输的 DataFrame
            book_name: 工作簿名称
            
        返回:
            模拟结果信息
        """
        return {
            "success": True,
            "message": f"模拟传输成功！数据将发送到 Origin 工作簿 '{book_name}'",
            "rows": len(df),
            "columns": list(df.columns),
            "code_example": f"""
import originpro as op
# 1. 唤醒 Origin
if op.oext: op.set_show(True)

# 2. 数据灌入
wks = op.new_sheet()
wks.from_df(df)

# 3. 自动绘图
graph = op.new_graph(template="LINE")
gl = graph[0]
gl.add_plot(wks, 1, 0, type=200)
gl.rescale()
"""
        }
