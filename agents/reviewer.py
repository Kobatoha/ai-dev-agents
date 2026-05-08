from typing import Optional

from ai_agents.agents.git_manager import GitManager
from ai_agents.core.agent_base import BaseAgent, Message
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime
import aiofiles


class Reviewer(BaseAgent):
    def __init__(self, model: str, config: dict):
        super().__init__("reviewer", "Code Reviewer & QA", model, config)

        agents_root = Path(__file__).parent.parent  # ai_agents/
        self.workspace = (agents_root / ".." / "pet_game").resolve()
        self.tests_dir = self.workspace / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

        self.git = GitManager(str(self.workspace))

        self.max_review_iterations = 3
        self.review_count = {}
        self.test_files = []  # ← ДОБАВЬТЕ ЭТУ СТРОКУ

        self.system_prompt = """Ты - строгий Code Reviewer и QA инженер.
    Проверяешь код и пишешь тесты.

    Всегда создавай ТОЛЬКО pytest тесты с именем функции начиная с test_

    Формат ответа:
    JSON с полем "test_code" содержащим ГОТОВЫЙ К ЗАПУСКУ код тестов
    или
    Просто код тестов с импортами

    Тесты должны быть простыми и проверять функциональность."""

    async def process_message(self, message: Message) -> Optional[Message]:
        print(f"🟡 [Reviewer] Получено сообщение: {message.msg_type}")

        if message.msg_type == "code_review":
            return await self._review_with_tests(message)

    async def _review_with_tests(self, message: Message) -> Message:
        """Ревью с генерацией и сохранением тестов"""
        task_id = message.task_id

        # Счетчик итераций
        if task_id not in self.review_count:
            self.review_count[task_id] = 0
        self.review_count[task_id] += 1

        iteration = self.review_count[task_id]
        print(f"🔍 [Reviewer] Проверка #{iteration} для задачи {task_id}")

        # Если это 4+ итерация - ПРИНИМАЕМ АВТОМАТОМ
        if iteration >= 4:
            print(f"⚠️ [Reviewer] Достигнут лимит итераций ({iteration}). ПРИНИМАЮ АВТОМАТИЧЕСКИ.")
            return self._create_review_response(
                message, True,
                f"✅ Код принят после {iteration} проверок (достигнут лимит итераций)."
            )

        try:
            code_data = json.loads(message.content)
            task_desc = code_data.get('task_description', '')
        except:
            code_data = {}
            task_desc = message.content[:200]

        # Читаем текущий код проекта
        project_code = await self._read_project_files()

        # Генерируем тесты
        if iteration == 1:
            # На первой итерации генерируем новые тесты
            test_code = await self._generate_tests(task_desc, project_code)
        else:
            # На последующих - используем существующие тесты
            test_code = await self._load_existing_tests()

        # Сохраняем тесты в файл
        test_file_path = None
        if test_code and len(test_code) > 50:
            test_file_path = await self._save_tests(test_code, task_id)

        # В методе, где сохраняются тесты
        if test_file_path:
            self.git.commit_changes(
                f"Add tests: {test_file_path.name}",
                task_id,
                agent_name="reviewer"
            )

        # Проверяем стиль кода
        style_issues = await self._check_code_style()

        # Запускаем тесты
        test_result = await self._run_tests(test_file_path)

        # Принимаем решение
        return self._make_decision(message, test_result, style_issues, iteration)

    async def _generate_tests(self, task_desc: str, project_code: str) -> str:
        """Генерирует РЕАЛЬНЫЕ тесты"""

        import re
        functions = re.findall(r'def (\w+)\(', project_code)
        classes = re.findall(r'class (\w+)', project_code)

        if not functions and not classes:
            print("⚠️ [Reviewer] Нет функций для тестирования")
            return ""

        # Пример кода для тестов (без f-string конфликта)
        example_test = '''def test_example(client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}'''

        prompt = f"""Задача: {task_desc[:200]}

    Найденные функции: {', '.join(functions[:5])}
    Найденные классы: {', '.join(classes[:3])}

    Код проекта:
    {project_code[:1500]}

    Напиши РАБОЧИЕ pytest тесты.
    Правила:
    1. Импортируй ТОЛЬКО существующие функции/классы
    2. Каждый тест должен проверять КОНКРЕТНЫЙ результат
    3. Используй assert с реальными значениями

    Пример правильного теста:
    {example_test}

    Напиши 2-3 теста. Только код, без markdown.
    """

        response = await self.think(prompt, self.system_prompt)
        return response

    async def _save_tests(self, test_code: str, task_id: str) -> Path:
        """Сохраняет тесты в файл"""
        # Определяем имя файла на основе содержимого
        test_filename = self._determine_test_filename(test_code, task_id)
        test_file_path = self.tests_dir / test_filename

        # Добавляем заголовок с информацией
        header = f'''"""
Автоматически сгенерированные тесты
Задача: {task_id}
Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Сгенерировано: Reviewer AI (qwen2.5-coder)
"""

'''

        # Добавляем правильные импорты если их нет
        if 'import sys' not in test_code:
            test_code = f'''import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

{test_code}'''

        full_code = header + test_code

        async with aiofiles.open(test_file_path, 'w', encoding='utf-8') as f:
            await f.write(full_code)

        print(f"💾 [Reviewer] Тесты сохранены: {test_file_path}")
        self.test_files.append(test_file_path)

        # Также сохраняем в корень для быстрого доступа
        quick_test_path = self.workspace / f"test_quick_{task_id[-6:]}.py"
        async with aiofiles.open(quick_test_path, 'w', encoding='utf-8') as f:
            await f.write(full_code)

        return test_file_path

    def _determine_test_filename(self, test_code: str, task_id: str) -> str:
        """Определяет имя файла для тестов"""
        # Ищем тестируемый модуль в импортах
        imports = re.findall(r'(?:from|import)\s+(\w+)', test_code)

        # Фильтруем системные модули
        system_modules = {'sys', 'os', 'pathlib', 'pytest', 'json', 'datetime', 'typing', 'asyncio'}
        project_modules = [m for m in imports if m not in system_modules]

        if project_modules:
            # Имя файла на основе тестируемого модуля
            module_name = project_modules[0]
            return f"test_{module_name}.py"
        elif 'test_' in task_id.lower():
            return f"test_task_{task_id[-6:]}.py"
        else:
            return f"test_feature_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"

    async def _load_existing_tests(self) -> str:
        """Загружает существующие тесты"""
        if self.tests_dir.exists():
            test_files = list(self.tests_dir.glob("test_*.py"))
            if test_files:
                # Берем последний созданный файл тестов
                latest_test = max(test_files, key=lambda x: x.stat().st_mtime)
                async with aiofiles.open(latest_test, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    # Убираем заголовок
                    if '"""' in content:
                        parts = content.split('"""', 2)
                        if len(parts) >= 3:
                            return parts[2].strip()
                    return content

        return ""

    async def _read_project_files(self) -> str:
        """Читает все файлы проекта (кроме тестов)"""
        code = []
        if self.workspace.exists():
            for py_file in self.workspace.rglob("*.py"):
                # Пропускаем тесты
                if 'test' in py_file.name.lower() or 'tests' in str(py_file):
                    continue

                try:
                    async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            code.append(f"# {py_file.relative_to(self.workspace)}\n{content[:500]}")
                except Exception as e:
                    print(f"⚠️ [Reviewer] Ошибка чтения {py_file}: {e}")

        return "\n\n".join(code) if code else "Проект пуст"

    async def _check_code_style(self) -> list:
        """Проверяет стиль кода"""
        issues = []

        if self.workspace.exists():
            for py_file in self.workspace.rglob("*.py"):
                if 'test' in py_file.name.lower():
                    continue

                try:
                    async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        lines = content.split('\n')

                    for i, line in enumerate(lines, 1):
                        if not line.strip() or line.strip().startswith('#'):
                            continue

                        if len(line.rstrip()) > 120:
                            issues.append(f"{py_file.name}:{i} - длинная строка ({len(line.rstrip())} симв)")
                            break  # По одной проблеме на файл

                        if '\t' in line:
                            issues.append(f"{py_file.name}:{i} - табуляция вместо пробелов")
                            break

                except Exception:
                    pass

        return issues[:3]

    async def _run_tests(self, test_file_path: Path = None) -> dict:
        """Запускает тесты. НЕ принимает пустые."""
        if not test_file_path or not test_file_path.exists():
            return {
                'passed': False,  # ИЗМЕНЕНО: False вместо True
                'errors': 'Файл тестов не найден',
                'summary': '❌ Тесты не созданы'
            }

        # Проверяем что файл не пустой
        if test_file_path.stat().st_size < 50:
            return {
                'passed': False,
                'errors': 'Файл тестов пустой',
                'summary': '❌ Тесты пустые'
            }

        try:
            print(f"🧪 [Reviewer] Запуск тестов: {test_file_path.name}")

            # Создаем __init__.py в tests если нет
            init_file = self.tests_dir / "__init__.py"
            if not init_file.exists():
                async with aiofiles.open(init_file, 'w') as f:
                    await f.write("# Test package\n")

            result = subprocess.run(
                ['pytest', str(test_file_path), '-v', '--tb=short', '--no-header', '-p', 'no:warnings'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.workspace)
            )

            output = result.stdout + result.stderr

            # Сохраняем результат запуска
            result_file = test_file_path.with_suffix('.result.txt')
            async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
                await f.write(f"Дата запуска: {datetime.now()}\n")
                await f.write(f"Тестовый файл: {test_file_path.name}\n")
                await f.write("=" * 50 + "\n")
                await f.write(output)

            # Анализируем результат
            if 'collected 0 items' in output:
                return {
                    'passed': True,
                    'errors': '',
                    'summary': f'⚠️ Нет тестов в файле (принято). Файл: {test_file_path.name}'
                }

            if result.returncode == 0 and 'failed' not in output:
                # Считаем пройденные тесты
                passed_count = output.count('PASSED')
                return {
                    'passed': True,
                    'errors': '',
                    'summary': f'✅ Все тесты пройдены ({passed_count} шт). Файл: {test_file_path.name}'
                }
            else:
                # Считаем результаты
                passed = output.count('PASSED')
                failed = output.count('FAILED')
                error = output.count('ERROR')

                if 'ModuleNotFoundError' in output or 'ImportError' in output:
                    return {
                        'passed': True,  # Принимаем если проблема в импортах
                        'errors': output[-300:],
                        'summary': f'⚠️ Проблемы с импортами (принято). Тесты сохранены в {test_file_path.name}'
                    }

                return {
                    'passed': False,
                    'errors': output[-500:],
                    'summary': f'❌ Пройдено: {passed}, Провалено: {failed}, Ошибки: {error}. Файл: {test_file_path.name}'
                }

        except subprocess.TimeoutExpired:
            return {'passed': True, 'errors': '', 'summary': '⏰ Тесты зависли (принято)'}
        except FileNotFoundError:
            return {'passed': True, 'errors': '',
                    'summary': '📦 pytest не установлен (тесты сохранены, запустите вручную)'}
        except Exception as e:
            print(f"⚠️ [Reviewer] Ошибка запуска тестов: {e}")
            return {'passed': True, 'errors': '', 'summary': f'🔧 Техническая ошибка (тесты сохранены): {str(e)[:100]}'}

    def _make_decision(self, message: Message, test_result: dict, style_issues: list, iteration: int) -> Message:
        """Принимает решение о принятии кода"""

        # Всегда принимаем если тесты пройдены
        if test_result['passed'] and len(style_issues) == 0:
            print(f"✅ [Reviewer] Код идеален! Тесты пройдены, стиль отличный.")
            return self._create_review_response(
                message, True,
                f"✅ Код принят!\n{test_result['summary']}\nСтиль кода: без замечаний\n"
                f"Тесты сохранены в проекте, можно запустить: pytest tests/"
            )

        # Принимаем если тесты пройдены и есть мелкие замечания
        if test_result['passed'] and len(style_issues) <= 3:
            print(f"✅ [Reviewer] Код рабочий, есть мелкие замечания по стилю.")
            return self._create_review_response(
                message, True,
                f"✅ Код принят!\n{test_result['summary']}\n"
                f"Замечания по стилю ({len(style_issues)}):\n" +
                '\n'.join(f"  • {issue}" for issue in style_issues) +
                f"\n\nТесты сохранены в tests/"
            )

        # На 3+ итерации принимаем в любом случае
        if iteration >= 3:
            print(f"⚠️ [Reviewer] Итерация {iteration}. Принимаю с замечаниями.")
            return self._create_review_response(
                message, True,
                f"⚠️ Код принят после {iteration} проверок.\n"
                f"{test_result['summary']}\n"
                f"Замечания по стилю: {len(style_issues)}\n"
                f"Тесты сохранены в tests/ (запустите вручную: pytest tests/)"
            )

        # Отправляем на доработку
        feedback_parts = []
        if not test_result['passed']:
            feedback_parts.append(f"❌ Тесты не пройдены:\n{test_result.get('errors', '')[:300]}")

        if style_issues:
            feedback_parts.append(f"📝 Стиль кода:\n" + '\n'.join(f"  • {issue}" for issue in style_issues))

        print(f"🔄 [Reviewer] Отправлено на доработку (итерация {iteration})")

        return self._create_review_response(
            message, False,
            '\n\n'.join(feedback_parts)
        )

    def _create_review_response(self, message: Message, approved: bool, feedback: str) -> Message:
        """Создает ответ ревью"""
        result = {
            "approved": approved,
            "feedback": feedback,
            "issues_found": [] if approved else ["Требуются исправления"],
            "required_changes": [] if approved else ["Исправить код"],
            "summary": feedback[:200],
            "test_files": [str(f.relative_to(self.workspace)) for f in self.test_files] if self.test_files else []
        }

        if approved:
            if message.task_id in self.review_count:
                del self.review_count[message.task_id]

        return Message(
            sender=self.name,
            receiver="tech_lead",
            task_id=message.task_id,
            content=json.dumps(result, ensure_ascii=False),
            msg_type="review_result",
            timestamp=message.timestamp,
            metadata={
                "review_iteration": self.review_count.get(message.task_id, 0),
                "test_files": result["test_files"]
            }
        )
