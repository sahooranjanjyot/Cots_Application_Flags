import pytest
import pika
from main import app
from security import verify_api_key

class MockChannel:
    def queue_declare(self, *args, **kwargs):
        pass
    def basic_publish(self, *args, **kwargs):
        pass

class MockConnection:
    def channel(self):
        return MockChannel()
    def close(self):
        pass

@pytest.fixture(autouse=True)
def bypass_api_key():
    app.dependency_overrides[verify_api_key] = lambda: True
    yield
    app.dependency_overrides = {}

@pytest.fixture(autouse=True)
def mock_rabbitmq(monkeypatch):
    def mock_blocking_connection(*args, **kwargs):
        return MockConnection()
    monkeypatch.setattr(pika, "BlockingConnection", mock_blocking_connection)
