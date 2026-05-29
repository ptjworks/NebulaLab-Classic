"""
通用数据清洗与加载模块 (Universal Data Loader)
==============================================
核心功能：
1. 文件类型路由 (File Router)
2. 通用文本嗅探算法 (Universal Sniffer) - 基于数据密度
3. 数据读取执行器 (Data Loading Executor) - 自动清洗

Designed for Scientific Data Processing
"""

import pandas as pd
import numpy as np
# from scipy.signal import savgol_filter # Moved to data_tools.py
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from io import BytesIO, StringIO
import re

# ==============================================================================
# 1. 数据结构定义
# ==============================================================================

@dataclass
class FileAnalysisResult:
    """文件分析结果，用于 UI 预填参数"""
    file_type: str                    # 'csv', 'txt', 'excel'
    encoding: str                     # 检测到的编码
    delimiter: Optional[str]          # 分隔符（CSV/TXT）
    header_row: int                   # 推荐的表头行号（0-indexed）
    skip_rows: int                    # 建议跳过的行数（用于 skiprows）
    sheet_names: Optional[List[str]]  # Excel 工作表名称列表
    preview_lines: List[str]          # 原始文件前 N 行预览
    total_lines: int                  # 总行数估计
    has_header: bool                  # 是否检测到表头
    suggested_columns: List[str]      # 推荐的列名
    warnings: List[str]               # 警告信息

class UnsupportedFormatError(Exception):
    pass

# ==============================================================================
# 2. 核心分析类 (The Universal Sniffer)
# ==============================================================================

