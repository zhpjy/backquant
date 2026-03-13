"""Task manager for market data operations."""
import threading
import uuid
from datetime import datetime
from typing import Optional, Callable
from queue import Queue

from app.database import DatabaseConfig, get_db_connection


class TaskManager:
    """Lightweight task manager for market data operations.

    Uses a serialized DatabaseConfig dict so that background worker threads
    can connect to the database without a Flask application context.
    """

    def __init__(self, db_config_dict: dict, max_workers: int = 1):
        self.db_config_dict = db_config_dict
        self.max_workers = max_workers
        self.task_queue = Queue()
        self.workers = []
        self.lock = threading.Lock()
        self._init_db()
        self._start_workers()

    def _get_db_connection(self):
        """Return a context manager for a database connection.

        Works in both Flask request context and background threads because
        it uses the pre-serialized config dict instead of current_app.
        """
        return get_db_connection(config_dict=self.db_config_dict)

    def _init_db(self):
        """Initialize database tables."""
        from app.market_data.db_init import init_database_with_connection
        with self._get_db_connection() as db:
            init_database_with_connection(db)

    def _start_workers(self):
        """Start worker threads."""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"TaskWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self):
        """Worker thread main loop."""
        while True:
            task_id, task_func, task_args = self.task_queue.get()
            try:
                self._update_task_status(task_id, 'running', started_at=datetime.utcnow())
                task_func(task_id, *task_args)
                self._update_task_status(task_id, 'success', finished_at=datetime.utcnow())
            except Exception as e:
                self._update_task_status(
                    task_id, 'failed',
                    error=str(e),
                    finished_at=datetime.utcnow()
                )
            finally:
                self.task_queue.task_done()

    def submit_task(self, task_type: str, task_func: Callable,
                    task_args: tuple = (), source: str = 'manual') -> str:
        """Submit a task for execution."""
        with self.lock:
            # Allow auto tasks to be submitted even when there's a running task
            # This is needed for chained tasks (e.g., download -> analyze)
            if source != 'auto' and self._has_running_task(task_type):
                raise RuntimeError("已有任务正在运行，请等待完成后再试")

            task_id = str(uuid.uuid4())
            self._create_task(task_id, task_type, source)
            self.task_queue.put((task_id, task_func, task_args))
            return task_id

    def _has_running_task(self, task_type: str = None) -> bool:
        """Check if there is a running task of the same category.

        vnpy_import tasks are independent from other market data tasks.
        """
        with self._get_db_connection() as db:
            if task_type == 'vnpy_import':
                row = db.fetchone(
                    "SELECT COUNT(*) as count FROM market_data_tasks "
                    "WHERE status IN ('pending', 'running') AND task_type = 'vnpy_import'"
                )
            else:
                row = db.fetchone(
                    "SELECT COUNT(*) as count FROM market_data_tasks "
                    "WHERE status IN ('pending', 'running') AND task_type != 'vnpy_import'"
                )
            return (row['count'] if row else 0) > 0

    def _create_task(self, task_id: str, task_type: str, source: str):
        """Create task record."""
        with self._get_db_connection() as db:
            db.execute(
                """INSERT INTO market_data_tasks
                   (task_id, task_type, status, source, created_at)
                   VALUES (?, ?, 'pending', ?, ?)""",
                (task_id, task_type, source, datetime.utcnow().isoformat())
            )

    def _update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status."""
        updates = ["status = ?"]
        params = [status]

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value.isoformat() if isinstance(value, datetime) else value)

        params.append(task_id)
        sql = f"UPDATE market_data_tasks SET {', '.join(updates)} WHERE task_id = ?"

        with self._get_db_connection() as db:
            db.execute(sql, tuple(params))

    def update_progress(self, task_id: str, progress: int, stage: str, message: str):
        """Update task progress."""
        with self._get_db_connection() as db:
            db.execute(
                """UPDATE market_data_tasks
                   SET progress = ?, stage = ?, message = ?
                   WHERE task_id = ?""",
                (progress, stage, message, task_id)
            )

    def log(self, task_id: str, level: str, message: str):
        """Log task message."""
        with self._get_db_connection() as db:
            db.execute(
                """INSERT INTO market_data_task_logs
                   (task_id, timestamp, level, message)
                   VALUES (?, ?, ?, ?)""",
                (task_id, datetime.utcnow().isoformat(), level, message)
            )

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status."""
        with self._get_db_connection() as db:
            return db.fetchone(
                "SELECT * FROM market_data_tasks WHERE task_id = ?",
                (task_id,)
            )

    def get_running_task(self) -> Optional[dict]:
        """Get currently running or pending task."""
        with self._get_db_connection() as db:
            return db.fetchone(
                """SELECT * FROM market_data_tasks
                   WHERE status IN ('pending', 'running')
                   ORDER BY created_at DESC
                   LIMIT 1"""
            )

    def get_running_task_by_type(self, task_type: str) -> Optional[dict]:
        """Get currently running or pending task of a specific type."""
        with self._get_db_connection() as db:
            return db.fetchone(
                """SELECT * FROM market_data_tasks
                   WHERE status IN ('pending', 'running') AND task_type = ?
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (task_type,)
            )

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task by marking it as cancelled."""
        with self._get_db_connection() as db:
            row = db.fetchone(
                "SELECT status FROM market_data_tasks WHERE task_id = ?",
                (task_id,)
            )
            if not row or row['status'] not in ('pending', 'running'):
                return False
            db.execute(
                "UPDATE market_data_tasks SET status = 'cancelled', finished_at = ? WHERE task_id = ?",
                (datetime.utcnow().isoformat(), task_id)
            )
            return True


# Global singleton
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get task manager singleton.

    Must be called at least once within a Flask application context so that
    the database configuration can be resolved. Subsequent calls (including
    from background threads) reuse the cached singleton without requiring a
    Flask context.
    """
    global _task_manager
    if _task_manager is None:
        config = DatabaseConfig.from_flask_config('market_data')
        # Ensure SQLite parent directory exists before handing off to TaskManager
        if config.db_type == 'sqlite' and config.sqlite_path:
            config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        _task_manager = TaskManager(config.to_dict(), max_workers=1)
    return _task_manager
