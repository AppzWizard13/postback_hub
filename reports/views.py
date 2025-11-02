from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, TemplateView, CreateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.utils.dateparse import parse_date
from datetime import date, timedelta
from decimal import Decimal
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import (
    DhanKillProcessLog, OrderHistoryLog, DailyAccountOverview,
    DailySelfAnalysis, WeeklyGoalReport, DailyGoalReport, TradingPlan, User
)
from .forms import DailySelfAnalysisForm, TradingPlanForm
from dhanhq import dhanhq


# ============================================================
# LOGS & HISTORY VIEWS
# ============================================================

class DhanKillProcessLogListView(LoginRequiredMixin, ListView):
    """Display list of Dhan kill process log entries."""
    
    model = DhanKillProcessLog
    template_name = 'dashboard/dhan_kill_process_log_list.html'
    context_object_name = 'logs'
    paginate_by = 10
    
    def get_queryset(self):
        """Get queryset of log entries ordered by creation date."""
        return DhanKillProcessLog.objects.all().order_by('-created_on')


class ClearKillLogView(LoginRequiredMixin, TemplateView):
    """Clear all kill process log entries."""
    
    def get(self, request, *args, **kwargs):
        """Handle GET request to clear logs."""
        DhanKillProcessLog.objects.all().delete()
        messages.success(
            request,
            "All log data has been cleared successfully."
        )
        return redirect('dhan-kill-log-list')


