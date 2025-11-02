from django.db import models
from django.utils import timezone
from account.forms import User

# Create your models here.

class DhanKillProcessLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_on = models.DateTimeField(default=timezone.now)
    log = models.JSONField()
    order_count = models.IntegerField()

    def __str__(self):
        return f"Log for {self.user.username} - Orders: {self.order_count}"


class TempNotifierTable(models.Model):
    type = models.CharField(max_length=50)  # Adjust max_length as needed
    status = models.BooleanField(default=False)  # Default set to False

    def __str__(self):
        return f"{self.type} - {'Active' if self.status else 'Inactive'}"

class DailyAccountOverview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_account_overviews')
    opening_balance = models.FloatField()
    updated_on = models.DateTimeField(auto_now=True)
    pnl_status = models.FloatField()
    expenses = models.FloatField()
    closing_balance = models.FloatField()
    order_count = models.IntegerField()
    actual_profit = models.FloatField()
    day_open = models.BooleanField(default=False)
    day_close = models.BooleanField(default=False)

    def __str__(self):
        return f"Account Overview for {self.user.username} on {self.updated_on.strftime('%Y-%m-%d')}"


from django.db import models

class slOrderslog(models.Model):
    SECURITY_CHOICES = [
        ('NSE', 'National Stock Exchange'),
        ('BSE', 'Bombay Stock Exchange'),
        # Add more exchanges if needed
    ]
    
    TRANSACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    PRODUCT_TYPE_CHOICES = [
        ('INTRADAY', 'Intraday'),
        ('DELIVERY', 'Delivery'),
        # Add more product types if needed
    ]

    ORDER_TYPE_CHOICES = [
        ('MARKET', 'Market Order'),
        ('LIMIT', 'Limit Order'),
        ('STOP_LOSS', 'Stop Loss Order'),
        # Add more order types if needed
    ]
    order_id = models.CharField(max_length=100, help_text="ID of the Order being traded")
    security_id = models.CharField(max_length=100, help_text="ID of the security being traded")
    exchange_segment = models.CharField(max_length=50, choices=SECURITY_CHOICES, help_text="Segment of the exchange")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES, default='SELL')
    quantity = models.PositiveIntegerField(help_text="Number of units to trade")
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='STOP_LOSS')
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='INTRADAY')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at which the order is set")
    trigger_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Trigger price for stop-loss orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} - {self.transaction_type} {self.quantity} units at {self.price}"





class OrderHistoryLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_data = models.JSONField()
    date = models.DateField()
    order_count = models.IntegerField()
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2)
    eod_balance = models.DecimalField(max_digits=10, decimal_places=2)
    sod_balance = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    expense = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Order History Log for {self.user.username} on {self.date}"

    class Meta:
        ordering = ['-date']

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class DailySelfAnalysis(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    health_check = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Rate from 0 to 100")
    mind_check = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Rate from 0 to 100")
    expectation_level = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Rate from 0 to 100")
    patience_level = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Rate from 0 to 100")
    previous_day_self_analysis = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Rate from 0 to 100")
    pnl_status = models.CharField(max_length=100, null=True, blank=True, help_text="Profit and Loss Status of the day")
    order_count = models.IntegerField(null=True, blank=True, help_text="Total number of orders of the day")
    date_time = models.DateTimeField(auto_now_add=True, help_text="The date and time when the self-analysis was created")
    overall_advice =  models.CharField(max_length=5000, null=True, blank=True, help_text="Profit and Loss Status of the day")

    def __str__(self):
        return f"Self Analysis on {self.id} by {self.user.username} at {self.date_time}"

from datetime import date
class UserRTCUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)
    usage_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class TradingPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trading_plans")
    plan_name = models.CharField(max_length=255, unique=True)
    initial_capital = models.DecimalField(max_digits=12, decimal_places=2)
    expected_growth = models.DecimalField(max_digits=20, decimal_places=2, help_text="Expected growth as a percentage (e.g., 15.5 for 15.5%)")
    no_of_weeks = models.PositiveIntegerField()
    average_weekly_gain = models.DecimalField(max_digits=5, decimal_places=2, help_text="Average weekly gain as a percentage (e.g., 2.5 for 2.5%)")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)  # New field with default False

    def __str__(self):
        return f"{self.plan_name} - {self.user.username}"
class WeeklyGoalReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan_id = models.IntegerField()  # plan_id to uniquely identify a plan
    plan_name = models.CharField(max_length=255)  # plan_name added to the WeeklyGoalReport
    week_number = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    accumulated_capital = models.DecimalField(max_digits=15, decimal_places=2)
    gained_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_achieved = models.BooleanField(default=False)

    def __str__(self):
        return f"Week {self.week_number} Report - {self.plan_name}"


class DailyGoalReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    weekly_goal = models.ForeignKey(WeeklyGoalReport, on_delete=models.CASCADE, related_name="daily_reports")
    plan_id = models.IntegerField()  # plan_id to uniquely identify a plan
    plan_name = models.CharField(max_length=255)  # plan_name added to the DailyGoalReport
    day_number = models.IntegerField()
    date = models.DateField()
    capital = models.DecimalField(max_digits=15, decimal_places=2)
    gained_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_achieved = models.BooleanField(default=False)
    progress = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Day {self.day_number} Report - {self.plan_name} - {self.date}"
