from django.apps import AppConfig

class AccountConfig(AppConfig):
    name = 'account'

    def ready(self):
        import account.tasks  # This ensures the @aiocron decorator is processed
