from base_prompt import BasePrompt


class DeveloperPrompts(BasePrompt):
    """Промпты для Senior Developer"""

    def system(self) -> str:
        return """
            Ты - Senior Python Developer.
            Пиши ТОЛЬКО код на Python 3.12.
            Используй async/await, FastAPI, Pydantic v2.
            
            ВАЖНО: 
            - Если файл существует - ДОПОЛНЯЙ его, не перезаписывай полностью
            - Сохраняй существующий код и добавляй новый
            - Каждый файл начинай с комментария # file: path/to/file.py
            - Не добавляй markdown-объяснения в код, только комментарии в коде
        """

    @staticmethod
    def implement_feature(task_description: str, target_files: list,
                          existing_code: str, mode: str) -> str:
        """Промпт для реализации фичи"""
        return f"""
            Задача: {task_description[:300]}

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

    @staticmethod
    def fix_code(feedback: str, required_changes: list) -> str:
        """Промпт для исправления кода"""
        changes_text = '\n'.join(f"- {c}" for c in required_changes)
        return f"""
            Нужно исправить код по замечаниям ревьюера:
            
            Замечания: {feedback}
            Требуемые изменения:
            {changes_text}
            
            Внеси исправления и верни обновленный код.
        """
