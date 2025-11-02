from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Control

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users with extended fields.
    Used in admin and user registration views.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter email address'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter last name'
        })
    )
    phone_number = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter phone number'
        })
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'email', 
            'username', 
            'phone_number',
            'password1', 
            'password2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove default help texts
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None
        self.fields['username'].help_text = None
        
        # Add Bootstrap classes and placeholders
        self.fields['username'].widget.attrs.update({
            'class': 'form-control m-2',
            'placeholder': 'Enter username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control m-2',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control m-2',
            'placeholder': 'Confirm password'
        })

    def clean_email(self):
        """Validate that email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_phone_number(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone_number')
        if phone and not phone.isdigit():
            raise ValidationError("Phone number must contain only digits.")
        return phone


class UserLoginForm(forms.Form):
    """
    Form for user login with username and password.
    """
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control m-2',
            'id': 'id_username',
            'placeholder': 'Enter username',
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control m-2',
            'id': 'id_password',
            'placeholder': 'Enter password',
            'autocomplete': 'current-password'
        })
    )

    def clean(self):
        """Additional form-level validation"""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            # Add any custom validation logic here
            pass
        
        return cleaned_data


class UserProfileUpdateForm(forms.ModelForm):
    """
    Form for updating basic user profile information.
    Used by regular users to update their own profiles.
    """
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'username', 
            'email', 
            'phone_number',
            'dhan_client_id', 
            'dhan_access_token', 
            'reserved_trade_count'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control m-1'
            
            # Add placeholders
            if field_name == 'first_name':
                field.widget.attrs['placeholder'] = 'First name'
            elif field_name == 'last_name':
                field.widget.attrs['placeholder'] = 'Last name'
            elif field_name == 'username':
                field.widget.attrs['placeholder'] = 'Username'
            elif field_name == 'email':
                field.widget.attrs['placeholder'] = 'Email address'
            elif field_name == 'phone_number':
                field.widget.attrs['placeholder'] = 'Phone number'

    def clean_email(self):
        """Validate email uniqueness excluding current user"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("This email address is already in use.")
        return email


