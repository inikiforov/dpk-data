"""
URL routes for dpk-blog.
Includes: index, portfolio, settings, public data API.
"""
from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Public pages (staff only)
    path('', views.index, name='index'),
    path('open/', views.portfolio_public, name='portfolio_public'),
    path('open/chart-embed/', views.portfolio_chart_embed, name='portfolio_chart_embed'),
    path('open/embed/return/', views.embed_return_chart, name='embed_return_chart'),
    path('open/embed/value/', views.embed_value_chart, name='embed_value_chart'),
    path('open/embed/holdings/', views.embed_holdings, name='embed_holdings'),
    
    # Portfolio management (staff only)
    path('lab/portfolio-v3/', views.lab_portfolio_v3, name='lab_portfolio_v3'),
    path('lab/settings/', views.lab_settings, name='lab_settings'),
    path('lab/settings/update-prices/', views.lab_update_prices, name='lab_update_prices'),
    
    # Public data API (no auth, CORS-restricted)
    path('data/active-performance/', api_views.api_active_performance, name='api_active_performance'),
    path('data/active-current-holdings/', api_views.api_active_current_holdings, name='api_active_current_holdings'),
    path('data/active-performance-chart-weekly/', api_views.api_active_performance_chart_weekly, name='api_active_performance_chart_weekly'),
]
