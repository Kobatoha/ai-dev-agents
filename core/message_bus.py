import asyncio
from typing import Dict
from core.agent_base import BaseAgent, Message
from datetime import datetime
import json
from pathlib import Path
import aiofiles

class MessageBus:
    """Шина сообщений для общения агентов"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.message_queue = asyncio.Queue()
        self.running = False
        self.user_messages = []  # Для ответов пользователю
        # Инициализируем logs_dir сразу
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
    
    def register_agent(self, agent: BaseAgent):
        """Регистрация агента в системе"""
        self.agents[agent.name] = agent
        print(f"✅ Агент {agent.name} ({agent.role}) зарегистрирован")

    async def _write_log(self, message: Message):
        """Прямая запись лога в файл"""
        try:
            log_file = self.logs_dir / f"team_log_{datetime.now().strftime('%Y%m%d')}.jsonl"

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "from": message.sender,
                "to": message.receiver,
                "type": message.msg_type,
                "task_id": message.task_id,
                "content": message.content[:500] if message.content else "",
                "metadata": str(message.metadata)
            }

            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            print(f"📝 Лог записан в {log_file.name}")

        except Exception as e:
            print(f"❌ Ошибка записи лога: {e}")

    async def send_message(self, message: Message):
        """Отправка сообщения агенту"""
        if message.receiver == "user":
            print(f"\n📬 Сообщение для пользователя: {message.content[:200]}...")
            self.user_messages.append(message)
            return

        if message.receiver in self.agents:
            print(f"📨 {message.sender} -> {message.receiver}: {message.msg_type}")
            agent = self.agents[message.receiver]

            try:
                response = await agent.process_message(message)

                if response:
                    print(f"📤 {message.receiver} -> {response.receiver}: {response.msg_type}")
                    await self.message_queue.put(response)
                else:
                    print(f"⚠️ {message.receiver} не вернул ответ")

            except Exception as e:
                print(f"❌ Ошибка обработки сообщения агентом {message.receiver}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ Агент {message.receiver} не найден")
    
    async def start(self):
        """Запуск обработки сообщений"""
        self.running = True
        print("🔄 Шина сообщений запущена")
        
        while self.running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=1.0
                )
                await self.send_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"❌ Ошибка шины сообщений: {e}")
    
    async def submit_user_request(self, request: str):
        """Отправка запроса пользователя"""
        from datetime import datetime
        
        message = Message(
            sender="user",
            receiver="tech_lead",
            task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            content=request,
            msg_type="user_request",
            timestamp=datetime.now().isoformat(),
            metadata={}
        )
        await self.message_queue.put(message)
    