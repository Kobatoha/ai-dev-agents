from abc import ABC, abstractmethod


class BasePrompt(ABC):
    """Базовый класс для всех промптов"""

    def __init__(self, context: dict[str, str] | None = None):
        self.context = context or {}

    @abstractmethod
    def system(self) -> str:
        """Системный промпт (роль агента)"""
        pass

    def build(self, template_name: str, **kwargs) -> str:
        """Собирает промпт из шаблона"""
        method = getattr(self, template_name, None)
        if method:
            return method(**kwargs)
        raise ValueError(f"Template {template_name} not found")

    def _inject_context(self, prompt: str) -> str:
        """Добавляет контекст проекта в промпт"""
        if self.context:
            ctx_parts = []
            if 'project_structure' in self.context:
                ctx_parts.append(f"Структура проекта:\n{self.context['project_structure']}")
            if 'completed_tasks' in self.context:
                ctx_parts.append(f"Выполненные задачи:\n{self.context['completed_tasks']}")
            if ctx_parts:
                prompt = '\n\n'.join(ctx_parts) + '\n\n' + prompt

        return prompt
