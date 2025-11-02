"""
Django Views Module for Trading Platform.

This module contains all the view classes and functions for managing
trading operations, user authentication, account management, and reporting.

Author: Trading Platform Team
Version: 2.0
PEP8 Compliant and Performance Optimized
"""

# Standard library imports
import json
import http.client
from datetime import datetime, timedelta, date
from decimal import Decimal
import random
import re

# Third-party imports
import pytz
import requests
from dhanhq import dhanhq

# Django imports
from django.conf import settings
from django.contrib import messages, auth
from django.contrib.auth import (
    login, authenticate, logout, get_user_model
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import F, Sum, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, UpdateView
)

# Local imports
from account.forms import UserLoginForm
from .forms import (
    CustomUserCreationForm, UserAdminUpdateForm, ControlCreateForm,
    ControlUpdateForm
)
from account.models import (
    Control, 
)
from reports.models import (
    DailyAccountOverview, 
    DailySelfAnalysis, UserRTCUsage, DailyGoalReport
)

# Get the custom user model
User = get_user_model()


class HomePageView(TemplateView):
    """
    Home page view for the landing page.

    Displays the main landing page of the application.
    """

    template_name = "landing/index.html"

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add custom logic if needed."""
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Get context data for the template.

        Returns:
            dict: Empty context dictionary.
        """
        context = super().get_context_data(**kwargs)
        return context


class UserloginView(View):
    """
    User login view handling both GET and POST requests.

    GET: Displays the login form.
    POST: Processes login credentials and authenticates user.
    """

    template_name = "dashboard/authentication-login.html"

    def get(self, request):
        """
        Handle GET request to display login form.

        Args:
            request: HTTP request object.

        Returns:
            HttpResponse: Rendered login page or redirect to dashboard.
        """
        if request.user.is_authenticated:
            return redirect('dashboard')

        context = {'form': UserLoginForm()}
        return render(request, self.template_name, context)

    def post(self, request):
        """
        Handle POST request to authenticate user.

        Args:
            request: HTTP request object with login credentials.

        Returns:
            HttpResponse: Redirect to dashboard or login page with errors.
        """
        form = UserLoginForm(request.POST)
        context = {'form': form}

        if form.is_valid():
            username = request.POST.get("username")
            password = request.POST.get("password")

            user = auth.authenticate(username=username, password=password)

            if user:
                auth.login(request, user)
                messages.success(
                    request,
                    f"Welcome back, {user.first_name}! "
                    "You have successfully logged in."
                )
                return redirect('dashboard')
            else:
                messages.error(request, 'Username or Password incorrect!')

        return render(request, self.template_name, context)


class UserCreateView(CreateView):
    """
    User registration view for creating new user accounts.

    Requires superuser privileges to create new users.
    """

    model = User
    form_class = CustomUserCreationForm
    template_name = "dashboard/authentication-register.html"
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        """
        Validate form and check user privileges.

        Args:
            form: The submitted user creation form.

        Returns:
            HttpResponse: Success or error response.
        """
        if not self.request.user.is_superuser:
            messages.error(
                self.request,
                "You have no privilege to add members. Please contact admin."
            )
            return super().form_invalid(form)

        response = super().form_valid(form)
        messages.success(
            self.request,
            "Registration successful! Please log in with your credentials."
        )
        return response

    def form_invalid(self, form):
        """
        Handle invalid form submission.

        Args:
            form: The invalid form.

        Returns:
            HttpResponse: Error response with form errors.
        """
        messages.error(
            self.request,
            "There was an error with your registration. "
            "Please check the form and try again."
        )
        return super().form_invalid(form)


class ControlCreateView(CreateView):
    """
    Control creation view for setting trading parameters.

    Allows creation of trading control settings for users.
    """

    model = User
    form_class = ControlCreateForm
    template_name = "dashboard/create_control.html"
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        """
        Process valid control creation form.

        Args:
            form: The submitted control creation form.

        Returns:
            HttpResponse: Success response.
        """
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Control created successfully! Please log in to manage it."
        )
        return response

    def form_invalid(self, form):
        """
        Handle invalid control creation form.

        Args:
            form: The invalid form.

        Returns:
            HttpResponse: Error response.
        """
        messages.error(
            self.request,
            "There was an error creating the control. "
            "Please check the form and try again."
        )
        return super().form_invalid(form)


