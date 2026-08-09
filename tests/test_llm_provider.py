"""Tests for the LLM Provider."""

import json
from io import BytesIO

import pytest
from beernotes.llm_provider import LLMProvider, LLMWorker


class MockResponse:
    def __init__(self, content_dict):
        self.content_dict = content_dict

    def read(self):
        return json.dumps(self.content_dict).encode("utf-8")
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_llm_provider_initialization():
    provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")
    assert provider.api_url == "http://localhost:8080/v1"
    assert provider.api_key == "test-key"
    assert provider.model_name == "test-model"


def test_llm_provider_complete(monkeypatch):
    provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")
    
    def mock_urlopen(req, timeout=None):
        assert req.full_url == "http://localhost:8080/v1/chat/completions"
        assert req.get_header("Authorization") == "Bearer test-key"
        data = json.loads(req.data.decode("utf-8"))
        assert data["model"] == "test-model"
        assert len(data["messages"]) == 2
        
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": "This is a summarized text."
                    }
                }
            ]
        }
        return MockResponse(response_data)
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    result = provider.summarize("This is a long text that needs summarization.")
    assert result == "This is a summarized text."


def test_llm_provider_worker(monkeypatch, qtbot):
    provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")
    
    def mock_urlopen(req, timeout=None):
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Worker test result"
                    }
                }
            ]
        }
        return MockResponse(response_data)
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    with qtbot.waitSignal(provider.result_ready, timeout=1000) as blocker:
        provider.run_async("Test prompt")
        
    assert blocker.args[0] == "Worker test result"


def test_llm_provider_worker_error(monkeypatch, qtbot):
    provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")
    
    def mock_urlopen_error(req, timeout=None):
        raise Exception("Mock error")
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)
    
    with qtbot.waitSignal(provider.error_occurred, timeout=1000) as blocker:
        provider.run_async("Test prompt")
        
    assert "Mock error" in blocker.args[0]
