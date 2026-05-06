import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import aiofiles

class Task:
    def __init__(self, id: str, title: str, description: str, 
                 status: str = "pending", assigned_to: Optional[str] = None,
                 created_at: Optional[str] = None,
                 updated_at: Optional[str] = None,
                 subtasks: Optional[List] = None,
                 result: Optional[str] = None,
                 review_feedback: Optional[str] = None,
                 **kwargs):  # Игнорирует все остальные параметры
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.assigned_to = assigned_to
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or self.created_at
        self.subtasks = subtasks or []
        self.result = result
        self.review_feedback = review_feedback

class TaskManager:
    def __init__(self, tasks_path: str):
        self.tasks_path = Path(tasks_path)
        self.tasks_path.mkdir(exist_ok=True)
        self.tasks: Dict[str, Task] = {}
        
    def create_task(self, title: str, description: str) -> Task:
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        task = Task(
            id=task_id, 
            title=title, 
            description=description,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.tasks[task_id] = task
        return task
    
    def add_subtask(self, parent_id: str, title: str, description: str) -> Task:
        subtask = self.create_task(title, description)
        if parent_id in self.tasks:
            self.tasks[parent_id].subtasks.append(subtask)
        return subtask
    
    async def save_task(self, task: Task):
        file_path = self.tasks_path / f"{task.id}.json"
        
        task_dict = {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'status': task.status,
            'assigned_to': task.assigned_to,
            'created_at': task.created_at,
            'updated_at': task.updated_at,
            'subtasks': [
                {
                    'id': st.id,
                    'title': st.title,
                    'description': st.description,
                    'status': st.status,
                    'assigned_to': st.assigned_to,
                    'created_at': st.created_at,
                    'updated_at': st.updated_at,
                    'subtasks': [],
                    'result': st.result,
                    'review_feedback': st.review_feedback
                }
                for st in task.subtasks
            ],
            'result': task.result,
            'review_feedback': task.review_feedback
        }
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(task_dict, ensure_ascii=False, indent=2))
    
    async def load_task(self, task_id: str) -> Optional[Task]:
        file_path = self.tasks_path / f"{task_id}.json"
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
            
            return Task(**data)
        except Exception as e:
            print(f"❌ Ошибка загрузки задачи: {e}")
            return None
    
    async def update_task_status(self, task_id: str, status: str, result: Optional[str] = None):
        task = await self.load_task(task_id)
        if task:
            task.status = status
            task.updated_at = datetime.now().isoformat()
            if result:
                task.result = result
            await self.save_task(task)