class OrderHistoryListView(LoginRequiredMixin, ListView):
    """
    Display order history with date filtering.
    
    Fetches from database for historical dates and from API for current date.
    """
    
    model = OrderHistoryLog
    template_name = 'dashboard/order_history_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Get order history from DB or API based on selected date."""
        user_id = self.request.GET.get('user_id')
        if user_id:
            self.user = User.objects.filter(id=user_id).first()
        else:
            self.user = self.request.user
        
        selected_date = self.request.GET.get('date')
        selected_date_parsed = (
            parse_date(selected_date) if selected_date else None
        )
        current_date = date.today()
        
        # Fetch from API for current date
        if selected_date_parsed is None or selected_date_parsed == current_date:
            dhan = dhanhq(
                self.user.dhan_client_id,
                self.user.dhan_access_token
            )
            self.orderlistdata = dhan.get_order_list()
            return OrderHistoryLog.objects.none()
        
        # Fetch from database for historical dates
        queryset = OrderHistoryLog.objects.all()
        if selected_date_parsed:
            queryset = queryset.filter(date=selected_date_parsed)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add order list and user data to context."""
        context = super().get_context_data(**kwargs)
        context['user_list'] = User.objects.all()
        
        if hasattr(self, 'orderlistdata'):
            context['orderlistdata'] = self.orderlistdata
        
        context['user'] = self.user
        context['today'] = date.today()
        return context


class TradeHistoryListView(LoginRequiredMixin, TemplateView):
    """
    Display trade history with date range filtering.
    
    Fetches trade data from Dhan API for specified date range.
    """
    
    template_name = 'dashboard/trade_history_list.html'
    
    def get_context_data(self, **kwargs):
        """Fetch and process trade history data."""
        context = super().get_context_data(**kwargs)
        
        # Get user
        user_id = self.request.GET.get('user_id')
        if user_id:
            self.user = User.objects.filter(id=user_id).first()
        else:
            self.user = self.request.user
        
        # Validate user credentials exist
        if not self.user.dhan_client_id or not self.user.dhan_access_token:
            context['error_message'] = "Dhan API credentials not found. Please configure your API settings."
            context['user_list'] = User.objects.all()
            context['trade_history'] = []
            return context
        
        # Parse and validate dates
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        start_date_parsed = parse_date(start_date) if start_date else None
        end_date_parsed = parse_date(end_date) if end_date else None
        
        current_date = date.today()
        if not start_date_parsed:
            start_date_parsed = current_date
        if not end_date_parsed:
            end_date_parsed = current_date
        
        if start_date_parsed > end_date_parsed:
            end_date_parsed = start_date_parsed
        
        # Format dates for API
        from_date_str = start_date_parsed.strftime('%Y-%m-%d')
        to_date_str = end_date_parsed.strftime('%Y-%m-%d')
        
        # Initialize default context values
        context['user_list'] = User.objects.all()
        context['selected_start_date'] = start_date_parsed
        context['selected_end_date'] = end_date_parsed
        context['trade_history'] = []
        context['total_charges'] = 0
        context['total_order_counts'] = 0
        
        try:
            # Fetch trade history from API
            dhan = dhanhq(
                self.user.dhan_client_id,
                self.user.dhan_access_token
            )
            
            response = dhan.get_trade_history(
                from_date_str, to_date_str, page_number=0
            )
            
            # Check response structure and status
            if isinstance(response, dict):
                # Handle error response structure
                if response.get('status') == 'failure':
                    error_data = response.get('data', {})
                    error_code = error_data.get('errorCode')
                    error_message = error_data.get('errorMessage', 'Unknown error')
                    
                    if error_code == 'DH-901':
                        context['error_message'] = (
                            "Authentication Failed: Your Dhan access token has expired. "
                            "Please generate a new access token from your Dhan profile and update it in settings."
                        )
                        context['error_type'] = 'authentication'
                        context['token_expired'] = True
                    else:
                        context['error_message'] = f"API Error ({error_code}): {error_message}"
                    
                    return context
                
                # Success response
                trade_history = response.get('data', [])
            else:
                trade_history = []
            
            # Calculate charges for each trade
            total_charges = 0
            for trade in trade_history:
                charges = sum([
                    float(trade.get('sebiTax', 0) or 0),
                    float(trade.get('stt', 0) or 0),
                    float(trade.get('brokerageCharges', 0) or 0),
                    float(trade.get('serviceTax', 0) or 0),
                    float(trade.get('exchangeTransactionCharges', 0) or 0),
                    float(trade.get('stampDuty', 0) or 0)
                ])
                trade['charges'] = charges
                total_charges += charges
            
            # Update context with successful data
            context['trade_history'] = trade_history
            context['total_charges'] = total_charges
            context['total_order_counts'] = len(trade_history)
            
        except Exception as e:
            # Handle any unexpected errors
            context['error_message'] = f"Error fetching trade history: {str(e)}"
            print(f"Trade history error: {str(e)}")
        
        return context


# ============================================================
# REPORTS & ANALYSIS VIEWS
# ============================================================

class DailyAccountOverviewListView(LoginRequiredMixin, ListView):
    """
    Display and filter daily account overview records.
    
    Supports filtering by:
    - User
    - Date range
    - Day open/close status
    """
    
    model = DailyAccountOverview
    template_name = 'dashboard/dailyaccountoverview.html'
    context_object_name = 'daily_account_overviews'
    paginate_by = 20
    
    def get_queryset(self):
        """Get filtered queryset based on GET parameters."""
        queryset = DailyAccountOverview.objects.all().order_by(
            '-updated_on'
        ).select_related('user')
        
        # Filter by user
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            start_date_parsed = parse_date(start_date)
            if start_date_parsed:
                queryset = queryset.filter(
                    updated_on__date__gte=start_date_parsed
                )
        
        if end_date:
            end_date_parsed = parse_date(end_date)
            if end_date_parsed:
                queryset = queryset.filter(
                    updated_on__date__lte=end_date_parsed
                )
        
        # Filter by day status
        day_open = self.request.GET.get('day_open')
        day_close = self.request.GET.get('day_close')
        
        if day_open is not None:
            queryset = queryset.filter(
                day_open=(day_open.lower() == 'true')
            )
        if day_close is not None:
            queryset = queryset.filter(
                day_close=(day_close.lower() == 'true')
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add filter context to template."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Daily Account Overview'
        context['user_list'] = User.objects.all()
        context['selected_user'] = self.request.GET.get('user_id', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['day_open'] = self.request.GET.get('day_open', '')
        context['day_close'] = self.request.GET.get('day_close', '')
        return context


class DailySelfAnalysisView(LoginRequiredMixin, TemplateView):
    """
    Handle daily self-analysis form submission and display.
    
    Generates personalized advice based on user's self-assessment scores.
    """
    
    template_name = 'dashboard/daily_selfanalysis.html'
    
    def get_context_data(self, **kwargs):
        """Add form and advice to context."""
        context = super().get_context_data(**kwargs)
        context['form'] = DailySelfAnalysisForm()
        context['advice_list'] = self.request.session.pop('advice_list', None)
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle form submission."""
        form = DailySelfAnalysisForm(request.POST)
        
        if form.is_valid():
            today = now().date()
            
            # Check if analysis already exists for today
            existing_analysis = DailySelfAnalysis.objects.filter(
                user=request.user,
                date_time__date=today
            ).first()
            
            if existing_analysis:
                messages.error(
                    request,
                    "You have already submitted your self-analysis for today."
                )
                return redirect('daily_self_analysis')
            
            # Create new analysis
            analysis = form.save(commit=False)
            analysis.user = request.user
            
            # Calculate overall score
            overall_score = (
                analysis.health_check +
                analysis.mind_check +
                analysis.expectation_level +
                analysis.patience_level +
                analysis.previous_day_self_analysis
            ) // 5
            
            # Generate advice for each category
            advice_health = self.get_advice(
                analysis.health_check, "health_check"
            )
            advice_mind = self.get_advice(analysis.mind_check, "mind_check")
            
            # Compile all advice
            advice_list = [advice_health, advice_mind]
            request.session['advice_list'] = advice_list
            
            # Save advice to model
            analysis.overall_advice = ', '.join(
                str(advice) for advice in advice_list
            )
            analysis.save()
            
            messages.success(
                request,
                "Your self-analysis was submitted successfully."
            )
            return redirect('daily_self_analysis')
        else:
            messages.error(
                request,
                "There was an error with your submission."
            )
            return self.render_to_response(self.get_context_data(form=form))
    
    def get_advice(self, score, category):
        """
        Generate advice based on score and category.
        
        Args:
            score (int): Score value
            category (str): Category name
            
        Returns:
            str: Advice message
        """
        # Implement your advice logic here
        if score >= 8:
            return f"{category}: Excellent condition!"
        elif score >= 5:
            return f"{category}: Good, but room for improvement."
        else:
            return f"{category}: Needs attention."


