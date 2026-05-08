from base_prompt import BasePrompt


class ReviewerPrompts(BasePrompt):
    """Промпты для Reviewer"""

    def system(self) -> str:
        return """
            Ты - строгий Code Reviewer и QA инженер.
            Проверяешь код и пишешь тесты.
            
            Всегда создавай ТОЛЬКО pytest тесты с именем функции начиная с test_
            
            Формат ответа:
            JSON с полем "test_code" содержащим ГОТОВЫЙ К ЗАПУСКУ код тестов
            или
            Просто код тестов с импортами
            
            Тесты должны быть простыми и проверять функциональность.
        """

    @staticmethod
    def generate_tests(task_desc: str, project_code: str,
                       functions: list, classes: list) -> str:
        """Промпт для генерации тестов"""
        example_test = '''
            def test_example(client):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
        '''

        return f"""
            Задача: {task_desc[:200]}

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

    @staticmethod
    def review_only(task_desc: str, code: str) -> str:
        """Промпт только для проверки (без тестов)"""
        return f"""
            Задача: {task_desc[:200]}   
        
            Код для проверки:
            {code[:1500]}
            
            Проверь на:
            1. Правильность async/await
            2. Обработку ошибок
            3. Соответствие FastAPI
            4. Безопасность
            
            Верни JSON с результатом проверки.
        """
