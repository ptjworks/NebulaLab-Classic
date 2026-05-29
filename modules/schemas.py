from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, Any

class Transformation(BaseModel):
    """
    Defines a mathematical operation on a column.
    """
    column: str          # Target column name (after alias applied)
    operation: str       # '+', '-', '*', '/'
    value: Union[float, str]   # Numeric value or magic string like "__COL_MAX__"

class ColumnConfig(BaseModel):
    """
    Defines how to handle a specific column.
    """
    original_name: str
    alias: Optional[str] = None
    keep: bool = True

class CleaningRule(BaseModel):
    """
    The root schema for a .nbr (Nebula Rule) file.
    """
    name: str = "Default Rule"
    created_at: str = "" # ISO Format
    file_type: str = "csv"
    
    # Parsing Configuration
    header_row: int = 0
    use_header: bool = True # [FIX] Add this field to control header usage
    skip_rows: int = 0
    delimiter: Optional[str] = ","
    sheet_name: Optional[Union[str, int]] = 0
    encoding: str = "utf-8"
    
    # Column Management
    # Key = original column name (for O(1) lookup), Value = Config
    columns: Dict[str, ColumnConfig] = Field(default_factory=dict)
    
    # Advanced Processing
    transformations: List[Transformation] = Field(default_factory=list)
    
    # Meta
    description: Optional[str] = ""
