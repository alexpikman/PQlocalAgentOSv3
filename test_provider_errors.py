"""
Тест обработки 404 ошибки для облачных провайдеров
"""
import sys
sys.path.insert(0, '.')

from server import provider_models
from io import BytesIO
import urllib.request

# Создаем mock 404 ошибку
class MockError:
    def __init__(self):
        self.code = 404
        self.reason = 'Model not found'
    
    def read(self):
        return b'{\"error\":\"Unknown model or unsupported format\"}'

def test_cloud_provider_404():
    """
    Тестируем обработку ошибки для облачных провайдеров
    (Anthropic, Gemini, Ollama)
    """
    # Используем provider с openai форматом и моделью, которая не существует
    mock_provider = {
        'id': 'test-provider',
        'kind': 'cloud',
        'format': 'openai',
        'base_url': 'http://example.com/api',
        'api_key': 'test-key'
    }
    
    # Тестируем provider_models для получения списка моделей (вызывает urlopen)
    try:
        models = provider_models(mock_provider)
        print(f"provider_models вернул {len(models)} моделей")
        if not models:
            print("  ✓ Хорошо - модели не найдены (возможно, 404)")
    except urllib.error.HTTPError as e:
        print(f"HTTP 404 ошибка при получении списка моделей!")
        print(f"  Код: {e.code}")
        print(f"  Причина: {e.reason}")
        
        # Проверим обработку ошибки в _cloud_provider_error
        from server import _cloud_provider_error
        
        msg = _cloud_provider_error(e)
        print(f"\n_cloud_provider_error результат:")
        print(f"  Сообщение: {msg}")
        
        if '404' in str(msg).lower() or e.reason == 'Not Found':
            print("  ⚠ Ошибка содержит код 404 - нужно проверить обработку")
    
if __name__ == '__main__':
    test_cloud_provider_404()