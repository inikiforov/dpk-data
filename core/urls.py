"""
URL routes for dpk-data.
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
    
    # ── Public Data API (no auth, CORS-restricted) ──────────────
    path('data/', api_views.api_index, name='api_index'),
    
    # Active portfolio (ID=2)
    path('data/active/performance/', api_views.api_active_performance, name='api_active_performance'),
    path('data/active/chart-performance/', api_views.api_active_chart_performance, name='api_active_chart_performance'),
    path('data/active/chart-value/', api_views.api_active_chart_value, name='api_active_chart_value'),
    path('data/active/holdings/', api_views.api_active_current_holdings, name='api_active_current_holdings'),
    path('data/active/closed-positions/', api_views.api_active_closed_positions, name='api_active_closed_positions'),
    
    # Passive portfolio (ID=1) — % only, no dollar values
    path('data/passive/performance-summary/', api_views.api_passive_performance_summary, name='api_passive_performance_summary'),
    path('data/passive/chart-performance/', api_views.api_passive_chart_performance, name='api_passive_chart_performance'),
    path('data/passive/holdings-summary/', api_views.api_passive_holdings_summary, name='api_passive_holdings_summary'),
    
    # Fintest — Public Financial Literacy Quiz
    path('fintest/', views.fintest, name='fintest'),
    path('fintest/api/questions/', views.fintest_questions, name='fintest_questions'),
    path('fintest/api/submit/', views.fintest_submit, name='fintest_submit'),

    # Legacy endpoints (backward compatibility)
    path('data/active-performance/', api_views.api_active_performance),
    path('data/active-current-holdings/', api_views.api_active_current_holdings),
    path('data/active-performance-chart-weekly/', api_views.api_active_chart_performance),
]