class DataAnalyzer:
    """
    通用数据分析器
    使用启发式算法自动检测：编码、分隔符、表头位置、数据起始行
    """
    
    COMMON_DELIMITERS = [',', '\t', ';', ' ', '|']
    COMMON_ENCODINGS = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'utf-16']
    
    def __init__(self, preview_lines: int = 200):
        self.preview_lines = preview_lines  # 增加到 200 行以提高准确性
    
    def analyze(self, uploaded_file) -> FileAnalysisResult:
        """主入口：分析文件结构"""
        filename = uploaded_file.name.lower()
        
        # Binary check based on extension
        if filename.endswith(('.raw', '.brml', '.bin', '.dat')):
            # 虽然 .dat 可能是文本，但也可能是二进制。这里简单处理，如果用户坚持是文本，可以改后缀
            # 根据需求文档，.dat 归类为 TEXT，但我们可以尝试读取，如果失败再报错
            pass
            
        if filename.endswith(('.raw', '.brml')):
             raise UnsupportedFormatError(f"不支持的二进制格式: {filename.split('.')[-1]}，请先转换为 CSV 或 Excel。")

        # Route by extension
        if filename.endswith(('.xlsx', '.xls')):
            return self._analyze_excel(uploaded_file)
        else:
            # 默认当作文本处理 (.csv, .txt, .xy, .asc, .dat)
            return self._analyze_text(uploaded_file)
    
    def _analyze_excel(self, uploaded_file) -> FileAnalysisResult:
        """分析 Excel 文件"""
        warnings = []
        try:
            xl = pd.ExcelFile(uploaded_file)
            sheet_names = xl.sheet_names
            
            # 默认分析第一个 Sheet
            df_preview = pd.read_excel(uploaded_file, sheet_name=0, nrows=self.preview_lines, header=None)
            
            # 将 DataFrame 转换为类似文本行的格式用于统一分析逻辑（可选，但这简单点）
            # 或者直接对 DF 进行分析
            header_row, data_start_row = self._detect_structure_from_df(df_preview)
            
            # 生成预览文本
            preview_lines = []
            for _, row in df_preview.head(20).iterrows():
                preview_lines.append(" | ".join([str(x) for x in row if pd.notna(x)]))

            # 获取列名建议
            if header_row is not None:
                cols = df_preview.iloc[header_row].tolist()
                suggested_columns = [str(c) for c in cols]
                skip_rows = data_start_row # Excel 的 skiprows 通常指跳过多少行开始读数据，或者配合 header 使用
                # Pandas read_excel 的 header 参数指定表头所在行。
                # 如果 header=2, 那么第 0,1 行被跳过。
                # 所以这里 header_row 就是我们要传给 read_excel 的 header
            else:
                suggested_columns = [f"Col_{i}" for i in range(df_preview.shape[1])]
                header_row = 0 # Fallback

            return FileAnalysisResult(
                file_type='excel',
                encoding='N/A',
                delimiter=None,
                header_row=header_row if header_row is not None else 0,
                # [FIX] Same logic for Excel: skip garbage before header
                skip_rows=header_row if header_row is not None else data_start_row,
                sheet_names=sheet_names,
                preview_lines=preview_lines,
                total_lines=len(df_preview), # 只是预览的行数
                has_header=(header_row is not None),
                suggested_columns=suggested_columns,
                warnings=warnings
            )
            
        except Exception as e:
            raise ValueError(f"Excel 解析失败: {str(e)}")

    def _analyze_text(self, uploaded_file) -> FileAnalysisResult:
        """分析文本文件 (CSV, TXT, etc.)"""
        warnings = []
        
        # 1. 编码检测与读取
        raw_content = uploaded_file.getvalue()
        uploaded_file.seek(0)
        encoding = self._detect_encoding(raw_content)
        
        try:
            content = raw_content.decode(encoding)
        except:
            encoding = 'latin-1' # Fallback
            content = raw_content.decode(encoding)
            warnings.append(f"编码检测失败，已回退到 {encoding}")
            
        lines = content.splitlines()
        total_lines = len(lines)
        sample_lines = lines[:self.preview_lines]
        
        # 2. 分隔符推断 (Universal Sniffer Core)
        delimiter = self._detect_delimiter_by_stability(sample_lines)
        if not delimiter:
            delimiter = ',' # Default fallback
            warnings.append("无法检测到清晰的分隔符，默认为逗号")

        # 3. 数据结构推断 (Header & Data Start)
        header_row, data_start_row = self._detect_structure_by_density(sample_lines, delimiter)
        
        # 4. 生成列名建议
        suggested_columns = []
        if header_row is not None and header_row < len(sample_lines):
            header_line = sample_lines[header_row]
            if delimiter:
                cols = header_line.split(delimiter)
            else:
                cols = header_line.split()
            suggested_columns = [c.strip() for c in cols]
        else:
            # 尝试从第一行数据推断列数
            if data_start_row < len(sample_lines):
                data_line = sample_lines[data_start_row]
                parts = data_line.split(delimiter) if delimiter else data_line.split()
                suggested_columns = [f"Col_{i}" for i in range(len(parts))]
        
        return FileAnalysisResult(
            file_type='txt', # 统称 TEXT
            encoding=encoding,
            delimiter=delimiter,
            header_row=header_row if header_row is not None else 0,
            # [FIX] Skip rows should point to the HEADER line (skipping garbage before it), not the Data line (which skips header!)
            skip_rows=header_row if header_row is not None else data_start_row,
            sheet_names=None,
            preview_lines=sample_lines, # 返回此时的 str list
            total_lines=total_lines,
            has_header=(header_row is not None),
            suggested_columns=suggested_columns,
            warnings=warnings
        )

    def _detect_encoding(self, raw_bytes: bytes) -> str:
        """检测 BOM，否则尝试解码"""
        if raw_bytes.startswith(b'\xef\xbb\xbf'): return 'utf-8-sig'
        if raw_bytes.startswith(b'\xff\xfe'): return 'utf-16-le'
        
        for enc in ['utf-8', 'gbk', 'latin-1']:
            try:
                raw_bytes[:1000].decode(enc)
                return enc
            except:
                continue
        return 'utf-8'

    def _detect_delimiter_by_stability(self, lines: List[str]) -> Optional[str]:
        """
        基于稳定性检测分隔符：
        计算每种分隔符在各行出现次数的标准差 (std_dev)。
        标准差越小，说明每行列数越一致，该分隔符的可能性越大。
        """
        valid_lines = [line.strip() for line in lines if line.strip()]
        if not valid_lines:
            return None
        
        candidates = []
        for d in self.COMMON_DELIMITERS:
            # 统计每行该分隔符出现的次数
            counts = [line.count(d) for line in valid_lines[:50]] # 取前 50 行非空行分析
            if not counts: continue
            
            mean_count = np.mean(counts)
            if mean_count < 1: continue # 几乎没出现过
            
            std_dev = np.std(counts)
            
            # 评分规则：标准差越低越好，(频率适中也有加分，但最重要的是稳定)
            # 我们直接用 cv (变异系数) = std / mean
            cv = std_dev / mean_count
            candidates.append((d, cv, mean_count))
        
        if not candidates:
            return None
            
        # 按变异系数排序（越小越稳），其次按出现频率（越多可能列数越多）
        candidates.sort(key=lambda x: (x[1], -x[2]))
        
        return candidates[0][0]

        return 0, 0 # Fallback

    def _detect_header_by_keywords(self, lines: List[str]) -> Optional[int]:
        """
        基于高频科研关键词检测表头
        """
        KEYWORDS = ['Time', 'Temp', 'Wavenumber', 'Absorbance', 'Pressure', 'Voltage', 
                    'Theta', 'Intensity', 'Energy', 'Counts', 'Mass', 'Heat Flow', 
                    'Transmittance', 'Frequency', 'Current',
                    # Chinese Keywords
                    '时间', '温度', '重量', '压力', '电流', '电压', '波数', '吸光度', '强度', '质量']
        
        best_row = None
        max_score = 0
        
        # 只扫描前 50 行，避免无关行干扰
        for i, line in enumerate(lines[:50]):
            score = 0
            line_str = line.strip()
            if not line_str: continue
            
            # 关键词匹配加分
            for kw in KEYWORDS:
                if kw.lower() in line_str.lower():
                    score += 1
            
            # 如果包含字母，额外加分 (表头通常是文本)
            if any(c.isalpha() for c in line_str):
                score += 0.5
                
            if score > max_score and score >= 1.5: # 至少命中一个关键词 (+0.5 isalpha) 才有资格
                max_score = score
                best_row = i
                
        return best_row

    def _detect_structure_by_density(self, lines: List[str], delimiter: Optional[str]) -> Tuple[Optional[int], int]:
        """
        基于数值密度检测数据区 + 关键词修正表头
        """
        # 1. 先尝试关键词检测表头
        keyword_header = self._detect_header_by_keywords(lines)
        
        # 2. 原有的数值密度检测
        def count_numbers(line):
            if not line.strip(): return 0
            parts = line.split(delimiter) if delimiter else line.split()
            count = 0
            for p in parts:
                try:
                    float(p.strip())
                    count += 1
                except:
                    pass
            return count

        consecutive_numeric_lines = 0
        data_start_index = 0
        
        for i, line in enumerate(lines):
            nums = count_numbers(line)
            if nums >= 2: 
                if consecutive_numeric_lines == 0:
                    data_start_index = i 
                consecutive_numeric_lines += 1
            else:
                consecutive_numeric_lines = 0 
            
            if consecutive_numeric_lines >= 3:
                # 找到了数据区
                
                # 决策表头逻辑：
                # 如果 Keyword 找到了表头，且在数据区之前，那就信 Keyword
                if keyword_header is not None and keyword_header < data_start_index:
                    return keyword_header, data_start_index
                
                # 否则回溯 1 行
                best_header_row = data_start_index - 1
                if best_header_row < 0: best_header_row = None
                return best_header_row, data_start_index
                
        # 如果没找到数据区，但找到了 keyword header
        if keyword_header is not None:
             # 假设数据在 header 下一行
             return keyword_header, keyword_header + 1
             
        return None, 0

    def _detect_structure_from_df(self, df: pd.DataFrame) -> Tuple[Optional[int], int]:
        """对 DataFrame 进行类似的数值密度分析"""
        def is_numeric_row(row):
            numeric_count = 0
            for x in row:
                if pd.api.types.is_number(x) and not pd.isna(x):
                    numeric_count += 1
                else:
                    try:
                        float(str(x))
                        numeric_count += 1
                    except:
                        pass
            return numeric_count >= 2

        consecutive = 0
        start_idx = 0
        
        for i in range(len(df)):
            if is_numeric_row(df.iloc[i]):
                if consecutive == 0:
                    start_idx = i
                consecutive += 1
            else:
                consecutive = 0
            
            if consecutive >= 3:
                return (start_idx - 1) if start_idx > 0 else None, start_idx
        
        return 0, 0 # Fallback


