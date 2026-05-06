import subprocess
from pathlib import Path
from datetime import datetime


class GitManager:
    """Управляет версионированием кода через Git в КОРНЕВОМ репозитории"""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        # Ищем корень проекта (где находится agents/, core/, main.py)
        self.root_path = self._find_project_root()
        self.setup_git()

    def _find_project_root(self) -> Path:
        """Находит корень проекта (где main.py)"""
        current = self.workspace
        while current != current.parent:
            if (current / 'main.py').exists() or (current / 'config.yaml').exists():
                print(f"🔍 [Git] Project root found: {current}")
                return current
            current = current.parent

        print(f"⚠️ [Git] Project root not found, using: {self.workspace}")
        return self.workspace

    def setup_git(self):
        """Инициализация Git в корне проекта"""
        if not (self.root_path / '.git').exists():
            try:
                subprocess.run(['git', 'init'], cwd=self.root_path, check=True, capture_output=True)

                # Настройка Git
                subprocess.run(['git', 'config', '--local', 'core.quotepath', 'false'], cwd=self.root_path)
                subprocess.run(['git', 'config', '--local', 'i18n.commitEncoding', 'utf-8'], cwd=self.root_path)

                # Создаем .gitignore
                gitignore = self.root_path / '.gitignore'
                if not gitignore.exists():
                    gitignore.write_text("""
__pycache__/
*.pyc
.pytest_cache/
*.result.txt
venv/
.env
logs/
tasks/
workspace/pet_game/reports/
""")

                # Первый коммит
                subprocess.run(['git', 'add', '.'], cwd=self.root_path, check=True, capture_output=True)
                subprocess.run(
                    ['git', 'commit', '-m', 'Initial commit - AI dev team project'],
                    cwd=self.root_path, check=True, capture_output=True
                )

                print(f"📦 Git initialized in {self.root_path}")
            except Exception as e:
                print(f"⚠️ Git init error: {e}")

    def commit_changes(self, message: str, task_id: str, agent_name: str = "unknown"):
        """
        Коммитит изменения в КОРНЕВОЙ репозиторий
        message - описание на русском
        agent_name - ник агента (senior_dev, reviewer)
        """
        try:
            # Добавляем только файлы из workspace/pet_game (кроме reports)
            workspace_relative = self.workspace.relative_to(self.root_path)

            # Добавляем файлы
            subprocess.run(
                ['git', 'add', str(workspace_relative)],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            # Также добавляем конфиги если изменились
            subprocess.run(
                ['git', 'add', 'config.yaml', '.gitignore'],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            # Проверяем есть ли изменения
            status = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            if not status.stdout.strip():
                print(f"📝 [Git] No changes to commit")
                return False

            # Формируем сообщение на английском
            short_task_id = task_id.split('_')[-1][-6:] if '_' in task_id else task_id[:6]
            message_en = self._to_english(message)
            commit_msg = f"[task_{short_task_id}] {message_en[:80]} | by {agent_name}"

            # Показываем что будет закоммичено
            print(f"📝 [Git] Files to commit:")
            for line in status.stdout.strip().split('\n')[:5]:
                print(f"   {line}")

            # Коммитим
            result = subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✅ [Git] Commit by {agent_name}: {commit_msg}")
                return True
            else:
                print(f"❌ [Git] Commit error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ [Git] Error: {e}")
            return False

    def _to_english(self, message: str) -> str:
        """Переводит описание задачи на английский"""
        # Простой маппинг частых фраз
        translations = {
            'Создать': 'Create',
            'создать': 'create',
            'Добавить': 'Add',
            'добавить': 'add',
            'Исправить': 'Fix',
            'исправить': 'fix',
            'Обновить': 'Update',
            'обновить': 'update',
            'файл': 'file',
            'функцию': 'function',
            'функция': 'function',
            'модель': 'model',
            'эндпоинт': 'endpoint',
            'питомца': 'pet',
            'питомец': 'pet',
            'код': 'code',
            'тесты': 'tests',
            'тест': 'test',
            'приложения': 'app',
            'структуру': 'structure',
            'базовую': 'basic',
            'новый': 'new',
            'расчета': 'calculation',
            'уровня': 'level',
        }

        result = message
        for ru, en in translations.items():
            result = result.replace(ru, en)

        # Если осталось много русского - используем общее описание
        russian_chars = sum(1 for c in result if 'А' <= c <= 'я' or c in 'ёЁ')
        if russian_chars > len(result) * 0.3:
            # Извлекаем ключевые слова
            if 'main.py' in result:
                return 'Update main.py'
            elif 'models.py' in result:
                return 'Update models'
            elif 'test' in result.lower():
                return 'Add tests'
            else:
                return 'Code update'

        return result

    def get_last_commits(self, count: int = 5) -> list:
        """Получает последние коммиты"""
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', f'-{count}'],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )
            return [c for c in result.stdout.strip().split('\n') if c]
        except:
            return []


    def _find_project_root(self) -> Path:
        """Находит корень проекта (где main.py)"""
        current = self.workspace
        while current != current.parent:
            if (current / 'main.py').exists() or (current / 'config.yaml').exists():
                print(f"🔍 [Git] Project root found: {current}")
                return current
            current = current.parent

        print(f"⚠️ [Git] Project root not found, using: {self.workspace}")
        return self.workspace