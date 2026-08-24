"""Tests for the LLM Provider."""

import json
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from ayrannotes.llm_provider import LLMProvider, LLMWorker


class MockResponse:
    def __init__(self, content_dict):
        self.content_dict = content_dict

    def read(self):
        return json.dumps(self.content_dict).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class LLMProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_llm_provider_initialization(self):
        provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")
        self.assertEqual(provider.api_url, "http://localhost:8080/v1")
        self.assertEqual(provider.api_key, "test-key")
        self.assertEqual(provider.model_name, "test-model")

    def test_llm_provider_complete(self):
        provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")

        def mock_urlopen(req, timeout=None):
            self.assertEqual(req.full_url, "http://localhost:8080/v1/chat/completions")
            self.assertEqual(req.get_header("Authorization"), "Bearer test-key")
            data = json.loads(req.data.decode("utf-8"))
            self.assertEqual(data["model"], "test-model")
            self.assertEqual(len(data["messages"]), 2)

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

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = provider.summarize("This is a long text that needs summarization.")
            self.assertEqual(result, "This is a summarized text.")

    def test_llm_provider_worker(self):
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

        results = []
        worker = LLMWorker(provider.api_url, provider.api_key, provider.model_name, "Test prompt")
        worker.result_ready.connect(results.append)

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            worker.run()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "Worker test result")

    def test_llm_provider_worker_error(self):
        provider = LLMProvider("http://localhost:8080/v1", "test-key", "test-model")

        def mock_urlopen_error(req, timeout=None):
            raise Exception("Mock error")

        errors = []
        worker = LLMWorker(provider.api_url, provider.api_key, provider.model_name, "Test prompt")
        worker.error_occurred.connect(errors.append)

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_error):
            worker.run()

        self.assertEqual(len(errors), 1)
        self.assertIn("Mock error", errors[0])


if __name__ == "__main__":
    unittest.main()
