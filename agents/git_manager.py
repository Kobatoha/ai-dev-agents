import subprocess
from pathlib import Path
from datetime import datetime


class GitManager:
    """Управляет версионированием кода через Git в КОРНЕВОМ репозитории"""
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        # Корень ПРОЕКТА (не агентов!)
        self.root_path = self.workspace.parent

        # Проверяем что Git есть в проекте
        if not (self.root_path / '.git').exists():
            print(f"❌ [Git] No Git repository in project: {self.root_path}")
            print(f"   Please run: git init && git add . && git commit")

        print(f"📦 [Git] Project root: {self.root_path}")
        print(f"📦 [Git] Workspace: {self.workspace}")

    def commit_changes(self, message: str, task_id: str, agent_name: str = "unknown"):
        try:
            # Добавляем файлы ПРОЕКТА (не агентов!)
            project_files = self.workspace.relative_to(self.root_path)

            print(f"📦 [Git] Adding project files: {project_files}")

            # Добавляем
            subprocess.run(
                ['git', 'add', str(project_files)],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            # Статус
            status = subprocess.run(
                ['git', 'status', '--porcelain', str(project_files)],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            if not status.stdout.strip():
                print(f"📝 [Git] No changes to commit")
                return False

            # Коммит
            short_id = task_id[-6:] if '_' in task_id else task_id[:6]
            commit_msg = f"[task_{short_id}] {self._to_english(message)[:80]} | by {agent_name}"

            result = subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✅ [Git] Committed to project: {commit_msg}")

                # Автопуш в проект
                self._auto_push()

                return True
            else:
                print(f"❌ [Git] Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ [Git] Exception: {e}")
            return False

    @staticmethod
    def _to_english(message: str) -> str:
        """Переводит описание на английский"""
        translations = {
            'Создать': 'Create', 'создать': 'create',
            'Добавить': 'Add', 'добавить': 'add',
            'Исправить': 'Fix', 'исправить': 'fix',
            'Обновить': 'Update', 'обновить': 'update',
            'файл': 'file', 'модель': 'model',
            'эндпоинт': 'endpoint', 'питомца': 'pet',
            'код': 'code', 'тесты': 'tests',
            'структуру': 'structure', 'базовую': 'basic',
            'новый': 'new', 'уровня': 'level',
        }
        result = message
        for ru, en in translations.items():
            result = result.replace(ru, en)

        # Если осталось много русского
        russian = sum(1 for c in result if 'А' <= c <= 'я')
        if russian > len(result) * 0.3:
            return 'Code update'  # Простое сообщение
        return result[:80]


    def _auto_push(self):
        """Автоматический пуш в origin"""
        try:
            # Проверяем есть ли remote
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.root_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                print(f"📤 [Git] Pushing to origin...")
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'master'],
                    cwd=self.root_path,
                    capture_output=True,
                    text=True
                )

                if push_result.returncode == 0:
                    print(f"✅ [Git] Pushed successfully!")
                else:
                    print(f"⚠️ [Git] Push failed: {push_result.stderr[:200]}")
            else:
                print(f"ℹ️ [Git] No remote 'origin' configured, skipping push")

        except Exception as e:
            print(f"⚠️ [Git] Auto-push error: {e}")
