import asyncio
import yaml
from pathlib import Path
from datetime import datetime
import json

from core.ollama_client import OllamaClient
from core.task_manager import TaskManager
from core.message_bus import MessageBus
from agents.tech_lead import TechLead
from agents.senior_dev import SeniorDev
from agents.reviewer import Reviewer

# ИЗМЕНЕНО: Добавлена глобальная переменная для корня агентов
AGENTS_ROOT = Path(__file__).parent


async def process_user_request(message_bus, request):
    """Обработка запроса пользователя"""
    from core.agent_base import Message

    message = Message(
        sender="user",
        receiver="tech_lead",
        task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        content=request,
        msg_type="user_request",
        timestamp=datetime.now().isoformat(),
        metadata={}
    )

    print(f"\n{'=' * 50}")
    print(f"📤 Запрос: {request[:80]}...")
    print(f"🆔 ID задачи: {message.task_id}")
    print(f"{'=' * 50}\n")

    await message_bus.message_queue.put(message)

    # Ждем ответа
    for i in range(1200):
        await asyncio.sleep(1)

        if hasattr(message_bus, 'user_messages') and message_bus.user_messages:
            msg = message_bus.user_messages.pop(0)
            print(f"\n{'=' * 50}")
            print(f"📬 ОТВЕТ КОМАНДЫ:")
            print(f"{'=' * 50}")
            print(msg.content)
            print(f"{'=' * 50}\n")

            # Проверяем, успешно ли выполнена задача
            if "✅ Задача выполнена" in msg.content or "✅ Код принят" in msg.content:
                print("\n" + "=" * 50)
                print("📋 ПРОВЕРКА РЕЗУЛЬТАТА")
                print("=" * 50)

                # ИЗМЕНЕНО: Путь к проекту относительно агентов
                project_path = (AGENTS_ROOT / ".." / "pet_game").resolve()

                if project_path.exists():
                    print("\n📁 Последние изменения:")

                    # Показываем последние измененные файлы
                    py_files = sorted(project_path.rglob("*.py"), key=lambda x: x.stat().st_mtime, reverse=True)
                    for f in py_files[:5]:  # Последние 5 файлов
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        print(
                            f"  • {f.relative_to(project_path)} ({f.stat().st_size} байт) - изменен {mtime.strftime('%H:%M:%S')}")

                    # Показываем содержимое самого большого измененного файла
                    if py_files:
                        latest_file = max(py_files, key=lambda x: x.stat().st_size)
                        print(f"\n📄 Содержимое {latest_file.relative_to(project_path)}:")
                        print("-" * 40)
                        try:
                            with open(latest_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                print(content[:1000])
                                if len(content) > 1000:
                                    print(f"\n... (всего {len(content)} символов)")
                        except:
                            print("⚠️ Не удалось прочитать файл")

                # ИЗМЕНЕНО: Отчеты в папке .ai_reports проекта
                reports_dir = project_path.parent / ".ai_reports"
                if reports_dir.exists():
                    report_files = sorted(reports_dir.glob("report_*.txt"), key=lambda x: x.stat().st_mtime,
                                          reverse=True)
                    if report_files:
                        print(f"\n📄 Последний отчет:")
                        print("-" * 40)
                        try:
                            with open(report_files[0], 'r', encoding='utf-8') as f:
                                print(f.read()[:500])
                        except:
                            print("⚠️ Не удалось прочитать отчет")

                # ИЗМЕНЕНО: Git log из корня проекта
                try:
                    import subprocess
                    result = subprocess.run(
                        ['git', 'log', '--oneline', '-3'],
                        cwd=str(project_path.parent),  # Корень WitchsStory
                        capture_output=True,
                        text=True
                    )
                    if result.stdout.strip():
                        print(f"\n📝 Последние коммиты:")
                        print(result.stdout)
                except:
                    pass

                print("\n" + "-" * 40)

                # Запрашиваем подтверждение
                while True:
                    choice = input(
                        "\n👍 Подтвердить выполнение задачи? (y - да / n - нет / r - повторить / q - выйти): ").lower()

                    if choice == 'y':
                        # ✅ Подтверждаем задачу
                        task_id = msg.task_id

                        # ИЗМЕНЕНО: Путь к задачам
                        tasks_dir = project_path.parent / ".ai_tasks"
                        tasks_dir.mkdir(exist_ok=True)

                        task_file = tasks_dir / f"{task_id}.json"
                        if task_file.exists():
                            try:
                                with open(task_file, 'r') as f:
                                    task_data = json.load(f)
                                task_data['status'] = 'approved'
                                task_data['approved_at'] = datetime.now().isoformat()
                                with open(task_file, 'w') as f:
                                    json.dump(task_data, f, indent=2, ensure_ascii=False)
                            except:
                                pass

                        # Добавляем файлы в защищенную зону
                        protected_file = project_path / ".protected"
                        with open(protected_file, 'a', encoding='utf-8') as f:
                            f.write(f"\n# Задача {task_id} - подтверждена {datetime.now()}\n")
                            py_files = sorted(project_path.rglob("*.py"), key=lambda x: x.stat().st_mtime, reverse=True)
                            for pf in py_files[:3]:  # Последние 3 измененных файла
                                f.write(f"{pf.relative_to(project_path)}\n")

                        print("✅ Задача подтверждена! Код добавлен в защищенную зону.")
                        print("   Эти файлы больше не будут изменяться без явного запроса.")
                        break

                    elif choice == 'n':
                        print("❌ Задача отклонена. Можно запросить новую.")
                        break

                    elif choice == 'r':
                        print("🔄 Повторяем задачу...")
                        # Можно добавить логику повторения
                        break

                    elif choice == 'q':
                        print("💾 Задача остается без изменений. Выходим.")
                        return True

                    else:
                        print("⚠️ Введите y, n, r или q")

            return True

        if i % 30 == 0 and i > 0:  # ИЗМЕНЕНО: 15 -> 30 для меньшего шума
            print(f"⏰ Работаем... ({i}с)")

    print("\n⚠️ Время ожидания истекло (1200с)")
    return False


def show_project_stats():
    """Показывает статистику проекта"""
    # ИЗМЕНЕНО: Все пути относительно агентов
    project_path = (AGENTS_ROOT / ".." / "pet_game").resolve()
    tasks_dir = (AGENTS_ROOT / ".." / ".ai_tasks").resolve()
    logs_dir = (AGENTS_ROOT / ".." / ".ai_logs").resolve()

    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА ПРОЕКТА")
    print("=" * 60)

    # Файлы
    if project_path.exists():
        py_files = list(project_path.rglob("*.py"))
        if py_files:
            print(f"\n💻 Python файлы ({len(py_files)}):")
            for f in py_files:
                size = f.stat().st_size
                print(f"  • {f.relative_to(project_path)} ({size} байт)")
        else:
            print("\n💻 Python файлы: пока нет")

    # Задачи
    if tasks_dir.exists():
        task_files = list(tasks_dir.glob("*.json"))
        if task_files:
            done = 0
            for tf in task_files:
                try:
                    with open(tf, 'r') as f:
                        if json.load(f).get('status') == 'done':
                            done += 1
                except:
                    pass
            print(f"\n📋 Задачи: {done}/{len(task_files)} выполнено")

    # Логи
    if logs_dir.exists():
        log_files = list(logs_dir.glob("team_log_*.jsonl"))
        if log_files:
            total_msgs = 0
            for lf in log_files:
                with open(lf, 'r') as f:
                    total_msgs += len([l for l in f if l.strip()])
            print(f"\n📝 Сообщений в логах: {total_msgs}")

    print("=" * 60)


async def main():
    # ИЗМЕНЕНО: Все пути относительно AGENTS_ROOT
    agents_root = Path(__file__).parent

    # Загружаем конфиг
    config_path = agents_root / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("🔧 Инициализация системы...")
    print(f"📊 Модели: TechLead={config['ollama']['models']['architect']}, "
          f"Dev={config['ollama']['models']['coder']}")

    # ИЗМЕНЕНО: Вычисляем пути
    project_path = (agents_root / config['workspace']['project_path']).resolve()
    tasks_path = (agents_root / config['workspace']['tasks_path']).resolve()
    logs_path = (agents_root / config['workspace']['logs_path']).resolve()

    # Создаем директории если нужно
    project_path.mkdir(parents=True, exist_ok=True)
    tasks_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    print(f"📁 Проект: {project_path}")
    print(f"📁 Задачи: {tasks_path}")
    print(f"📁 Логи: {logs_path}")

    # Инициализируем компоненты
    ollama_client = OllamaClient(
        config['ollama']['base_url'],
        config['ollama']['timeout']
    )

    task_manager = TaskManager(str(tasks_path))
    message_bus = MessageBus()

    # Создаем агентов
    tech_lead = TechLead(
        config['ollama']['models']['architect'],
        config['agents']['tech_lead'],
        task_manager
    )
    tech_lead.ollama_client = ollama_client

    # ИЗМЕНЕНО: Передаем полный путь к проекту
    senior_dev = SeniorDev(
        config['ollama']['models']['coder'],
        config['agents']['senior_dev'],
        str(project_path)
    )
    senior_dev.ollama_client = ollama_client

    reviewer = Reviewer(
        config['ollama']['models']['reviewer'],
        config['agents']['reviewer']
    )
    reviewer.ollama_client = ollama_client

    # Регистрируем агентов
    message_bus.register_agent(tech_lead)
    message_bus.register_agent(senior_dev)
    message_bus.register_agent(reviewer)

    # Запускаем шину сообщений
    bus_task = asyncio.create_task(message_bus.start())

    print("\n" + "=" * 60)
    print("🤖 СИСТЕМА ИИ-РАЗРАБОТКИ ГОТОВА!")
    print("💡 Для выхода: 'exit' или Ctrl+C")
    print(f"💡 Проект: {project_path}")
    print("=" * 60)

    try:
        while True:
            user_input = input("\n💬 Задача (exit/статистика): ")

            if user_input.lower() == 'exit':
                break
            elif user_input.lower() == 'статистика':
                show_project_stats()
                continue
            elif not user_input.strip():
                continue

            await process_user_request(message_bus, user_input)

    except KeyboardInterrupt:
        print("\n👋 Завершение работы...")

    # Останавливаем шину
    message_bus.running = False
    await bus_task

    # Финальная статистика
    show_project_stats()
    print("\n👋 До свидания!")


if __name__ == "__main__":
    asyncio.run(main())
