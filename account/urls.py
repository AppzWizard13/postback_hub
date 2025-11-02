from . import views
from django.urls import path
from django.contrib import admin
from account.views import UserloginView, DashboardView, HomePageView
from django.contrib.auth import views as auth_views
from .views import (
    UserListView, UserDetailView, ControlListView, UserCreateView, 
    ControlCreateView, EditControlView
)

urlpatterns = [
    # ============================================================
    # AUTHENTICATION & LANDING PAGE
    # ============================================================
    path('', views.HomePageView.as_view(), name='home'),
    path('login/', views.UserloginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # ============================================================
    # DASHBOARD
    # ============================================================
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/<slug:slug>/', DashboardView.as_view(), name='dashboard'),
    
    # ============================================================
    # USER MANAGEMENT
    # ============================================================
    path('users/', UserListView.as_view(), name='manage_user'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('user-registration/', UserCreateView.as_view(), name='user_registration'),
    path('delete/<int:pk>/', views.user_delete, name='user_delete'),
    
    # ============================================================
    # CONTROL MANAGEMENT
    # ============================================================
    path('controls/', ControlListView.as_view(), name='control_list_view'),
    path('controls/<int:pk>/', EditControlView.as_view(), name='edit-control'),
    path('create-control/', ControlCreateView.as_view(), name='create_control'),
    
    # ============================================================
    # TRADING OPERATIONS
    # ============================================================
    path('close-all-positions/', views.close_all_positions, name='close_all_positions'),
    path('activate_kill_switch/', views.activate_kill_switch, name='activate_kill_switch'),
    path('check-log-status/', views.check_log_status, name='check_log_status'),
    
]


# ============================================================
# WEBSOCKET URL PATTERNS
# ============================================================
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/orders/<str:username>/", consumers.OrderUpdateConsumer.as_asgi()),
]
