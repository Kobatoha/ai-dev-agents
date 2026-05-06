from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
import asyncio
from datetime import datetime
import aiofiles

@dataclass
class Message:
    """Сообщение между агентами"""
    sender: str
    receiver: str
    task_id: str
    content: str
    msg_type: str  # "task", "code", "review", "approval", "question"
    timestamp: str
    metadata: Dict[str, Any]

class BaseAgent(ABC):
    """Базовый класс для всех агентов"""
    
    def __init__(self, name: str, role: str, model: str, config: Dict):
        self.name = name
        self.role = role
        self.model = model
        self.config = config
        self.message_queue = asyncio.Queue()
        self.context: Dict[str, Any] = {}
        self.ollama_client = None  # Будет установлен позже
        
    @abstractmethod
    async def process_message(self, message: Message) -> Optional[Message]:
        """Обработка входящего сообщения"""
        pass
    
    async def think(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Вызов Ollama API"""
        # Будет реализован в ollama_client
        pass
    
    async def send_message(self, receiver: str, task_id: str, 
                          content: str, msg_type: str, **metadata) -> Message:
        """Отправка сообщения другому агенту"""
        message = Message(
            sender=self.name,
            receiver=receiver,
            task_id=task_id,
            content=content,
            msg_type=msg_type,
            timestamp=datetime.now().isoformat(),
            metadata=metadata
        )
        return message
    

    async def think(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Вызов Ollama API"""
        if not self.ollama_client:
            raise ValueError("OllamaClient не установлен!")
        
        print(f"🤔 {self.name} думает...")
        response = await self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            system_prompt=system_prompt or getattr(self, 'system_prompt', None),
            temperature=self.config.get('temperature', 0.3),
            max_tokens=self.config.get('max_tokens', 2048)
        )
        print(f"💡 {self.name} получил ответ ({len(response)} символов)")
        return response