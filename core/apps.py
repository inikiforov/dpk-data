from django.apps import AppConfig
import os


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Called when Django is ready.
        Start the portfolio price scheduler if enabled.
        """
        # Avoid running scheduler twice in development (Django auto-reloader)
        # RUN_MAIN is set by the reloader; we only start scheduler when it's 'true'
        # or when not using runserver (e.g., gunicorn, uwsgi)
        run_main = os.environ.get('RUN_MAIN')
        
        # Only start if:
        # 1. RUN_MAIN is 'true' (second process in runserver) OR
        # 2. RUN_MAIN is not set (production server like gunicorn)
        if run_main == 'true' or run_main is None:
            # Check if scheduler is enabled via environment variable
            if os.environ.get('ENABLE_PORTFOLIO_SCHEDULER', 'false').lower() == 'true':
                from core.scheduler import start_scheduler
                start_scheduler()
