import os
import json
from typing import List, Optional
from modules.schemas import CleaningRule

# Default directory for storing rules
RULES_DIR = "rules"

class RuleManager:
    """
    Manages the lifecycle of CleaningRule objects (Save, Load, List, Delete).
    Stores rules as .nbr (Nebula Rule) JSON files.
    """
    
    def __init__(self, rules_dir: str = RULES_DIR):
        self.rules_dir = rules_dir
        if not os.path.exists(self.rules_dir):
            os.makedirs(self.rules_dir)
            
    def _get_path(self, name: str) -> str:
        # Sanitize name to avoid path traversal or invalid chars
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        return os.path.join(self.rules_dir, f"{safe_name}.nbr")

    def save_rule(self, rule: CleaningRule) -> str:
        """
        Saves a CleaningRule object to disk.
        Returns the absolute path of the saved file.
        """
        path = self._get_path(rule.name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(rule.model_dump_json(indent=2))
        return path

    def load_rule(self, name: str) -> Optional[CleaningRule]:
        """
        Loads a CleaningRule by name.
        """
        path = self._get_path(name)
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_data = f.read()
            # Validate and parse
            return CleaningRule.model_validate_json(json_data)
        except Exception as e:
            print(f"Error loading rule {name}: {e}")
            return None

    def list_rules(self) -> List[str]:
        """
        Returns a list of available rule names (without extension).
        """
        if not os.path.exists(self.rules_dir):
            return []
            
        files = [f for f in os.listdir(self.rules_dir) if f.endswith('.nbr')]
        # Sort by modification time (newest first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.rules_dir, x)), reverse=True)
        
        return [f[:-4] for f in files]

    def delete_rule(self, name: str) -> bool:
        """
        Deletes a rule file.
        """
        path = self._get_path(name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
