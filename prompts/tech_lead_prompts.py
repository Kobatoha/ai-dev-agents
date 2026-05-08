from base_prompt import BasePrompt


class TechLeadPrompts(BasePrompt):
    """Промпты для TechLead"""

    def system(self) -> str:
        return """
            Ты - Технический Лидер проекта "Игра с питомцем" (FastAPI).
            Твои обязанности:
            1. Анализировать запросы пользователяц
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
            }
        """

    def analyze_and_plan(self, user_request: str, project_state: str, completed_tasks: str) -> str:
        """Промпт для анализа запроса и планирования"""
        prompt = f"""
            Запрос пользователя: {user_request}
            
            ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА:
            {project_state}
            
            ВЫПОЛНЕННЫЕ ЗАДАЧИ:
            {completed_tasks}
            
            Проверь, не реализован ли уже этот запрос в проекте.
            Если НЕТ - создай план из 2-4 подзадач.
            Предложи 2-3 следующих логических шага после выполнения.
            
            Ответь JSON.
        """

        return self._inject_context(prompt)

    @staticmethod
    def answer_question(question: str) -> str:
        """Промпт для ответа на вопрос разработчика"""
        return f"Разработчик спрашивает: {question}\nДай технический ответ."

    @staticmethod
    def handle_review(review_feedback: str) -> str:
        """Промпт для обработки ревью"""
        return f"Результат ревью: {review_feedback}\nПрими решение: принять или отправить на доработку."
