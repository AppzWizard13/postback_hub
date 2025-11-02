
from django.urls import path
from django.contrib import admin
from account.views import UserloginView, DashboardView, HomePageView
from django.contrib.auth import views as auth_views

from reports import views

urlpatterns = [
    # ============================================================
    # LOGS & HISTORY
    # ============================================================
    path('dhan_kill_logs/', views.DhanKillProcessLogListView.as_view(), name='dhan-kill-log-list'),
    path('clear-kill-log/', views.ClearKillLogView.as_view(), name='clear_kill_log'),
    path('order-history/', views.OrderHistoryListView.as_view(), name='order_history'),
    path('trade-history/', views.TradeHistoryListView.as_view(), name='trade_history'),
    
    # ============================================================
    # REPORTS & ANALYSIS
    # ============================================================
    # Daily Reports
    path('daily-account-overview/', views.DailyAccountOverviewListView.as_view(), name='daily_account_overview_list'),
    path('daily-self-analysis/', views.DailySelfAnalysisView.as_view(), name='daily_self_analysis'),
    
    # Goal Reports
    path('save-goal-reports/', views.SaveGoalReportsView.as_view(), name='save_goal_reports'),
    
    # Trading Plan Reports
    path('create-trade-plan/', views.CreateTradePlanView.as_view(), name='create_trade_plan'),
    path('trade-plan-list/', views.TradePlanListView.as_view(), name='trade_plan_list_view'),
    path('view-trade-plan/<int:pk>/', views.ViewTradePlanDetailView.as_view(), name='view_trade_plan'),
    path('generate-trading-plan/<int:plan_id>/', views.GenerateTradingPlanView.as_view(), name='generate-trading-plan'),
    path('delete-trading-plan/<int:plan_id>/', views.DeleteTradingPlanView.as_view(), name='delete-trading-plan'),
]