@method_decorator(csrf_exempt, name='dispatch')
class SaveGoalReportsView(LoginRequiredMixin, TemplateView):
    """Save weekly and daily goal reports."""
    
    def post(self, request, *args, **kwargs):
        """Handle POST request to save goal reports."""
        try:
            data = json.loads(request.body)
            weekly_data = data.get("weekly_data", [])
            daily_data = data.get("daily_data", [])
            
            # Save weekly reports
            for week in weekly_data:
                weekly_report, created = (
                    WeeklyGoalReport.objects.update_or_create(
                        user=request.user,
                        week_number=week["week_number"],
                        plan_name=week["plan_name"],
                        defaults={
                            "start_date": week["start_date"],
                            "end_date": week["end_date"],
                            "accumulated_capital": week["accumulated_capital"],
                            "gained_amount": week["gained_amount"],
                            "progress": week.get("progress", None),
                            "is_achieved": week.get("is_achieved", False),
                        },
                    )
                )
            
            # Save daily reports
            for day in daily_data:
                weekly_goal = WeeklyGoalReport.objects.get(
                    user=request.user,
                    week_number=day["week_number"],
                    plan_name=day["plan_name"]
                )
                DailyGoalReport.objects.update_or_create(
                    user=request.user,
                    weekly_goal=weekly_goal,
                    day_number=day["day_number"],
                    date=day["date"],
                    plan_name=day["plan_name"],
                    defaults={
                        "capital": day["capital"],
                        "gained_amount": day.get("gained_amount", None),
                        "is_achieved": day.get("is_achieved", False),
                        "progress": day.get("progress", None),
                    },
                )
            
            return JsonResponse({
                "success": True,
                "message": "Reports saved successfully!"
            })
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": f"Error saving reports: {e}"
            }, status=400)


# ============================================================
# TRADING PLAN VIEWS
# ============================================================

