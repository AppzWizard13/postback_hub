from django.apps import AppConfig

class SchedulerConfig(AppConfig):
    name = 'scheduler'

    def ready(self):
        import scheduler.scheduler
        scheduler.scheduler.start_scheduler()
