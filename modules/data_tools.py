
import numpy as np
import pandas as pd
from scipy import signal, integrate, optimize, interpolate
import streamlit as st
from typing import List, Dict, Any, Union

# ==================== 🛠️ 独立工具函数 (Standalone Functions) ====================

@st.cache_data
def apply_smoothing(data: np.ndarray, window_length: int = 11, polyorder: int = 3) -> np.ndarray:
    """
    对数据进行 Golay 平滑处理
    (Robust implementation from data_loader.py)
    """
    if len(data) < window_length:
        window_length = len(data) if len(data) % 2 == 1 else len(data) - 1
    if window_length < 5: return data
    if polyorder >= window_length: polyorder = window_length - 1
    return signal.savgol_filter(data, window_length, polyorder)

def get_numeric_columns(df: pd.DataFrame) -> List[str]:
    """获取 DataFrame 中的数值列名"""
    return df.select_dtypes(include=[np.number]).columns.tolist()

def get_data_summary(df: pd.DataFrame) -> str:
    """
    生成数据的 Markdown 统计摘要
    """
    summary_parts = []
    summary_parts.append(f"### 数据概览\n- **维度**: {df.shape[0]} 行 × {df.shape[1]} 列")
    summary_parts.append(f"- **列名**: {', '.join(map(str, df.columns))}")
    
    numeric_df = df.select_dtypes(include=[np.number])
    if not numeric_df.empty:
        summary_parts.append("\n### 科学特征分析")
        for col in numeric_df.columns:
            data = numeric_df[col].dropna()
            if len(data) == 0: continue
            
            # --- 基础统计 ---
            stats = data.describe()
            summary_parts.append(f"\n#### 列: {col}")
            summary_parts.append(f"- 范围: [{stats['min']:.4f}, {stats['max']:.4f}]")
            summary_parts.append(f"- 均值/中位数: {stats['mean']:.4f} / {stats['50%']:.4f}")
            
            # --- 峰值检测 (简单版) ---
            try:
                # 简单归一化以便参数通用
                y_norm = (data - data.min()) / (data.max() - data.min() + 1e-9)
                
                # 使用 scipy.signal.find_peaks
                from scipy.signal import find_peaks
                # 高度 > 0.3, 距离 > 10
                peak_idxs, _ = find_peaks(y_norm, height=0.2, distance=10)
                
                if len(peak_idxs) > 0:
                    top_peaks = data.iloc[peak_idxs].nlargest(3) # 取前3个高峰
                    peak_str = ", ".join([f"{v:.2f} (at Idx {i})" for i, v in top_peaks.items()])
                    summary_parts.append(f"- **主要峰值**: {peak_str}")
                else:
                    summary_parts.append("- 峰值: 未检测到显著峰")
            except:
                pass

            # --- 噪音水平估算 ---
            # 假设高频分量是噪音：原始 - 平滑
            try:
                smoothed = apply_smoothing(data.values, window_length=11, polyorder=3)
                noise = data - smoothed
                noise_level = np.std(noise)
                signal_range = data.max() - data.min()
                snr_est = signal_range / (noise_level + 1e-9)
                summary_parts.append(f"- 信噪比(估算): {snr_est:.1f} (噪音水平 {noise_level:.2e})")
            except:
                pass
                
    return "\n".join(summary_parts)


# ==================== 🧰 DataTools Class (Legacy Support) ====================