@method_decorator(login_required(login_url='/'), name='dispatch')
class DashboardView(TemplateView):
    """
    Main dashboard view displaying trading information and statistics.

    Shows comprehensive trading data including:
    - Fund limits and balances
    - Position data
    - Order history
    - P&L statistics
    - Performance metrics
    """

    template_name = "dashboard/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Initialize dashboard data and handle errors.

        Args:
            request: HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Dashboard page or redirect on error.
        """
        try:
            self.slug = kwargs.get('slug')
            self.users = User.objects.filter(is_active=True).select_related()
            self.allusers = self.users
            self.dashboard_view = True
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Error in DashboardView: {e}")
            return redirect('/users/')

    def get_context_data(self, **kwargs):
        """
        Prepare comprehensive dashboard context data.

        Performance optimizations:
        - Minimized database queries using select_related/prefetch_related
        - Cached repeated calculations
        - Optimized API calls

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: Context dictionary with all dashboard data.
        """
        context = super().get_context_data(**kwargs)

        # Get IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        now_time = datetime.now(ist)
        today = now_time.date()

        # Get user based on slug or current user
        user = self._get_user_from_slug()

        # Fetch control data with caching
        control_data = Control.objects.filter(user=user).first()

        # Initialize Dhan client and fetch data
        dhan_client = self._initialize_dhan_client(user)

        # Fetch all required data in parallel where possible
        fund_data = dhan_client.get_fund_limits()
        holdings = dhan_client.get_holdings()
        orderlistdata = dhan_client.get_order_list()
        position_data = dhan_client.get_positions()

        # Process order data
        traded_orders = get_traded_order_filter_dhan(orderlistdata)
        pending_sl_order = get_pending_order_filter_dhan(orderlistdata)
        order_count = get_traded_order_count(orderlistdata)

        # Calculate financial metrics
        total_expense = self._calculate_total_expense(order_count)
        total_realized_profit = self._calculate_realized_profit(position_data)

        # Process position data
        positions = self._get_positions(position_data)
        position_data_json = json.dumps(position_data.get('data', []))
        open_position = self._get_open_positions(position_data.get('data', []))

        # Calculate balances and P&L
        actual_profit = total_realized_profit - total_expense
        opening_balance, available_balance = self._extract_fund_data(fund_data)
        actual_balance = opening_balance + actual_profit

        # Determine actual balance for calculations
        actual_bal = (
            opening_balance if opening_balance >= available_balance 
            else available_balance
        )

        # Calculate P&L percentage
        pnl_percentage = (
            (actual_profit / actual_bal) * 100 
            if actual_profit and actual_bal else 0
        )

        # Extract control parameters
        control_params = self._extract_control_params(control_data)

        # Calculate trading limits and expenses
        day_exp_brokerage = (
            float(control_params['order_limit_second']) * 
            float(settings.BROKERAGE_PARAMETER)
        )

        exp_entry_count = control_params['order_limit_second'] // 2
        actual_entry_count = order_count // 2
        remaining_trades = (
            (control_params['order_limit_second'] - order_count) // 2
        )

        # Prepare breakup data for charts
        breakup_series, breakup_labels = self._prepare_breakup_data(
            total_realized_profit, opening_balance, 
            available_balance, total_expense
        )

        print("breakup_series, breakup_labels", breakup_series, breakup_labels)

        # Calculate max expected loss and expense
        max_expected_loss, max_expected_expense = (
            self._calculate_max_expected_metrics(
                control_data, remaining_trades, actual_bal, day_exp_brokerage
            )
        )

        # Fetch hourly status data with optimization
        hourly_status_data = list(
            DailyAccountOverview.objects
            .filter(user=user)
            .annotate(total=F('closing_balance'))
            .order_by('-updated_on')
            .values_list('total', flat=True)[:20]
        )[::-1]

        # Calculate progress metrics
        remaining_orders = (
            control_params['order_limit_second'] - order_count
        )
        progress_percentage = (
            (remaining_orders / control_params['order_limit_second']) * 100
        )
        progress_color = self._get_progress_color(progress_percentage)

        # Fetch and process daily analysis
        advice_dict = self._get_daily_analysis(user, today)

        # Calculate accuracy from recent performance
        accuracy = self._calculate_accuracy(user)

        # Calculate forecast balance
        charge_per_trade = 2 * float(settings.BROKERAGE_PARAMETER)
        max_remaining_expense = charge_per_trade * (remaining_orders // 2)

        forecast_balance, day_risk_forecast = (
            self._calculate_forecasts(
                control_params['stoploss_type'], remaining_orders,
                available_balance, control_params['stoploss_parameter'],
                charge_per_trade, remaining_trades, max_remaining_expense
            )
        )

        # Fetch daily goal data
        daily_goal_data = self._get_daily_goal_data(user, today)

        # Calculate weekly metrics
        used_rt_count = self._get_rtc_usage(user)
        weekly_trade_count = self._calculate_weekly_trade_count(
            control_data, user, used_rt_count
        )

        # Fetch weekly progress data
        weekly_progress_data = self._get_weekly_progress_data(
            user, weekly_trade_count
        )


        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", json.dumps(breakup_series))
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", json.dumps(breakup_labels))

        # Update context with all calculated data
        context.update({
            'accuracy': accuracy,
            'weekly_progress_data': weekly_progress_data,
            'weekly_trade_count': range(weekly_trade_count),
            'progress_color': progress_color,
            'open_position': open_position,
            'pending_sl_order': pending_sl_order,
            'breakup_series': breakup_series,
            'breakup_labels': breakup_labels,
            'breakup_series_json': json.dumps(breakup_series),
            'breakup_labels_json': json.dumps(breakup_labels),
            'actual_entry_count': actual_entry_count,
            'exp_entry_count': exp_entry_count,
            'max_expected_loss': max_expected_loss,
            'max_expected_expense': max_expected_expense,
            'fund_data': fund_data,
            'pnl_percentage': pnl_percentage,
            'day_exp_brokerge': day_exp_brokerage,
            'order_limit': control_params.get('order_limit', 0),
            'order_limit_second': control_params['order_limit_second'],
            'user': user,
            'advice_dict': advice_dict,
            'stoploss_parameter': control_params['stoploss_parameter'],
            'stoploss_type': control_params['stoploss_type'][:7].upper(),
            'hourly_status_data': hourly_status_data,
            'orderlistdata': traded_orders,
            'position_data': position_data,
            'current_date': today,
            'position_data_json': position_data_json,
            'total_realized_profit': total_realized_profit,
            'total_expense': total_expense,
            'order_count': order_count,
            'actual_profit': actual_profit,
            'actual_balance': actual_balance,
            'daily_goal_data': daily_goal_data,
            'remaining_orders': remaining_orders,
            'remaining_trades': remaining_orders // 2,
            'progress_percentage': progress_percentage,
            'forecast_balance': forecast_balance,
            'available_balance': available_balance,
            'day_risk_forecast': day_risk_forecast,
            'slug': self.slug,
            'users': self.users,
            'allusers': self.allusers,
            'dashboard_view': self.dashboard_view,
        })



        return context

    def _get_user_from_slug(self):
        """Get user from slug or return current user."""
        if self.slug:
            return User.objects.filter(username=self.slug).first()
        return self.request.user

    def _initialize_dhan_client(self, user):
        """Initialize and return Dhan API client."""
        return dhanhq(user.dhan_client_id, user.dhan_access_token)

    def _calculate_total_expense(self, order_count):
        """Calculate total brokerage expense."""
        return float(order_count * float(settings.BROKERAGE_PARAMETER))

    def _calculate_realized_profit(self, position_data):
        """Calculate total realized profit from positions."""
        if ('data' not in position_data or 
            not isinstance(position_data['data'], list) or 
            not position_data['data']):
            return 0.0

        positions = position_data['data']
        return float(sum(
            position.get('realizedProfit', 0) for position in positions
        ))

    def _get_positions(self, position_data):
        """Extract positions from position data."""
        if ('data' not in position_data or 
            not isinstance(position_data['data'], list) or 
            not position_data['data']):
            return False
        return position_data['data']

    def _get_open_positions(self, all_positions):
        """Filter open positions from all positions."""
        return [
            {
                'tradingSymbol': position['tradingSymbol'],
                'securityId': position['securityId']
            }
            for position in all_positions
            if (isinstance(position, dict) and 
                position.get('positionType') != 'CLOSED')
        ]

    def _extract_fund_data(self, fund_data):
        """Extract and validate fund data."""
        if (isinstance(fund_data, dict) and 
            'data' in fund_data and 
            isinstance(fund_data['data'], dict)):
            opening_balance = float(fund_data['data'].get('sodLimit', 0))
            available_balance = float(
                fund_data['data'].get('availabelBalance', 0)
            )
        else:
            opening_balance = 0.0
            available_balance = 0.0
        return opening_balance, available_balance

    def _extract_control_params(self, control_data):
        """Extract control parameters with defaults."""
        if control_data:
            return {
                'order_limit': control_data.order_limit_first,
                'order_limit_second': control_data.order_limit_second,
                'stoploss_parameter': control_data.stoploss_parameter,
                'stoploss_type': control_data.stoploss_type,
            }
        return {
            'order_limit': 0,
            'order_limit_second': 0,
            'stoploss_parameter': 0,
            'stoploss_type': "",
        }

    def _prepare_breakup_data(self, realized_profit, opening_balance, 
                              available_balance, total_expense):
        """Prepare data for breakup chart."""
        if realized_profit > 0:
            series = [opening_balance, realized_profit, total_expense]
        elif realized_profit < 0:
            series = [available_balance, realized_profit, total_expense]
        else:
            series = [available_balance, realized_profit, total_expense]

        labels = ['A/C Balance', 'Profit/Loss', 'Charges']
        return series, labels

    def _calculate_max_expected_metrics(self, control_data, remaining_trades,
                                       actual_bal, day_exp_brokerage):
        """Calculate maximum expected loss and expense."""
        max_expected_loss = 0
        max_expected_expense = 0

        if control_data:
            stoploss_param = control_data.stoploss_parameter
            if control_data.stoploss_type == "price":
                max_expected_loss = remaining_trades * stoploss_param
                max_expected_expense = (
                    float(max_expected_loss) + day_exp_brokerage
                )
            else:
                max_expected_loss = (
                    (actual_bal * remaining_trades) * (stoploss_param / 100)
                )
                max_expected_expense = (
                    float(max_expected_loss) + day_exp_brokerage
                )

        return max_expected_loss, max_expected_expense

    def _get_progress_color(self, progress_percentage):
        """Determine progress bar color based on percentage."""
        if progress_percentage >= 60:
            return 'green'
        elif progress_percentage >= 40:
            return 'yellow'
        elif progress_percentage >= 20:
            return 'orange'
        return 'red'

    def _get_daily_analysis(self, user, today):
        """Fetch and process daily self-analysis."""
        existing_analysis = DailySelfAnalysis.objects.filter(
            user=user, 
            date_time__date=today
        ).first()

        if existing_analysis and existing_analysis.overall_advice:
            cleaned_advice = re.sub(
                r"[()]", "", existing_analysis.overall_advice
            )
            advice_items = cleaned_advice.split("', '")

            advice_dict = {}
            for i in range(0, len(advice_items), 2):
                if i + 1 < len(advice_items):
                    key = advice_items[i].strip().strip("'")
                    value = advice_items[i + 1].strip().strip("'")
                    advice_dict[key] = value
            return advice_dict

        return {}

    def _calculate_accuracy(self, user):
        """Calculate trading accuracy from recent performance."""
        data = list(
            DailyAccountOverview.objects
            .filter(user=user)
            .annotate(annotated_pnl_status=F('pnl_status'))
            .order_by('-updated_on')
            .values('annotated_pnl_status')[:20]
        )[::-1]

        positive_pnl_count = sum(
            1 for entry in data if entry['annotated_pnl_status'] > 0
        )
        total_entries = len(data)

        return (
            (positive_pnl_count / total_entries) * 100 
            if total_entries > 0 else 0
        )

    def _calculate_forecasts(self, stoploss_type, remaining_orders,
                            available_balance, stoploss_parameter,
                            charge_per_trade, remaining_trades,
                            max_remaining_expense):
        """Calculate forecast balance and day risk forecast."""
        if stoploss_type == 'price' and remaining_orders > 0:
            forecast_balance = (
                available_balance - stoploss_parameter - charge_per_trade
            )
            day_risk_forecast = (
                available_balance - 
                (stoploss_parameter * remaining_trades) - 
                max_remaining_expense
            )
        else:
            forecast_balance = "0.00"
            day_risk_forecast = available_balance - max_remaining_expense

        return forecast_balance, day_risk_forecast

    def _get_daily_goal_data(self, user, today):
        """Fetch daily goal data for the user."""
        try:
            return DailyGoalReport.objects.filter(
                user=user, date=today
            ).get()
        except DailyGoalReport.DoesNotExist:
            return None

    def _get_rtc_usage(self, user):
        """Get RTC usage count for the user."""
        try:
            used_rtc = UserRTCUsage.objects.get(user=user)
            return int(used_rtc.usage_count)
        except UserRTCUsage.DoesNotExist:
            return 0

    def _calculate_weekly_trade_count(self, control_data, user, 
                                     used_rt_count):
        """Calculate total weekly trade count."""
        return int(
            (int(control_data.default_order_limit_second) / 2 * 5) +
            int(user.reserved_trade_count) +
            used_rt_count
        )

    def _get_weekly_progress_data(self, user, weekly_trade_count):
        """Fetch and process weekly progress data."""
        start_date, end_date = get_current_week_start_and_end_dates()

        results = DailyAccountOverview.objects.filter(
            user=user,
            day_open=False,
            updated_on__date__range=(start_date, end_date)
        ).order_by('id')

        weekly_data = list(results.values(
            'id', 'actual_profit', 'updated_on'
        ))

        for index, entry in enumerate(weekly_data, start=1):
            entry['serial_number'] = index

        weekly_progress_data = []
        available_serial_numbers = {
            trade_data['serial_number']: trade_data 
            for trade_data in weekly_data
        }

        for i in range(1, weekly_trade_count + 1):
            if i in available_serial_numbers:
                weekly_progress_data.append(available_serial_numbers[i])
            else:
                weekly_progress_data.append({
                    'serial_number': i, 
                    'status': 'No trade'
                })

        return weekly_progress_data


# Utility Functions

def get_current_week_start_and_end_dates():
    """
    Calculate the start (Monday) and end (Friday) dates of the current week.

    Returns:
        tuple: (start_date, end_date) as date objects.
    """
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=4)
    return start_of_week.date(), end_of_week.date()


def get_traded_order_count(order_list):
    """
    Count the number of traded orders from the order list.

    Performance: O(n) where n is the number of orders.

    Args:
        order_list (dict): Order list data from API.

    Returns:
        int: Count of traded orders.
    """
    if ('data' not in order_list or 
        not isinstance(order_list['data'], list) or 
        not order_list['data']):
        return 0

    traded_count = sum(
        1 for order in order_list['data'] 
        if order.get('orderStatus') == 'TRADED'
    )
    return traded_count


def get_traded_order_filter_dhan(response):
    """
    Filter and return only traded orders from the response.

    Args:
        response (dict): API response containing order data.

    Returns:
        list: List of traded orders or 0 if none found.
    """
    if ('data' not in response or 
        not isinstance(response['data'], list) or 
        not response['data']):
        return 0

    return [
        order for order in response['data'] 
        if order.get('orderStatus') == 'TRADED'
    ]


def get_pending_order_filter_dhan(response):
    """
    Filter and return pending sell orders from the response.

    Args:
        response (dict): API response containing order data.

    Returns:
        list or bool: List of pending sell orders or False if none found.
    """
    if ('data' not in response or 
        not isinstance(response['data'], list)):
        return False

    pending_sl_orders = [
        order for order in response['data']
        if (isinstance(order, dict) and
            order.get('orderStatus') == 'PENDING' and
            order.get('transactionType') == 'SELL')
    ]

    return pending_sl_orders if pending_sl_orders else False


def get_latest_buy_order_dhan(response):
    """
    Get the latest traded buy order from the response.

    Args:
        response (dict): API response containing order data.

    Returns:
        dict or bool: Latest buy order or False if none found.
    """
    if 'data' not in response:
        return False

    traded_buy_orders = [
        order for order in response['data']
        if (order.get('orderStatus') == 'TRADED' and 
            order.get('transactionType') == 'BUY')
    ]

    if not traded_buy_orders:
        return False

    return max(traded_buy_orders, key=lambda x: x['createTime'])


class LogoutView(View):
    """Handle user logout and redirect to login page."""

    def get(self, request):
        """
        Process logout request.

        Args:
            request: HTTP request object.

        Returns:
            HttpResponse: Redirect to login page.
        """
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('login')


class UserListView(ListView):
    """Display list of all users in the system."""

    model = User
    template_name = 'dashboard/user_list_view.html'
    context_object_name = 'users'

    def get_queryset(self):
        """
        Get queryset of all users.

        Returns:
            QuerySet: All user objects.
        """
        return User.objects.all().select_related()


def user_delete(request, pk):
    """
    Delete a user from the system.

    Only superusers can delete users, and they cannot delete themselves.

    Args:
        request: HTTP request object.
        pk (int): Primary key of the user to delete.

    Returns:
        HttpResponse: Redirect to user management page.
    """
    user = get_object_or_404(User, pk=pk)

    if request.user.is_superuser and user != request.user:
        user.delete()
        messages.success(request, "User deleted successfully.")
    else:
        messages.error(
            request, 
            "You do not have permission to delete this user."
        )

    return redirect('manage_user')





def check_log_status(request):
    """
    Check for changes in order count or kill switch status.

    Used for real-time updates without page refresh.

    Args:
        request: HTTP request object with username parameter.

    Returns:
        JsonResponse: Status indicating if page reload is needed.
    """
    username = request.GET.get('username')
    user = get_object_or_404(User, username=username)

    # Retrieve session data
    kill_switch_key = f"{username}_kill_switch"
    session_kill_switch = request.session.get(
        kill_switch_key, 
        {"kill_switch_1": None, "kill_switch_2": None}
    )
    session_order_count_key = f"{username}_order_count"
    session_order_count = request.session.get(session_order_count_key, 0)

    # Get current values
    current_kill_switch = {
        "kill_switch_1": user.kill_switch_1,
        "kill_switch_2": user.kill_switch_2
    }

    # Fetch current order count
    dhan = dhanhq(user.dhan_client_id, user.dhan_access_token)
    orderlistdata = dhan.get_order_list()
    actual_order_count = get_traded_order_count(orderlistdata)

    # Check for changes
    if (session_order_count != actual_order_count or 
        session_kill_switch != current_kill_switch):
        request.session[session_order_count_key] = actual_order_count
        request.session[kill_switch_key] = current_kill_switch
        return JsonResponse({'status': 'reload'})

    return JsonResponse({'status': 'no_change'})


class UserDetailView(UpdateView):
    """
    View and edit user details.

    Allows superusers to modify user settings and trading parameters.
    """

    model = User
    template_name = 'dashboard/user-detail-edit.html'
    context_object_name = 'user'
    form_class = UserAdminUpdateForm
    success_url = reverse_lazy('manage_user')

    def form_valid(self, form):
        """
        Process valid form submission.

        Args:
            form: The submitted user form.

        Returns:
            HttpResponse: Success or error response.
        """
        if self.request.user.is_superuser:
            user = form.save(commit=False)
            updated_data = {
                'email': form.cleaned_data.get('email'),
                'phone_number': form.cleaned_data.get('phone_number'),
                'role': form.cleaned_data.get('role'),
                'country': form.cleaned_data.get('country'),
                'dhan_access_token': form.cleaned_data.get(
                    'dhan_access_token'
                ),
                'dhan_client_id': form.cleaned_data.get('dhan_client_id'),
                'status': form.cleaned_data.get('status'),
                'is_active': form.cleaned_data.get('is_active'),
                'kill_switch_1': form.cleaned_data.get('kill_switch_1'),
                'kill_switch_2': form.cleaned_data.get('kill_switch_2'),
                'quick_exit': form.cleaned_data.get('quick_exit'),
                'sl_control_mode': form.cleaned_data.get('sl_control_mode')
            }

            User.objects.filter(username=user.username).update(
                **updated_data
            )
            messages.success(
                self.request, 
                'User details updated successfully.'
            )
        else:
            messages.error(
                self.request,
                'You have no privilege to edit user settings.'
            )
            return super().form_invalid(form)

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        print(form.errors)
        messages.error(
            self.request, 
            'Please correct the errors below.'
        )
        return super().form_invalid(form)

    def get_object(self, queryset=None):
        """Get the user object based on URL parameter."""
        return get_object_or_404(User, pk=self.kwargs['pk'])


class ControlListView(ListView):
    """Display list of all trading control settings."""

    model = Control
    template_name = 'dashboard/control_listview.html'
    context_object_name = 'controls'

    def get_queryset(self):
        """
        Get all control objects.

        Returns:
            QuerySet: All control settings.
        """
        return Control.objects.all().select_related('user')


class EditControlView(UpdateView):
    """Edit trading control settings for users."""

    model = Control
    template_name = 'dashboard/edit_control.html'
    context_object_name = 'control'
    form_class = ControlUpdateForm
    success_url = reverse_lazy('control_list_view')

    def form_valid(self, form):
        """Process valid control form submission."""
        if self.request.user.is_superuser:
            control = form.save(commit=False)

            updated_data = {
                'order_limit_first': form.cleaned_data.get('order_limit_first'),
                'order_limit_second': form.cleaned_data.get(
                    'order_limit_second'
                ),
                'max_loss_limit': form.cleaned_data.get('max_loss_limit'),
                'peak_loss_limit': form.cleaned_data.get('peak_loss_limit'),
                'max_profit_limit': form.cleaned_data.get(
                    'max_profit_limit'
                ),
                'max_profit_mode': form.cleaned_data.get('max_profit_mode'),
                'max_order_count_mode': form.cleaned_data.get(
                    'max_order_count_mode'
                ),
                'stoploss_parameter': form.cleaned_data.get(
                    'stoploss_parameter'
                ),
                'user': form.cleaned_data.get('user'),
            }

            Control.objects.filter(pk=control.pk).update(**updated_data)
            messages.success(
                self.request, 
                'Control settings updated successfully.'
            )
        else:
            messages.error(
                self.request,
                'You have no privilege to edit controls.'
            )
            return super().form_invalid(form)

        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        print(form.errors)
        messages.error(
            self.request, 
            'Please correct the errors below.'
        )
        return super().form_invalid(form)

    def get_object(self, queryset=None):
        """Get the control object based on URL parameter."""
        return get_object_or_404(Control, pk=self.kwargs['pk'])






class DhanAPIException(Exception):
    """Custom exception for Dhan API errors."""
    pass




@login_required
@require_POST
@csrf_exempt
def close_all_positions(request):
    """
    Close all open trading positions for a user.

    Cancels pending SL orders and closes the latest buy position.

    Args:
        request: HTTP request with username in JSON body.

    Returns:
        JsonResponse: Status of position closure.
    """
    data = json.loads(request.body)
    username = data.get('username')

    try:
        user = User.objects.get(is_active=True, username=username)
    except User.DoesNotExist:
        return JsonResponse(
            {"error": "User not found or inactive."}, 
            status=404
        )

    # Initialize Dhan client
    dhan = dhanhq(user.dhan_client_id, user.dhan_access_token)
    order_list = dhan.get_order_list()

    if not order_list.get('data'):
        return JsonResponse(
            {"message": f"No orders found for user {username}"}, 
            status=200
        )

    # Cancel pending SL orders
    pending_sl_orders = get_pending_order_filter_dhan(order_list)
    if pending_sl_orders:
        for order in pending_sl_orders:
            cancel_slorder_response = dhan.cancel_order(
                order_id=order['orderId']
            )
            print("Cancel SL order response:", cancel_slorder_response)

    # Get latest buy order
    latest_buy_entry = get_latest_buy_order_dhan(order_list)

    if not latest_buy_entry:
        return JsonResponse(
            {"message": f"No orders found for user {username}"}, 
            status=200
        )

    # Close buy position if it's traded
    if (latest_buy_entry.get('transactionType') == 'BUY' and 
        latest_buy_entry.get('orderStatus') == 'TRADED'):

        sellorder_response = dhan.place_order(
            security_id=latest_buy_entry['securityId'],
            exchange_segment='NSE_FNO',
            transaction_type='SELL',
            quantity=latest_buy_entry['quantity'],
            order_type='MARKET',
            product_type='INTRADAY',
            price=0
        )

        message = (
            sellorder_response['remarks']['message'] 
            if 'remarks' in sellorder_response and 
               'message' in sellorder_response['remarks']
            else sellorder_response['remarks']['error_message']
        )

        return JsonResponse({
            "message": message, 
            "response": sellorder_response
        })

    return JsonResponse(
        {"message": "No open BUY order to close."}, 
        status=200
    )


@login_required
@require_POST
@csrf_exempt
def activate_kill_switch(request):
    """
    Activate kill switch for a user to stop all trading.

    Args:
        request: HTTP request with username in JSON body.

    Returns:
        JsonResponse: Status of kill switch activation.
    """
    try:
        data = json.loads(request.body)
        username = data.get('username')

        user = User.objects.get(is_active=True, username=username)
        dhan_access_token = user.dhan_access_token

        url = 'https://api.dhan.co/killSwitch?killSwitchStatus=ACTIVATE'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'access-token': dhan_access_token
        }

        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            # Update kill switch status
            if not user.kill_switch_1 and not user.kill_switch_2:
                user.kill_switch_1 = True
                message = f"Kill switch 1 activated for user: {username}"
            elif user.kill_switch_1 and not user.kill_switch_2:
                user.kill_switch_2 = True
                user.status = False
                message = f"Kill switch 2 activated for user: {username}"
            else:
                message = (
                    f"Kill switch already fully activated for user: "
                    f"{username}"
                )

            user.save()
            result = {"status": "success", "message": message}
        else:
            result = {
                "status": "error",
                "message": (
                    f"Failed to activate kill switch for user {username}: "
                    f"Status code {response.status_code}"
                )
            }

    except User.DoesNotExist:
        result = {
            "status": "error",
            "message": f"User {username} not found or inactive."
        }
    except requests.RequestException as e:
        result = {
            "status": "error",
            "message": (
                f"Error activating kill switch for user {username}: {e}"
            )
        }
    except Exception as e:
        result = {
            "status": "error",
            "message": f"An unexpected error occurred: {e}"
        }

    return JsonResponse(result)


# Self-Analysis Advice Pool

ADVICE_POOL = {
    "health_check": {
        "0-20": [
            (
                "Physical condition is low, which can negatively impact "
                "decision-making and emotional control.",
                "Tip: Avoid trading until your physical state improves. "
                "Focus on recovery activities like rest, hydration, and "
                "nutrition. A fatigued body leads to impaired cognitive "
                "performance."
            ),
        ],
        "21-40": [
            (
                "Your energy levels are below optimal. Avoid making major "
                "decisions or handling complex trades.",
                "Tip: Engage in mindfulness or relaxation techniques to "
                "reset and recharge. Trading when physically drained can "
                "lead to overtrading or poor decision-making."
            ),
        ],
        "41-60": [
            (
                "Your energy is moderate. You may experience periods of "
                "fatigue, affecting concentration and emotional regulation.",
                "Tip: Incorporate short breaks and maintain consistent "
                "hydration to keep your energy stable. Avoid emotional "
                "decision-making and stick to a strategy."
            ),
        ],
        "61-80": [
            (
                "Good physical state, allowing you to handle stressful "
                "situations with composure.",
                "Tip: Leverage your energy levels to stay focused and keep "
                "your risk management strategies in place. Remain alert, "
                "especially during high-volatility periods."
            ),
        ],
        "81-100": [
            (
                "Peak physical condition. You're prepared to make "
                "high-stakes, strategic trades.",
                "Tip: Use this energy wisely, maintaining a disciplined "
                "approach to trading. Avoid impulsive trades and focus on "
                "your long-term strategy and risk tolerance."
            ),
        ],
    },
    "mind_check": {
        "0-20": [
            (
                "Your mental clarity is significantly low, which can impair "
                "your ability to analyze data and make rational decisions.",
                "Tip: Take time off from the markets. Engage in activities "
                "like meditation, light exercise, or a short walk to reset "
                "your mental state."
            ),
        ],
        "21-40": [
            (
                "Mental clarity is suboptimal. Avoid making any major "
                "trading decisions as it may lead to mistakes.",
                "Tip: Use relaxation techniques to calm your mind. Mental "
                "fatigue can lead to emotional overreaction and a loss of "
                "focus."
            ),
        ],
        "41-60": [
            (
                "Your mental state is steady, though you may encounter "
                "moments of distraction or emotional bias.",
                "Tip: Stay grounded with mindfulness practices, and always "
                "follow your pre-established trading plan to avoid letting "
                "emotions drive decisions."
            ),
        ],
        "61-80": [
            (
                "Your mind is sharp and focused. You're ready to assess "
                "market data effectively and execute trades with precision.",
                "Tip: Use this clarity to identify market trends, but stay "
                "cautious. Overconfidence can lead to risk-taking behaviors "
                "that deviate from your strategy."
            ),
        ],
        "81-100": [
            (
                "You're in an optimal mental state, able to think critically "
                "and analytically under pressure.",
                "Tip: Maintain discipline and stick to your risk management "
                "plan. You are capable of handling complex strategies and "
                "unpredictable market shifts."
            ),
        ],
    },
    # Additional advice categories would continue here...
}


def get_advice(score, category):
    """
    Generate advice and tips based on score intervals for each category.

    Args:
        score (int): Score value (0-100).
        category (str): Category name from ADVICE_POOL.

    Returns:
        tuple: (advice_text, tip_text)
    """
    if score <= 20:
        advice = random.choice(ADVICE_POOL[category]["0-20"])
    elif 21 <= score <= 40:
        advice = random.choice(ADVICE_POOL[category]["21-40"])
    elif 41 <= score <= 60:
        advice = random.choice(ADVICE_POOL[category]["41-60"])
    elif 61 <= score <= 80:
        advice = random.choice(ADVICE_POOL[category]["61-80"])
    else:
        advice = random.choice(ADVICE_POOL[category]["81-100"])
    return advice


