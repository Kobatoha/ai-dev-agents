from typing import Optional

from core.agent_base import BaseAgent, Message
from pathlib import Path
import json
import aiofiles
from datetime import datetime
from agents.git_manager import GitManager
from core.protected_files import ProtectedFiles


class SeniorDev(BaseAgent):
    def __init__(self, model: str, config: dict, workspace_path: str):
        super().__init__("senior_dev", "Senior Python Developer", model, config)
        self.workspace = Path(workspace_path)
        self.workspace.mkdir(parents=True, exist_ok=True)
        # Git в корне проекта
        self.git = GitManager(str(self.workspace))

        self.reports_dir = self.workspace / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        self.nickname = "Veniamin"

        self.system_prompt = """
            Ты - Senior Python Developer.
            Пиши ТОЛЬКО код на Python 3.12.
            Используй async/await, FastAPI, Pydantic v2.
            
            ВАЖНО: 
            - Если файл существует - ДОПОЛНЯЙ его, не перезаписывай полностью
            - Сохраняй существующий код и добавляй новый
            - Каждый файл начинай с комментария # file: path/to/file.py
            - Не добавляй markdown-объяснения в код, только комментарии в коде
        """


    async def process_message(self, message: Message) -> Optional[Message]:
        print(f"🟢 [SeniorDev] Получено сообщение: {message.msg_type}")

        if message.msg_type in ["coding_task", "fix_request"]:
            return await self._implement_feature(message)

    async def _implement_feature(self, message: Message) -> Message:
        print(f"💻 [SeniorDev] Начинаю разработку...")

        try:
            task_data = json.loads(message.content)
        except json.JSONDecodeError:
            task_data = {"description": message.content}

        # Читаем ВЕСЬ существующий код для контекста
        existing_code = await self._read_existing_code()

        # Определяем режим: создание или дополнение
        target_files = task_data.get('file_path', 'main.py')
        if isinstance(target_files, str):
            target_files = [target_files]

        mode = "create" if not any((self.workspace / f).exists() for f in target_files) else "modify"

        prompt = f"""
            Задача: {task_data.get('description', task_data)[:300]}
            
            РЕЖИМ РАБОТЫ: {"Создание новых файлов" if mode == "create" else "ДОПОЛНЕНИЕ существующих файлов"}
            
            Целевые файлы: {', '.join(target_files)}
            
            Существующий код в проекте:
            {existing_code[:3000]}
            
            НАПИШИ ТОЛЬКО НОВЫЙ КОД (без объяснений):
            {"- Создай файлы с нуля" if mode == "create" else "- ДОПОЛНИ существующие файлы новым функционалом"}
            - Каждый файл начинай с: # file: имя_файла.py
            - Не дублируй существующий код
            - Добавляй только новый функционал
        """

        response = await self.think(prompt, self.system_prompt)

        if not response or len(response) < 10:
            print("❌ [SeniorDev] Пустой ответ от модели!")
            return self._create_error_response(message)

        # Сохраняем код (с учетом существующих файлов)
        saved_files = await self._save_code_smart(response, target_files, mode)

        # Создаем отчет о проделанной работе
        report_path = await self._create_report(message.task_id, task_data, saved_files, mode)

        # Делаем коммит
        commit_msg = f"{task_data.get('description', 'Code update')[:70]}"
        self.git.commit_changes(commit_msg, message.task_id, agent_name="senior_dev")
        print(f"🔍 [SeniorDev] Attempting git commit...")
        print(f"   Workspace: {self.workspace}")
        print(f"   Git root: {self.git.root_path}")

        result = self.git.commit_changes(commit_msg, message.task_id, agent_name="senior_dev")
        print(f"   Commit result: {result}")

        print(f"📁 [SeniorDev] Сохранено файлов: {saved_files}")
        print(f"📄 [SeniorDev] Отчет: {report_path}")

        # Отправляем на ревью
        return Message(
            sender=self.name,
            receiver="reviewer",
            task_id=message.task_id,
            content=json.dumps({
                "code": response[:1000],
                "full_code": response,
                "task_description": task_data.get('description', ''),
                "files_changed": saved_files,
                "mode": mode,
                "report_path": str(report_path.relative_to(self.workspace)) if report_path else None
            }),
            msg_type="code_review",
            timestamp=message.timestamp,
            metadata={"parent_task_id": message.metadata.get("parent_task_id")}
        )

    async def _read_existing_code(self) -> str:
        """Читает ВЕСЬ существующий код"""
        code_sections = []

        if self.workspace.exists():
            py_files = sorted(self.workspace.rglob("*.py"))
            for py_file in py_files:
                # Пропускаем тесты и временные файлы
                if 'test' in py_file.name.lower() or py_file.name.startswith('_'):
                    continue

                try:
                    async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            rel_path = py_file.relative_to(self.workspace)
                            code_sections.append(f"=== {rel_path} ===\n{content}")
                except Exception as e:
                    print(f"⚠️ [SeniorDev] Ошибка чтения {py_file}: {e}")

        return "\n\n".join(code_sections) if code_sections else "Файлов пока нет"

    async def _save_code_smart(self, code: str, target_files: list, mode: str) -> list:
        """Умное сохранение кода (создание или дополнение)"""
        saved_files = []

        # Разбиваем код на файлы по маркерам
        file_blocks = self._split_code_blocks(code)
        protected = ProtectedFiles(str(self.workspace))

        for filename, block_content in file_blocks:
            if protected.is_protected(filename):
                print(f"🔒 [SeniorDev] Файл {filename} защищен от изменений! Пропускаю.")
                continue

        for filename, block_content in file_blocks:
            file_path = self.workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "modify" and file_path.exists():
                # Читаем существующий код
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    existing_content = await f.read()

                # Проверяем, не дублируется ли код
                if block_content.strip() not in existing_content:
                    # Дополняем файл
                    new_content = existing_content.rstrip() + "\n\n# === Новый код (добавлен автоматически) ===\n" + block_content
                    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                        await f.write(new_content)

                    print(f"   📝 Дополнен: {file_path} (+{len(block_content)} симв)")
                else:
                    print(f"   ⏭️ Пропущен: {file_path} (код уже существует)")
            else:
                # Создаем новый файл
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(block_content)

                print(f"   ✨ Создан: {file_path} ({len(block_content)} симв)")

            saved_files.append(filename)

        return saved_files

    def _split_code_blocks(self, code: str) -> list:
        """Разделяет код на блоки по файлам"""
        blocks = []
        current_file = "main.py"
        current_lines = []

        for line in code.split('\n'):
            if '# file:' in line.lower():
                # Сохраняем предыдущий блок
                if current_lines:
                    blocks.append((current_file, '\n'.join(current_lines).strip()))

                # Начинаем новый файл
                current_file = line.split('# file:')[-1].strip()
                current_lines = []
            elif not line.startswith('```'):
                current_lines.append(line)

        # Последний блок
        if current_lines:
            blocks.append((current_file, '\n'.join(current_lines).strip()))

        return blocks

    async def _create_report(self, task_id: str, task_data: dict, saved_files: list, mode: str) -> Path:
        """Создает текстовый отчет о проделанной работе"""
        report_path = self.reports_dir / f"report_{task_id[-8:]}.txt"

        report_content = f"""ОТЧЕТ О ВЫПОЛНЕННОЙ РАБОТЕ
{'=' * 50}
Задача ID: {task_id}
Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Режим работы: {mode}

ОПИСАНИЕ ЗАДАЧИ:
{task_data.get('description', 'Нет описания')[:500]}

ИЗМЕНЕННЫЕ ФАЙЛЫ:
{chr(10).join(f'- {f}' for f in saved_files)}

РЕЗУЛЬТАТ:
- Режим: {'Дополнение существующего кода' if mode == 'modify' else 'Создание новых файлов'}
- Всего файлов: {len(saved_files)}

Git: изменения закоммичены
"""

        async with aiofiles.open(report_path, 'w', encoding='utf-8') as f:
            await f.write(report_content)

        return report_path

    def _create_error_response(self, message: Message) -> Message:
        """Создает ответ при ошибке генерации"""
        return Message(
            sender=self.name,
            receiver="reviewer",
            task_id=message.task_id,
            content=json.dumps({"error": "Не удалось сгенерировать код"}),
            msg_type="code_review",
            timestamp=message.timestamp,
            metadata={}
        )
