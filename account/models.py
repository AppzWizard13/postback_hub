from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models



class User(AbstractUser):
    phone_number = models.CharField(max_length=12, null=True)
    profile_image = models.ImageField(upload_to='uploads/', null=True)
    country = models.CharField(max_length=250, null=True)
    status = models.BooleanField(default=False)  # New is_active field
    role = models.CharField(max_length=250, null=True)
    dhan_client_id = models.CharField(max_length=250, null=True)
    dhan_access_token = models.CharField(max_length=1000, null=True)
    is_active = models.BooleanField(default=False)  # New is_active field
    auto_stop_loss = models.BooleanField(default=False)
    kill_switch_1  = models.BooleanField(default=False)  # New is_kill_1  field
    kill_switch_2 = models.BooleanField(default=False)  # New is_kill_2  field
    quick_exit = models.BooleanField(default=False)
    sl_control_mode = models.BooleanField(default=False)
    last_order_count = models.IntegerField(default=0)
    reserved_trade_count = models.IntegerField(default=0)


    # Adding related_name to prevent reverse accessor clashes
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_groups',  # Change the related_name to avoid conflict
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions',  # Change the related_name to avoid conflict
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    REQUIRED_FIELDS = []

    def __str__(self):
        return self.username



class Control(models.Model):
    ENABLE_DISABLE_CHOICES = [
        ('0', 'Disable'),
        ('1', 'Enable'),
    ]
    STOPLOSS_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('points', 'Points'),
        ('price', 'Price'),
    ]

    order_limit_first = models.IntegerField(default=0)
    order_limit_second = models.IntegerField(default=0)
    default_order_limit_second = models.IntegerField(default=0)
    max_loss_limit = models.FloatField(default=0.0)
    peak_loss_limit = models.FloatField(default=0.0)
    max_profit_limit = models.FloatField(default=0.0)
    peak_profit_limit = models.FloatField(default=0.0)
    max_lot_size_limit = models.FloatField(default=0.0)
    max_loss_mode = models.CharField(max_length=1, choices=ENABLE_DISABLE_CHOICES, default='0')
    max_profit_mode = models.CharField(max_length=1, choices=ENABLE_DISABLE_CHOICES, default='0')
    max_order_count_mode = models.CharField(max_length=1, choices=ENABLE_DISABLE_CHOICES, default='0')
    max_lot_size_mode = models.CharField(max_length=1, choices=ENABLE_DISABLE_CHOICES, default='0')
    stoploss_parameter = models.IntegerField(default=0)
    stoploss_type = models.CharField(
        max_length=10,
        choices=STOPLOSS_TYPE_CHOICES,
        default='percentage',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Foreign key for user

    def __str__(self):
        return f"Control Settings (Order Limit: {self.order_limit_first}, Profit Limit: {self.max_profit_limit})"