class UserAdminUpdateForm(forms.ModelForm):
    """
    Comprehensive form for admin to update user information.
    Includes all user fields including trading settings.
    """
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'username',
            'email',
            'phone_number', 
            'country', 
            'dhan_client_id', 
            'dhan_access_token', 
            'status',
            'is_active', 
            'auto_stop_loss', 
            'kill_switch_1',
            'kill_switch_2',
            'quick_exit',
            'sl_control_mode',
            'reserved_trade_count'
        ]
        widgets = {
            'profile_image': forms.ClearableFileInput(attrs={
                'class': 'form-control m-1'
            }),
            # 'country': forms.Select(attrs={
            #     'class': 'form-control m-1'
            # }),
            'role': forms.TextInput(attrs={
                'class': 'form-control m-1',
                'placeholder': 'User role'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['profile_image']:
                # Boolean fields should use CheckboxInput
                if isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs['class'] = 'form-check-input m-1'
                else:
                    field.widget.attrs['class'] = 'form-control m-1'

class ControlCreateForm(forms.ModelForm):
    """
    Form for creating new Control instances.
    Used by admin to set trading control parameters.
    """
    class Meta:
        model = Control
        fields = [
            'user',
            'order_limit_first', 
            'order_limit_second', 
            'default_order_limit_second',
            'max_loss_limit',
            'peak_loss_limit',
            'max_profit_limit', 
            'max_loss_mode',
            'max_profit_mode', 
            'max_order_count_mode', 
            'max_lot_size_mode',
            'max_lot_size_limit',
            'stoploss_parameter',
            'stoploss_type'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
                field.widget.attrs['role'] = 'switch'
            else:
                field.widget.attrs['class'] = 'form-control m-2'
            
            # Remove help texts
            field.help_text = None
            
            # Add placeholders for numeric fields
            if field_name.endswith('_limit'):
                field.widget.attrs['placeholder'] = f'Enter {field.label.lower()}'
            elif field_name == 'stoploss_parameter':
                field.widget.attrs['placeholder'] = 'Enter stop loss value'

    def clean_user(self):
        """Validate that user doesn't already have a Control instance"""
        user = self.cleaned_data.get('user')
        if user and Control.objects.filter(user=user).exists():
            raise ValidationError(
                f"Control settings already exist for user '{user.username}'. "
                "Each user can only have one control configuration."
            )
        return user

    def clean(self):
        """Validate control parameters"""
        cleaned_data = super().clean()
        
        # Validate order_limit_second >= order_limit_first
        max_order = cleaned_data.get('order_limit_first')
        peak_order = cleaned_data.get('order_limit_second')
        
        if max_order and peak_order and peak_order < max_order:
            raise ValidationError(
                "Order Limit Second must be greater than or equal to Order Limit First."
            )
        
        # Validate loss limits
        max_loss = cleaned_data.get('max_loss_limit')
        peak_loss = cleaned_data.get('peak_loss_limit')
        
        if max_loss and peak_loss and peak_loss < max_loss:
            raise ValidationError(
                "Peak loss limit must be greater than or equal to max loss limit."
            )
        
        return cleaned_data


class ControlUpdateForm(forms.ModelForm):
    """
    Form for updating existing Control instances.
    Similar to ControlCreateForm but used for updates.
    """
    class Meta:
        model = Control
        fields = [
            'user',
            'order_limit_first', 
            'order_limit_second', 
            'default_order_limit_second', 
            'max_loss_limit',
            'peak_loss_limit', 
            'max_profit_limit',
            'max_loss_mode',
            'max_profit_mode', 
            'max_order_count_mode', 
            'max_lot_size_mode',
            'max_lot_size_limit',
            'stoploss_parameter',
            'stoploss_type'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input m-2'
            else:
                field.widget.attrs['class'] = 'form-control m-2'
            
            # Remove help texts
            field.help_text = None

        # Make user field read-only in update form
        if self.instance.pk:
            self.fields['user'].disabled = True

    def clean(self):
        """Validate control parameters"""
        cleaned_data = super().clean()
        
        # Validate order_limit_second >= order_limit_first
        max_order = cleaned_data.get('order_limit_first')
        peak_order = cleaned_data.get('order_limit_second')
        
        if max_order and peak_order and peak_order < max_order:
            raise ValidationError(
                "Order Limit Second must be greater than or equal to Order Limit First."
            )
        
        # Validate loss limits
        max_loss = cleaned_data.get('max_loss_limit')
        peak_loss = cleaned_data.get('peak_loss_limit')
        
        if max_loss and peak_loss and peak_loss < max_loss:
            raise ValidationError(
                "Peak loss limit must be greater than or equal to max loss limit."
            )
        
        return cleaned_data


class UserPasswordChangeForm(forms.Form):
    """
    Form for users to change their password.
    Requires old password for verification.
    """
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter current password',
            'autocomplete': 'current-password'
        })
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Enter new password',
            'autocomplete': 'new-password'
        })
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control m-2',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """Validate old password"""
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError("Current password is incorrect.")
        return old_password

    def clean(self):
        """Validate new passwords match"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError("New passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        """Save the new password"""
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class UserBulkActionForm(forms.Form):
    """
    Form for performing bulk actions on multiple users.
    Used in admin list views.
    """
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('activate', 'Activate Users'),
        ('deactivate', 'Deactivate Users'),
        ('enable_status', 'Enable Status'),
        ('disable_status', 'Disable Status'),
        ('enable_auto_sl', 'Enable Auto Stop Loss'),
        ('disable_auto_sl', 'Disable Auto Stop Loss'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control m-2'
        })
    )
    
    user_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )

    def clean_user_ids(self):
        """Parse and validate user IDs"""
        user_ids = self.cleaned_data.get('user_ids')
        try:
            id_list = [int(id.strip()) for id in user_ids.split(',') if id.strip()]
            if not id_list:
                raise ValidationError("No users selected.")
            return id_list
        except ValueError:
            raise ValidationError("Invalid user IDs.")


class UserSearchForm(forms.Form):
    """
    Form for searching and filtering users.
    Used in user list views.
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by username, email, or name...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    is_active = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )


class ControlSearchForm(forms.Form):
    """
    Form for searching and filtering control records.
    """
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    max_loss_mode = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All'),
            ('true', 'Enabled'),
            ('false', 'Disabled'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )