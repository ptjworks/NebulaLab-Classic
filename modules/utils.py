import json
import os
from typing import Dict, Any, List
from datetime import datetime
from modules.schemas import CleaningRule, ColumnConfig, Transformation

# ==================== 🛠️ 基础工具 (Utils) ====================

def load_config(file_path: str = "ai_config.json") -> Dict[str, Any]:
    """加载配置文件"""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config: Dict[str, Any], file_path: str = "ai_config.json"):
    """保存配置文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")


def load_chat_sessions(file_path: str = "chat_history.json") -> Dict[str, Any]:
    """Load chat sessions with migration support."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Migration: Old format was a list of messages
                if isinstance(data, list):
                    return {
                        "sessions": {
                            "default": {
                                "id": "default",
                                "title": "默认对话",
                                "messages": data
                            }
                        },
                        "active_session_id": "default"
                    }
                return data
        except Exception as e:
            print(f"Error loading chat history: {e}")
            return {"sessions": {}, "active_session_id": None}
            
    return {"sessions": {}, "active_session_id": None}

def save_chat_sessions(sessions_data: Dict[str, Any], file_path: str = "chat_history.json"):
    """Save chat sessions to disk."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(sessions_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving chat sessions: {e}")


def estimate_tokens(text: str) -> int:
    """简单估算 Token 数 (按 0.75 ratio)"""
    return int(len(text) * 0.75)

# ==================== 🔄 规则转换工具 (Rule Conversion) ====================

def settings_to_rule(name: str, settings: Dict[str, Any]) -> CleaningRule:
    """
    Converts UI settings dict to a CleaningRule object.
    """
    # 1. Map Columns
    cols = {}
    aliases = settings.get('column_aliases', {})
    for orig, alias in aliases.items():
        cols[str(orig)] = ColumnConfig(
            original_name=str(orig),
            alias=alias if alias != str(orig) else None,
            keep=True
        )
    
    # 2. Map Transformations
    transforms = []
    for t in settings.get('transformations', []):
        try:
            transforms.append(Transformation(
                column=t['column'],
                operation=t['op'],
                value=t['val']
            ))
        except:
            pass # Skip invalid

    # 3. Create Object
    return CleaningRule(
        name=name,
        created_at=datetime.now().isoformat(),
        file_type=settings.get('file_type', 'csv'),
        header_row=settings.get('header_row', 0),
        use_header=settings.get('use_header', True), # [FIX] Persist use_header
        skip_rows=settings.get('skip_rows', 0),
        delimiter=settings.get('delimiter'),
        sheet_name=settings.get('sheet_name', 0),
        encoding=settings.get('encoding', 'utf-8'),
        columns=cols,
        transformations=transforms
    )

def rule_to_settings(rule: CleaningRule) -> Dict[str, Any]:
    """
    Converts a CleaningRule object back to UI settings dict.
    """
    # 1. Aliases
    aliases = {}
    for col_cfg in rule.columns.values():
        if col_cfg.keep:
            aliases[col_cfg.original_name] = col_cfg.alias or col_cfg.original_name
            
    # 2. Transformations
    transforms = []
    for t in rule.transformations:
        transforms.append({
            "column": t.column,
            "op": t.operation,
            "val": t.value
        })
        
    # 3. Build Dict
    return {
        'file_type': rule.file_type,
        'header_row': rule.header_row,
        'use_header': rule.use_header, # [FIX] Restore use_header
        'skip_rows': rule.skip_rows,
        'delimiter': rule.delimiter,
        'sheet_name': rule.sheet_name,
        'encoding': rule.encoding,
        'column_aliases': aliases,
        'transformations': transforms
    }
