"""Beer Notes — LLM Provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class LLMWorker(QThread):
    """Worker thread for making LLM API requests."""
    
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_name: str,
        prompt: str,
        system_prompt: str = ""
    ) -> None:
        super().__init__()
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/v1/chat/completions") and not self.api_url.endswith("/chat/completions"):
            if self.api_url.endswith("/v1"):
                self.api_url += "/chat/completions"
            else:
                self.api_url += "/v1/chat/completions"
                
        self.api_key = api_key
        self.model_name = model_name
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self) -> None:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.prompt})

        data = {
            "model": self.model_name,
            "messages": messages,
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                self.result_ready.emit(content)
        except urllib.error.URLError as e:
            self.error_occurred.emit(f"Connection error: {e.reason}")
        except json.JSONDecodeError:
            self.error_occurred.emit("Invalid JSON response from API")
        except Exception as e:
            self.error_occurred.emit(f"API error: {e!s}")


class LLMProvider(QObject):
    """Provides LLM integration with OpenAI-compatible endpoints."""
    
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        model_name: str = "",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self._worker: LLMWorker | None = None
        
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Synchronous wrapper for tests, but actual calls use workers."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model_name,
            "messages": messages,
        }
        
        api_url = self.api_url.rstrip("/")
        if not api_url.endswith("/v1/chat/completions") and not api_url.endswith("/chat/completions"):
            if api_url.endswith("/v1"):
                api_url += "/chat/completions"
            else:
                api_url += "/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        req = urllib.request.Request(
            api_url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {e!s}"
            
    def run_async(self, prompt: str, system_prompt: str = "") -> None:
        self._worker = LLMWorker(
            self.api_url, self.api_key, self.model_name, prompt, system_prompt
        )
        self._worker.result_ready.connect(self.result_ready.emit)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.start()

    def summarize(self, text: str) -> str:
        system_prompt = "You are a helpful assistant that summarizes text concisely."
        prompt = f"Please summarize the following text:\n\n{text}"
        return self.complete(prompt, system_prompt)

    def continue_writing(self, text: str) -> str:
        system_prompt = "You are a helpful assistant that continues the writing seamlessly."
        prompt = f"Please continue the following text in the same style and tone:\n\n{text}"
        return self.complete(prompt, system_prompt)

    def fix_code(self, code: str) -> str:
        system_prompt = "You are an expert programmer. Fix the bugs and formatting in the provided code. Output ONLY the fixed code without any conversational text or markdown blocks if not necessary."
        prompt = f"Fix the following code:\n\n{code}"
        return self.complete(prompt, system_prompt)

    def improve_writing(self, text: str) -> str:
        system_prompt = "You are an expert editor. Improve the grammar, clarity, and flow of the text. Output ONLY the improved text."
        prompt = f"Improve the following text:\n\n{text}"
        return self.complete(prompt, system_prompt)