class DataTools:
    """
    科学数据处理工具库 (25+ Tools)
    包含了常用的信号处理、拟合、统计分析功能。
    """
    
    # ==================== 📊 数据处理 (Data Processing) ====================
    
    @staticmethod
    @st.cache_data
    def smooth(y: np.ndarray, window_length: int = 11, polyorder: int = 3) -> np.ndarray:
        """S-G 平滑 (Wrapper utilizing st.cache_data)"""
        # 利用全局的 robust apply_smoothing
        return apply_smoothing(y, window_length, polyorder)

    @staticmethod
    @st.cache_data
    def find_peaks(y: np.ndarray, distance: int = 10, prominence: float = 0.1) -> dict:
        """峰值检测"""
        peaks, props = signal.find_peaks(y, distance=distance, prominence=prominence)
        return {"peaks": peaks, "properties": props}

    @staticmethod
    def normalize(y: np.ndarray, method: str = 'minmax') -> np.ndarray:
        """归一化"""
        if method == 'minmax':
            return (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-9)
        elif method == 'zscore':
            return (y - np.mean(y)) / (np.std(y) + 1e-9)
        return y

    @staticmethod
    def baseline_correct(x: np.ndarray, y: np.ndarray, method: str = 'linear') -> np.ndarray:
        """基线校正 (简单线性去底)"""
        # 假设首尾点为基线
        slope = (y[-1] - y[0]) / (x[-1] - x[0])
        intercept = y[0] - slope * x[0]
        baseline = slope * x + intercept
        return y - baseline

    @staticmethod
    def derivative(x: np.ndarray, y: np.ndarray, order: int = 1) -> np.ndarray:
        """求导"""
        res = y
        for _ in range(order):
            res = np.gradient(res, x)
        return res

    @staticmethod
    def integrate_area(x: np.ndarray, y: np.ndarray) -> float:
        """计算面积 (积分)"""
        return np.trapz(y, x)

    @staticmethod
    @st.cache_data
    def fit_curve(x: np.ndarray, y: np.ndarray, model: str = 'gaussian') -> dict:
        """特定曲线拟合"""
        def gaussian(x, amp, cen, wid):
            return amp * np.exp(-(x-cen)**2 / (2*wid*wid))
        
        try:
            if model == 'gaussian':
                p0 = [np.max(y), x[np.argmax(y)], (np.max(x)-np.min(x))/10]
                popt, _ = optimize.curve_fit(gaussian, x, y, p0=p0, maxfev=5000)
                fitted_y = gaussian(x, *popt)
                return {"fitted_y": fitted_y, "params": popt}
        except:
            pass
        return {"fitted_y": y, "params": []}

    @staticmethod
    def interpolate_data(x: np.ndarray, y: np.ndarray, num_points: int = 1000) -> dict:
        """插值"""
        f = interpolate.interp1d(x, y, kind='cubic')
        x_new = np.linspace(np.min(x), np.max(x), num_points)
        y_new = f(x_new)
        return {"x": x_new, "y": y_new}

    @staticmethod
    def remove_outliers(y: np.ndarray, threshold: float = 3.0) -> np.ndarray:
        """去除异常值 (Z-score 替代)"""
        mean_y = np.mean(y)
        std_y = np.std(y)
        z_scores = np.abs((y - mean_y) / (std_y + 1e-9))
        mask = z_scores < threshold
        # 为了不改变数组长度，异常值用插值或均值替代，这里简单用均值
        y_clean = y.copy()
        y_clean[~mask] = mean_y # 简单的策略
        return y_clean

    @staticmethod
    def crop_range(x: np.ndarray, y: np.ndarray, x_min: float, x_max: float) -> dict:
        """数据裁剪"""
        mask = (x >= x_min) & (x <= x_max)
        return {"x": x[mask], "y": y[mask]}

    # ==================== 📈 分析功能 (Analysis) ====================

    @staticmethod
    def calc_fwhm(x: np.ndarray, y: np.ndarray) -> float:
        """计算半高宽 (FWHM)"""
        peaks, _ = signal.find_peaks(y)
        if len(peaks) == 0: return 0.0
        
        # 取最高峰
        main_peak = peaks[np.argmax(y[peaks])]
        half_max = y[main_peak] / 2.0
        
        # 寻找左右交点
        # 简单算法：搜索最近的索引
        signs = np.sign(y - half_max)
        zero_crossings = (signs[:-1] != signs[1:])
        cross_indices = np.where(zero_crossings)[0]
        
        # 找到包围峰值的两个点
        left = cross_indices[cross_indices < main_peak]
        right = cross_indices[cross_indices > main_peak]
        
        if len(left) > 0 and len(right) > 0:
            x_l = x[left[-1]]
            x_r = x[right[0]]
            return abs(x_r - x_l)
        return 0.0

    @staticmethod
    def calc_slope(x: np.ndarray, y: np.ndarray) -> float:
        """计算整体斜率 (线性拟合)"""
        slope, intercept = np.polyfit(x, y, 1)
        return slope

    @staticmethod
    def compare_samples(y1: np.ndarray, y2: np.ndarray) -> dict:
        """样品对比 (简单的统计差异)"""
        diff = np.mean(y1) - np.mean(y2)
        corr = np.corrcoef(y1, y2)[0, 1] if len(y1) == len(y2) else None
        return {"mean_diff": diff, "correlation": corr}

    @staticmethod
    def batch_process(data_list: list, func_name: str, **kwargs) -> list:
        """(Placeholder) 批量处理入口"""
        # 实际逻辑需在应用层结合 DataTools.method 调用
        return [{"status": "pending", "func": func_name}]

    @staticmethod
    def suggest_next_step(data: np.ndarray) -> str:
        """(Rule-based) 智能建议下一 步"""
        # 简单规则：噪音大 -> 平滑；有峰 -> 拟合
        std = np.std(data)
        if std > np.mean(data) * 0.1:
            return "建议数据平滑 (Smooth)"
        return "建议峰值分析 (Find Peaks)"

    # ==================== 🎨 图表样式 (Chart Styles) ====================
    # (保持原样，供 AI 调用建议使用)
    
    @staticmethod
    def set_label(axis: str, label: str) -> dict:
        """设置轴标签 (axis='x' or 'y')"""
        return {"type": "style", "action": "set_label", "axis": axis, "label": label}
        
    @staticmethod
    def set_range(axis: str, min_val: float, max_val: float) -> dict:
        """设置轴范围"""
        return {"type": "style", "action": "set_range", "axis": axis, "min": min_val, "max": max_val}
        
    @staticmethod
    def set_color(curve_name: str, color: str) -> dict:
        """设置曲线颜色"""
        return {"type": "style", "action": "set_color", "curve": curve_name, "color": color}
        
    @staticmethod
    def set_line_style(curve_name: str, style: str) -> dict:
        """设置线型 (solid, dash, dot)"""
        return {"type": "style", "action": "set_line_style", "curve": curve_name, "style": style}
        
    @staticmethod
    def add_legend(show: bool = True) -> dict:
        """显示/隐藏图例"""
        return {"type": "style", "action": "config_legend", "show": show}
    
    @staticmethod
    def add_title(title: str) -> dict:
        """设置图表标题"""
        return {"type": "style", "action": "set_title", "title": title}
        
    @staticmethod
    def invert_axis(axis: str) -> dict:
        """反转坐标轴"""
        return {"type": "style", "action": "invert_axis", "axis": axis}
        
    @staticmethod
    def log_scale(axis: str) -> dict:
        """设置对数坐标"""
        return {"type": "style", "action": "log_scale", "axis": axis}
        
    @staticmethod
    def dual_y_axis(enable: bool = True) -> dict:
        """启用双Y轴"""
        return {"type": "style", "action": "dual_y_axis", "enable": enable}

    # ==================== 🌐 AI 增强 (AI Enhanced) ====================
    
    @staticmethod
    def web_search(query: str) -> str:
        """(Mock) 联网搜索占位符"""
        return f"[Mock Search] 正在搜索: {query} (需接入 Search API)"

    @staticmethod
    def analyze_image(image_base64: str) -> str:
        """(Placeholder) 图片分析入口"""
        return "Image analysis request prepared."
