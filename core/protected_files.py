from pathlib import Path
from typing import List


class ProtectedFiles:
    """Управляет защищенными от изменений файлами"""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.protected_file = self.workspace / ".protected"
        self.protected_list: List[str] = []
        self.load_protected_files()

    def load_protected_files(self):
        """Загружает список защищенных файлов"""
        if self.protected_file.exists():
            with open(self.protected_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.protected_list.append(line)

    def is_protected(self, file_path: str) -> bool:
        """Проверяет, защищен ли файл"""
        return file_path in self.protected_list

    def add_protected(self, file_path: str):
        """Добавляет файл в защищенную зону"""
        if file_path not in self.protected_list:
            self.protected_list.append(file_path)
            with open(self.protected_file, 'a') as f:
                f.write(f"{file_path}\n")

    def remove_protected(self, file_path: str):
        """Удаляет файл из защищенной зоны"""
        if file_path in self.protected_list:
            self.protected_list.remove(file_path)
            # Перезаписываем файл
            with open(self.protected_file, 'w') as f:
                for pf in self.protected_list:
                    f.write(f"{pf}\n")
