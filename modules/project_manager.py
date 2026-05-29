import pickle
import base64
import streamlit as st
import datetime
import io

class ProjectManager:
    """
    Handles project lifecycle: save, load, and auto-recovery for Nebula Lab Classic.
    Project format: .nbp (Nebula Project) - Binary pickle file.
    """
    
    REQUIRED_KEYS = [
        'data_repo', 
        'settings_repo', 
        'chart_styles', 
        'processed_data',
        'current_page',
        'file_buffers'  # [Persistence] Include raw source files
    ]

    @staticmethod
    def export_project():
        """
        Serializes current session state into a binary byte stream.
        Includes all required data keys AND dynamic UI state keys (ending with _wb).
        """
        project_data = {}
        
        # 1. Save Core Data
        for key in ProjectManager.REQUIRED_KEYS:
            if key in st.session_state:
                project_data[key] = st.session_state[key]
        
        # 2. Save UI State (Dynamic Widget Keys)
        # Scan session_state for any key ending in '_wb' (workspace widgets)
        ui_state = {k: st.session_state[k] for k in st.session_state if k.endswith('_wb')}
        project_data['__ui_state__'] = ui_state
        
        # 3. Add Metadata
        project_data['__meta__'] = {
            'version': '5.4',
            'saved_at': datetime.datetime.now().isoformat(),
            'platform': 'Nebula Vision Workbench'
        }
        
        return pickle.dumps(project_data)

    @staticmethod
    def import_project(binary_data):
        """
        De-serializes project file and injects data back into session_state.
        """
        try:
            data = pickle.loads(binary_data)
            
            # Basic validation
            if '__meta__' not in data:
                return False, "❌ 无效的工程文件：缺失元数据。"
            
            # 1. Restore Core Data
            for key in ProjectManager.REQUIRED_KEYS:
                if key in data:
                    st.session_state[key] = data[key]
            
            # 2. Restore UI State
            if '__ui_state__' in data:
                for k, v in data['__ui_state__'].items():
                    st.session_state[k] = v
            
            return True, f"✅ 工程恢复成功！(保存于: {data['__meta__']['saved_at'][:19]})"
        except Exception as e:
            return False, f"❌ 加载失败: {str(e)}"

    @staticmethod
    def inject_unload_protection():
        """
        Injects a robust JavaScript payload to provide 'Before Unload' confirmation.
        Uses st.components.v1.html to ensure the script runs in the window context.
        """
        # We use a trick: injecting script into the parent window since Streamlit components are iframed
        js_code = """
        <script>
            (function() {
                var p = window.parent || window;
                function protect() {
                    p.onbeforeunload = function(e) {
                        var msg = '您有未保存的工程进度，确定要离开吗？';
                        e = e || p.event;
                        if (e) e.returnValue = msg;
                        return msg;
                    };
                }
                protect();
                // Re-apply on any potential navigation or interaction
                p.addEventListener('mousedown', protect, {once: true});
                console.log("Nebula Persistence Guard: Deep Active");
            })();
        </script>
        """
        # Set height=0 to keep it invisible
        st.components.v1.html(js_code, height=0)