class CreateTradePlanView(LoginRequiredMixin, TemplateView):
    """Create a new trading plan."""
    
    template_name = 'dashboard/trade_planner.html'
    
    def get_context_data(self, **kwargs):
        """Add form to context."""
        context = super().get_context_data(**kwargs)
        context['form'] = TradingPlanForm()
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle POST request to create trading plan."""
        form = TradingPlanForm(request.POST)
        
        if form.is_valid():
            plan_name = form.cleaned_data['plan_name']
            
            # Check for duplicate plan name
            if TradingPlan.objects.filter(plan_name=plan_name).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': (
                        f'Trading plan with the name "{plan_name}" already exists.'
                    )
                })
            
            try:
                trade_plan = form.save(commit=False)
                trade_plan.user = request.user
                trade_plan.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Trade plan saved successfully!'
                })
            except Exception as e:
                print(f"Error saving trade plan: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'There was an error saving the trade plan: {e}'
                })
        else:
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(error)
            
            return JsonResponse({
                'status': 'error',
                'message': error_messages
            })


class TradePlanListView(LoginRequiredMixin, ListView):
    """Display list of all trading plans."""
    
    model = TradingPlan
    template_name = 'dashboard/trade_plan_listview.html'
    context_object_name = 'trading_plans'
    
    def get_queryset(self):
        """Get all trading plans with user relationship."""
        return TradingPlan.objects.all().select_related('user')


class ViewTradePlanDetailView(LoginRequiredMixin, DetailView):
    """Display details of a specific trading plan with goals."""
    
    model = TradingPlan
    template_name = 'dashboard/view_trade_plan.html'
    context_object_name = 'trading_plan'
    
    def get_context_data(self, **kwargs):
        """Add weekly and daily goals to context."""
        context = super().get_context_data(**kwargs)
        
        # Fetch related goals
        weekly_goals = WeeklyGoalReport.objects.filter(
            plan_id=self.object.pk
        ).order_by('week_number')
        
        daily_goals = DailyGoalReport.objects.filter(
            weekly_goal__plan_id=self.object.pk
        ).order_by('date')
        
        # Calculate progress percentages
        for goal in daily_goals:
            if goal.progress != 0:
                goal.progress_percentage = (
                    (goal.progress / goal.gained_amount) * 100
                )
            else:
                goal.progress_percentage = 0
        
        context['weekly_goals'] = weekly_goals
        context['daily_goals'] = daily_goals
        
        return context


class GenerateTradingPlanView(LoginRequiredMixin, TemplateView):
    """Generate weekly and daily goal reports for a trading plan."""
    
    def get(self, request, plan_id, *args, **kwargs):
        """Handle GET request to generate trading plan."""
        trading_plan = get_object_or_404(TradingPlan, id=plan_id)
        
        # Extract plan data
        user = trading_plan.user
        initial_capital = Decimal(trading_plan.initial_capital)
        average_weekly_gain = Decimal(trading_plan.average_weekly_gain)
        no_of_weeks = trading_plan.no_of_weeks
        start_date = trading_plan.start_date
        
        # Clear existing reports
        WeeklyGoalReport.objects.filter(
            user=user, plan_id=plan_id
        ).delete()
        
        weeks_growth_rate = Decimal(1 + (average_weekly_gain / 100))
        accumulated_capital = initial_capital
        current_date = start_date
        
        # Generate reports for each week
        for week_number in range(1, no_of_weeks + 1):
            # Calculate week start (Monday) and end (Friday)
            while current_date.weekday() != 0:
                current_date += timedelta(days=1)
            monday_date = current_date
            friday_date = monday_date + timedelta(days=4)
            
            # Calculate weekly gain
            weekly_gain = (
                accumulated_capital * (weeks_growth_rate - 1)
            ).quantize(Decimal('0.01'))
            accumulated_capital += weekly_gain
            
            # Create weekly goal report
            weekly_goal = WeeklyGoalReport.objects.create(
                user=user,
                plan_id=plan_id,
                week_number=week_number,
                start_date=monday_date,
                end_date=friday_date,
                accumulated_capital=accumulated_capital,
                gained_amount=weekly_gain,
                progress=0,
                is_achieved=False,
            )
            
            # Generate daily reports
            daily_gain = Decimal(
                (weekly_gain / 5).quantize(Decimal('0.01'))
            )
            
            for day in range(5):
                daily_date = monday_date + timedelta(days=day)
                day_capital = Decimal(
                    accumulated_capital - (5 - day) * daily_gain
                )
                
                DailyGoalReport.objects.create(
                    user=user,
                    weekly_goal=weekly_goal,
                    plan_id=plan_id,
                    day_number=(week_number - 1) * 5 + day + 1,
                    date=daily_date,
                    capital=day_capital,
                    gained_amount=daily_gain,
                    progress=0,
                    is_achieved=False,
                )
            
            current_date += timedelta(days=7)
        
        # Mark plan as active
        trading_plan.is_active = True
        trading_plan.save()
        
        messages.success(
            request,
            f"Trading plan '{trading_plan.plan_name}' successfully processed and reports generated."
        )
        return redirect('trade_plan_list_view')


class DeleteTradingPlanView(LoginRequiredMixin, DeleteView):
    """Delete a trading plan and all related reports."""
    
    model = TradingPlan
    success_url = reverse_lazy('trade_plan_list_view')
    pk_url_kwarg = 'plan_id'
    
    def delete(self, request, *args, **kwargs):
        """Handle deletion with related reports cleanup."""
        self.object = self.get_object()
        plan_id = self.object.id
        user = self.object.user
        plan_name = self.object.plan_name
        
        # Delete related reports
        DailyGoalReport.objects.filter(
            weekly_goal__plan_id=plan_id, user=user
        ).delete()
        
        WeeklyGoalReport.objects.filter(
            plan_id=plan_id, user=user
        ).delete()
        
        # Delete the plan
        self.object.delete()
        
        messages.success(
            request,
            f"Trading plan '{plan_name}' and related reports have been successfully deleted."
        )
        return redirect(self.success_url)