# ==============================================================================
# 3. 数据加载执行器 (Execution)
# ==============================================================================

class DataLoader:
    """
    负责执行最终的数据读取与清洗
    """
    def load(self, uploaded_file, params: Dict[str, Any]) -> pd.DataFrame:
        file_type = params.get('file_type', 'txt')
        raw_mode = params.get('raw_mode', False) # New parameter
        
        uploaded_file.seek(0)
        
        try:
            if file_type == 'excel':
                df = self._load_excel(uploaded_file, params)
            else:
                df = self._load_text(uploaded_file, params)
            
            # --- Raw Mode (上帝视角) ---
            # 如果开启 Raw Mode，直接返回读取结果，不做任何清洗
            if raw_mode:
                return df
                
            # --- 自动清洗 ---
            df.dropna(how='all', inplace=True)
            
            # --- 1. 列重命名与过滤 (Aliasing & Filtering) ---
            column_aliases = params.get('column_aliases', {})
            # [FIX] Enforce string column names IMMEDIATELY to avoid type mismatches (Int vs Str)
            df.columns = df.columns.astype(str)
            
            if column_aliases:
                # 增强稳定性：Fuzzy Matching (Strip whitespace + Lowercase)
                # Map {CleanName: OriginalName}
                col_map = {str(c).strip().lower(): c for c in df.columns}
                
                matched_cols = []
                rename_dict = {}
                
                for alias_key, target_alias in column_aliases.items():
                    # alias_key is the "Original Name" stored in Rule
                    # We also clean the key to match
                    clean_key = str(alias_key).strip().lower()
                    
                    if clean_key in col_map:
                        orig_col = col_map[clean_key]
                        matched_cols.append(orig_col)
                        rename_dict[orig_col] = target_alias
                    # Fallback strategies were removed as clean_key covers strict match too (if case matches)
                
                if not matched_cols:
                    # 如果一个都没匹配上（通常是切换了表头行导致旧配置失效），则放弃过滤，返回所有原始列
                    # 这样用户至少能看到数据并重新配置，而不是看到一个空报错
                    pass
                else:
                    # Keep order based on Rule? Or Message?
                    # We currently append in simple order. 
                    # Drop duplicates if any.
                    matched_cols = list(dict.fromkeys(matched_cols))
                    df = df[matched_cols]
                    df.rename(columns=rename_dict, inplace=True)
            
            # --- 2. 智能数值转换 ---
            original_columns = df.columns
            df_numeric = df.apply(pd.to_numeric, errors='coerce')
            df_numeric.columns = original_columns
            
            # --- 3. 数据转换 (Transformations) ---
            transformations = params.get('transformations', [])
            for rule in transformations:
                col = rule.get('column')
                op = rule.get('op')
                val_raw = rule.get('val', 0.0)
                
                if col in df_numeric.columns:
                    try:
                        # 动态常量支持
                        if val_raw == "__COL_FIRST__":
                            # 获取第一个非空值
                            val = df_numeric[col].dropna().iloc[0] if not df_numeric[col].dropna().empty else 1.0
                        elif val_raw == "__COL_MAX__":
                            val = df_numeric[col].max()
                        elif val_raw == "__COL_MIN__":
                            val = df_numeric[col].min()
                        else:
                            val = float(val_raw)
                        
                        if op == '+': df_numeric[col] = df_numeric[col] + val
                        elif op == '-': df_numeric[col] = df_numeric[col] - val
                        elif op == '*': df_numeric[col] = df_numeric[col] * val
                        elif op == '/': 
                            if val != 0: df_numeric[col] = df_numeric[col] / val
                    except:
                        pass

            # --- 4. 移除完全无效的行/列 ---
            # 仅移除全空行，保留列结构
            df_clean = df_numeric.dropna(axis=0, how='all')
            
            if df_clean.empty:
                raise ValueError("读取结果为空。请检查：1. [表头行号] 是否正确；2. [分隔符] 是否匹配；3. [跳过行数] 是否过多。")
                
            return df_clean
            
        except Exception as e:
            raise ValueError(f"读取执行失败: {str(e)}")

    def _load_excel(self, file, params):
        raw_mode = params.get('raw_mode', False)
        
        # Raw Mode: 强制 header=None 以读取所有文本
        if raw_mode:
            return pd.read_excel(file, sheet_name=params.get('sheet_name', 0), header=None)
            
        return pd.read_excel(
            file,
            sheet_name=params.get('sheet_name', 0),
            header=params.get('header_row', 0) if params.get('use_header') else None,
            # Excel 中 skiprows 行为比较特殊，通常有了 header 就不需要 skiprows 
            # 除非数据在 header 之后还隔了几行。这里简单处理：
            # 如果 params 提供了 manual_skiprows (用户手动输入), 则优先使用
            skiprows=params.get('skip_rows') if not params.get('use_header') else None
        )

    def _load_text(self, file, params):
        raw_mode = params.get('raw_mode', False)
        
        delimiter = params.get('delimiter')
        if delimiter == 'auto': delimiter = None
        # 映射转义字符
        sep = delimiter
        if sep == '\\t': sep = '\t'
        
        # Raw Mode: 强制 header=None, sep=None (sniffer logic might interfere, better stick to sep/delimiter but ignore headers)
        if raw_mode:
             # 为了尽量看清原始文本，我们尝试用 sep 读取，但如果 sep 不明确，可能读乱。
             # Raw 模式这里主要为了看行号，所以还是用检测到的 sep，但不要 header
             return pd.read_csv(
                file,
                sep=sep,
                encoding=params.get('encoding', 'utf-8'),
                header=None,
                skiprows=None, # Raw mode needs validation of all rows
                engine='python'
            )
        
        try:
            return pd.read_csv(
                file,
                sep=sep,
                encoding=params.get('encoding', 'utf-8'),
                header=params.get('header_row', 'infer') if params.get('use_header') else None,
                skiprows=params.get('skip_rows', 0),
                engine='python'
            )
        except UnicodeDecodeError:
            # Fallback strategy
            for enc in ['gbk', 'gb18030', 'latin-1']:
                try:
                    file.seek(0)
                    return pd.read_csv(
                        file,
                        sep=sep,
                        encoding=enc,
                        header=params.get('header_row', 'infer') if params.get('use_header') else None,
                        skiprows=params.get('skip_rows', 0),
                        engine='python'
                    )
                except:
                    continue
            raise ValueError(f"无法解码文件。已尝试 UTF-8, GBK, Latin-1。请检查文件编码。")

# ==============================================================================
# Helper functions for backward compatibility
# ==============================================================================

def load_data(uploaded_file):
    """兼容旧接口"""
    analyzer = DataAnalyzer()
    res = analyzer.analyze(uploaded_file)
    loader = DataLoader()
    return loader.load(uploaded_file, {
        'file_type': res.file_type,
        'encoding': res.encoding,
        'delimiter': res.delimiter,
        'header_row': res.header_row,
        'skip_rows': res.skip_rows,
        'use_header': res.has_header,
        'sheet_name': res.sheet_names[0] if res.sheet_names else 0
    })


# Helper functions moved to modules/data_tools.py
# (apply_smoothing, get_numeric_columns, get_data_summary)

