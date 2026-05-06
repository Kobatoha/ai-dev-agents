import aiohttp
import json
from typing import Optional
import asyncio

class OllamaClient:
    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    async def generate(self, 
                      model: str, 
                      prompt: str, 
                      system_prompt: Optional[str] = None,
                      temperature: float = 0.3,
                      max_tokens: int = 2048) -> str:
        """Асинхронный вызов Ollama API"""
        
        # Формируем промпт правильно
        full_prompt = ""
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = f"User: {prompt}\n\nAssistant:"
        
        print(f"🔍 Отправка запроса к {model}...")
        print(f"📝 Длина промпта: {len(full_prompt)} символов")
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ HTTP {response.status}: {error_text[:200]}")
                        return f"ERROR: HTTP {response.status}"
                    
                    result = await response.json()
                    response_text = result.get("response", "")
                    
                    if not response_text:
                        print(f"⚠️ Пустой ответ от модели. Полный ответ API: {json.dumps(result, indent=2)[:500]}")
                    
                    return response_text
                    
            except asyncio.TimeoutError:
                print(f"❌ Таймаут при запросе к {model}")
                return "ERROR: Timeout"
            except Exception as e:
                print(f"❌ Ошибка вызова Ollama: {e}")
                return f"ERROR: {str(e)}"
