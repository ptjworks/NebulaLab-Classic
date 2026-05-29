"""
AI 服务模块 (Enhanced AI Service)
=================================
负责与 LLM API 交互，支持文本分析与多模态图片理解
"""

from openai import OpenAI, AuthenticationError, APIConnectionError, RateLimitError
from typing import Optional, List, Dict, Any
import base64

from dataclasses import dataclass, field

@dataclass
class ProviderConfig:
    """
    [Architecture] 服务商配置数据类
    Separate configuration from logic for easier maintenance.
    """
    name: str                       # 显示名称
    base_url: str                   # API Base URL
    default_model: str              # 默认推荐模型
    models: List[str]               # 常用模型列表
    api_key_env: str = ""           # (Optional) 环境变量名, e.g. "OPENAI_API_KEY"
    help_text: str = ""             # 用户提示
    requires_headers: bool = False  # 是否需要特殊 Headers (如 OpenRouter)

# ==================== 🛠️ AI 服务商配置库 (Registry) ====================
# For AI Maintainer: Add new providers here directly.
AI_PROVIDERS: Dict[str, ProviderConfig] = {
    "OpenRouter": ProviderConfig(
        name="OpenRouter (聚合)",
        base_url="https://openrouter.ai/api/v1",
        default_model="google/gemini-2.0-flash-exp:free",
        models=["google/gemini-2.0-flash-exp:free", "deepseek/deepseek-chat", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3-8b-instruct:free"],
        help_text="支持免费模型 (如 Gemini 2.0 Flash) 及付费顶级模型",
        requires_headers=True
    ),
    "SiliconFlow": ProviderConfig(
        name="SiliconFlow (硅基流动)",
        base_url="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-V3",
        models=["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-7B-Instruct"],
        help_text="国内高速 API，支持 DeepSeek 系列"
    ),
    "DeepSeek": ProviderConfig(
        name="DeepSeek (官方)",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        models=["deepseek-chat", "deepseek-reasoner"],
        help_text="DeepSeek 官方 API"
    ),
    "OpenAI": ProviderConfig(
        name="OpenAI (官方)",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        help_text="标准 OpenAI 服务"
    ),
    "Anthropic": ProviderConfig(
        name="Anthropic (Claude)",
        base_url="https://api.anthropic.com/v1", # Note: Anthropic python client usually handles this, but here we assume OpenAI-compatible adapter or generic usage
        default_model="claude-3-5-sonnet-20240620",
        models=["claude-3-5-sonnet-20240620", "claude-3-opus-20240229"],
        help_text="Claude 系列 (需确认 API 兼容性或使用 OpenRouter)"
    ),
    "Ollama": ProviderConfig(
        name="Ollama (本地)",
        base_url="http://localhost:11434/v1",
        default_model="llama3",
        models=["llama3", "mistral", "qwen2"],
        help_text="完全本地运行，保护隐私。需先安装 Ollama。"
    ),
    "CherryStudio": ProviderConfig(
        name="CherryStudio (Local)",
        base_url="http://localhost:8080/v1",
        default_model="default-model",
        models=["default-model"],
        help_text="连接本地 Cherry Studio 服务"
    ),
    "Custom": ProviderConfig(
        name="自定义 (Custom)",
        base_url="",
        default_model="",
        models=[],
        help_text="手动输入完整配置"
    )
}

class AIAnalyzer:
    def __init__(self, api_key: str, base_url: str, model_name: str, provider: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = provider
        self._client = None
    
    def _get_client(self) -> OpenAI:
        if self._client is None:
            kwargs = {"api_key": self.api_key, "base_url": self.base_url}
            
            # 自动注入 Headers (如果配置要求)
            if self.provider and self.provider in AI_PROVIDERS:
                config = AI_PROVIDERS[self.provider]
                if config.requires_headers:
                    kwargs["default_headers"] = {
                        "HTTP-Referer": "https://github.com/scientific-data-assistant",
                        "X-Title": "Scientific Data Assistant"
                    }
                    
            self._client = OpenAI(**kwargs)
        return self._client

    @staticmethod
    def fetch_available_models(api_key: str, base_url: str) -> List[str]:
        """
        [New] 获取远程模型列表
        """
        try:
            # Create a temporary client for listing models
            temp_client = OpenAI(api_key=api_key, base_url=base_url)
            models_response = temp_client.models.list()
            # Sort models by id
            model_ids = sorted([m.id for m in models_response.data])
            return model_ids
        except Exception as e:
            print(f"Failed to fetch models: {e}")
            return []

    def chat_stream(self, messages: List[Dict[str, Any]], temperature: float = 0.7):
        """
        [NEW] 流式输出接口 (Streaming Interface)
        Yields chunks of content for real-time display.
        """
        try:
            client = self._get_client()
            stream = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=4000,
                stream=True  # Enable streaming
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"❌ AI 响应错误: {str(e)}"

    def chat(self, messages: List[Dict[str, Any]], temperature: float = 0.7) -> str:
        """
        通用聊天接口，支持多轮对话与图片输入
        messages 格式遵循 OpenAI 标准:
        [{'role': 'user', 'content': 'text...'}, {'role': 'user', 'content': [{'type': 'text', ...}, {'type': 'image_url', ...}]}]
        """
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=4000
            )
            content = response.choices[0].message.content
            if not content:
                return "⚠️ AI 返回了空内容 (Empty Response)"
            return content
        except AuthenticationError:
            return "Error: 🚫 认证失败 (Authentication Failed)。请检查您的 API Key 是否正确。"
        except APIConnectionError:
            return "Error: 📡 连接失败 (Connection Failed)。请检查 Base URL 是否正确，或网络是否通畅。"
        except RateLimitError:
            return "Error: ⏳ 请求受限 (Rate Limit Exceeded)。您的额度已用完或请求太快。"
        except Exception as e:
            return f"❌ AI 响应错误: {str(e)}"

    def encode_image(self, uploaded_file) -> str:
        """将上传图片转为 Base64"""
        if uploaded_file is None: return None
        return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

    def analyze_data(self, df_summary: str, x_col: str, y_col: str) -> str:
        """(Legacy) 单次分析接口兼容易用"""
        prompt = f"""请分析实验数据：
        X轴: {x_col}, Y轴: {y_col}
        统计摘要:\n{df_summary}
        请从科研角度提供趋势分析、异常点识别及建议。"""
        
        messages = [
            {"role": "system", "content": "你是一位资深科研数据专家。"},
            {"role": "user", "content": prompt}
        ]
        return self.chat(messages)

class ContextManager:
    """
    [NEW] 上下文管理器: 负责组装 Prompt、图片截图预处理与 Token 估算
    """
    @staticmethod
    def get_chart_image(fig) -> str:
        """使用 Plotly to_image 生成 Base64 图片"""
        try:
            # Requires `kaleido` package installed for static export
            import io
            # 降低分辨率以节省 Token (如 800x600)
            img_bytes = fig.to_image(format="png", width=800, height=600, scale=1)
            return base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            # Fallback text if image generation fails
            print(f"Chart image generation failed: {e}")
            return None

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """简单估算 Token 数 (按 0.75 ratio)"""
        if not text: return 0
        return int(len(text) * 0.75)
    
    @staticmethod
    def prepare_full_data_context(df: Any, max_rows: int = 1000) -> str:
        """准备 CSV 格式的完整数据(有行数限制)"""
        if df.shape[0] > max_rows:
            return f"Data truncated (Top {max_rows} rows):\n" + df.head(max_rows).to_csv(index=False)
        return df.to_csv(index=False)




# DataTools class moved to modules/data_tools.py



