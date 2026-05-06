from core.agent_base import BaseAgent, Message
from core.task_manager import TaskManager
from typing import Optional, List
import json
from pathlib import Path
import aiofiles


class TechLead(BaseAgent):
    def __init__(self, model: str, config: dict, task_manager: TaskManager):
        super().__init__("tech_lead", "Tech Lead & Architect", model, config)
        self.task_manager = task_manager
        self.workspace = Path("./workspace/pet_game")
        self.system_prompt = """Ты - Технический Лидер проекта "Игра с питомцем" (FastAPI).
Твои обязанности:
1. Анализировать запросы пользователя
2. Проверять, не реализована ли уже задача в проекте
3. Разбивать новые задачи на подзадачи
4. После выполнения задачи предлагать следующие шаги

ВСЕГДА отвечай в формате JSON:
{
  "analysis": "Анализ запроса",
  "already_exists": true/false,
  "existing_files": ["файл1.py"],
  "main_task": "Название",
  "subtasks": [
    {
      "title": "Подзадача",
      "description": "Что сделать",
      "file_path": "файл.py",
      "priority": 1
    }
  ],
  "next_steps": ["Шаг 1", "Шаг 2"]
}"""

    async def process_message(self, message: Message) -> Optional[Message]:
        if message.msg_type == "user_request":
            return await self._analyze_and_plan(message)
        elif message.msg_type == "review_result":
            return await self._handle_review(message)

    async def _analyze_and_plan(self, message: Message) -> Optional[Message]:
        print(f"📋 [TechLead] Анализ запроса и контекста проекта...")

        # Читаем текущее состояние проекта
        project_state = await self._get_project_state_detailed()

        # Список выполненных задач
        completed_tasks = await self._get_completed_tasks()

        prompt = f"""
        Запрос: {message.content[:200]}

        СОСТОЯНИЕ ПРОЕКТА:
        Файлов: {project_state.get('total_files', 0)}
        Структура: {json.dumps({k: {'size': v['size'], 'classes': v['classes']} for k, v in project_state.get('files', {}).items()}, indent=2)[:1000]}

        ОПРЕДЕЛИ:
        1. Если задача частично реализована - укажи существующие файлы и что нужно ДОПОЛНИТЬ
        2. Если задача новая - укажи что нужно СОЗДАТЬ

        Верни JSON с полем mode: "modify" или "create"
        """

        response = await self.think(prompt, self.system_prompt)

        if not response:
            return self._create_direct_task(message)

        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                plan = json.loads(response[json_start:json_end])

                # Если задача уже существует
                if plan.get("already_exists"):
                    print(f"✅ [TechLead] Эта задача уже реализована!")
                    return Message(
                        sender=self.name,
                        receiver="user",
                        task_id=message.task_id,
                        content=f"✅ Эта задача уже реализована в проекте!\n\n"
                                f"Существующие файлы: {plan.get('existing_files', [])}\n\n"
                                f"Предлагаю следующие шаги:\n" +
                                "\n".join(f"• {step}" for step in plan.get('next_steps', [])),
                        msg_type="user_notification",
                        timestamp=message.timestamp,
                        metadata={"status": "already_exists"}
                    )

                # Создаем задачу
                main_task = self.task_manager.create_task(
                    plan.get("main_task", "Задача"),
                    message.content
                )

                # Сохраняем следующие шаги
                main_task.result = json.dumps({
                    "next_steps": plan.get("next_steps", []),
                    "analysis": plan.get("analysis", "")
                })

                await self.task_manager.save_task(main_task)

                print(f"✅ [TechLead] Создан план с {len(plan.get('subtasks', []))} подзадачами")

                if plan.get('next_steps'):
                    print(f"📋 [TechLead] Следующие шаги:")
                    for step in plan['next_steps']:
                        print(f"   • {step}")

                # Отправляем первую подзадачу разработчику
                if plan.get("subtasks"):
                    subtask = plan["subtasks"][0]

                    return Message(
                        sender=self.name,
                        receiver="senior_dev",
                        task_id=main_task.id,
                        content=json.dumps(subtask, ensure_ascii=False),
                        msg_type="coding_task",
                        timestamp=message.timestamp,
                        metadata={
                            "parent_task_id": main_task.id,
                            "total_subtasks": len(plan["subtasks"]),
                            "current_subtask": 1
                        }
                    )
        except Exception as e:
            print(f"⚠️ [TechLead] Ошибка: {e}")
            import traceback
            traceback.print_exc()

        return self._create_direct_task(message)

    async def _get_project_state_detailed(self) -> dict:
        """Детальный анализ состояния проекта"""
        state = {
            'files': {},
            'total_files': 0,
            'imports': [],
            'classes': [],
            'functions': []
        }

        if self.workspace.exists():
            for py_file in self.workspace.rglob("*.py"):
                if 'test' in py_file.name.lower():
                    continue

                try:
                    async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        lines = content.split('\n')

                    rel_path = str(py_file.relative_to(self.workspace))
                    state['files'][rel_path] = {
                        'size': len(content),
                        'lines': len(lines),
                        'imports': [l for l in lines if l.startswith('import ') or l.startswith('from ')],
                        'classes': [l for l in lines if l.strip().startswith('class ')],
                        'functions': [l for l in lines if l.strip().startswith('def ')]
                    }
                    state['total_files'] += 1

                except Exception as e:
                    print(f"⚠️ [TechLead] Ошибка анализа {py_file}: {e}")

        return state

    async def _get_completed_tasks(self) -> str:
        """Получает список выполненных задач"""
        tasks = []
        if self.task_manager.tasks_path.exists():
            for task_file in self.task_manager.tasks_path.glob("*.json"):
                try:
                    async with aiofiles.open(task_file, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                        if data.get('status') == 'done':
                            tasks.append(f"✅ {data.get('title')} ({data.get('id')})")
                except:
                    pass

        return '\n'.join(tasks[-5:]) if tasks else "Нет выполненных задач"

    def _create_direct_task(self, message: Message) -> Message:
        main_task = self.task_manager.create_task("Задача разработки", message.content)

        return Message(
            sender=self.name,
            receiver="senior_dev",
            task_id=main_task.id,
            content=message.content,
            msg_type="coding_task",
            timestamp=message.timestamp,
            metadata={"parent_task_id": main_task.id}
        )

    async def _handle_review(self, message: Message) -> Optional[Message]:
        print(f"🔍 [TechLead] Проверка ревью...")

        try:
            review_data = json.loads(message.content)
            approved = review_data.get("approved", True)
        except:
            approved = True

        if approved:
            print("✅ [TechLead] Задача одобрена!")

            # Обновляем статус задачи
            task = await self.task_manager.load_task(message.task_id)
            if task:
                task.status = "done"
                task.updated_at = message.timestamp

                # Добавляем следующие шаги
                if task.result:
                    try:
                        next_steps = json.loads(task.result)
                        next_steps_list = next_steps.get('next_steps', [])
                    except:
                        next_steps_list = []
                else:
                    next_steps_list = []

                await self.task_manager.save_task(task)

            # Формируем ответ
            response_text = "✅ Задача выполнена успешно!\n\n"
            response_text += f"📊 Результат ревью: {review_data.get('feedback', 'Код одобрен')}\n\n"

            if next_steps_list:
                response_text += "📋 Предлагаю следующие шаги:\n"
                for i, step in enumerate(next_steps_list, 1):
                    response_text += f"  {i}. {step}\n"

            return Message(
                sender=self.name,
                receiver="user",
                task_id=message.task_id,
                content=response_text,
                msg_type="user_notification",
                timestamp=message.timestamp,
                metadata={
                    "status": "success",
                    "next_steps": next_steps_list
                }
            )
        else:
            return Message(
                sender=self.name,
                receiver="senior_dev",
                task_id=message.task_id,
                content=json.dumps({"feedback": "Нужны правки"}),
                msg_type="fix_request",
                timestamp=message.timestamp,
                metadata={}
            )
