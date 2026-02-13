"""
Public JSON API views for WordPress consumption.
No authentication required. CORS restricted to delopahnetkerosinom.ru.
"""
from django.http import JsonResponse

ALLOWED_ORIGIN = 'https://delopahnetkerosinom.ru'

# Portfolio IDs
PORTFOLIO_IDS = {
    'active': 2,
    'passive': 1,
}


def cors_response(data, status=200):
    """Create a JsonResponse with CORS headers."""
    response = JsonResponse(data, status=status)
    response['Access-Control-Allow-Origin'] = ALLOWED_ORIGIN
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Cache-Control'] = 'public, max-age=300'  # 5-minute cache
    return response


def cors_preflight():
    """Handle OPTIONS preflight request."""
    response = JsonResponse({})
    response['Access-Control-Allow-Origin'] = ALLOWED_ORIGIN
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Max-Age'] = '86400'
    return response


def _get_portfolio(portfolio_type):
    """Get portfolio by type ('active' or 'passive')."""
    from .models import Portfolio
    pid = PORTFOLIO_IDS.get(portfolio_type)
    if not pid:
        return None
    return Portfolio.objects.filter(id=pid).first()


# ============================================================
# Generic endpoint builders
# ============================================================

def _yearly_performance(request, portfolio_type):
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio(portfolio_type)
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    data = PortfolioEngineV3.get_yearly_performance(portfolio)
    # Reverse order: current year first
    data.sort(key=lambda x: x['year'], reverse=True)
    return cors_response({'data': data})


def _chart_weekly_performance(request, portfolio_type):
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio(portfolio_type)
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    data = PortfolioEngineV3.get_weekly_chart_data(portfolio)
    return cors_response({'nav_pct': data.get('nav_pct', [])})


def _chart_weekly_value(request, portfolio_type):
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio(portfolio_type)
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    data = PortfolioEngineV3.get_weekly_chart_data(portfolio)
    return cors_response({'value': data.get('value', [])})


def _current_holdings(request, portfolio_type):
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio(portfolio_type)
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    data = PortfolioEngineV3.get_current_holdings(portfolio)
    return cors_response({'data': data})


def _closed_positions(request, portfolio_type):
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio(portfolio_type)
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    data = PortfolioEngineV3.get_closed_positions(portfolio)
    return cors_response({'data': data})


# ============================================================
# Active Portfolio Endpoints (portfolio ID=2)
# ============================================================

def api_active_performance(request):
    """Yearly performance for the active portfolio (current year first)."""
    return _yearly_performance(request, 'active')

def api_active_chart_performance(request):
    """Weekly NAV % return chart for the active portfolio."""
    return _chart_weekly_performance(request, 'active')

def api_active_chart_value(request):
    """Weekly portfolio $ value chart for the active portfolio."""
    return _chart_weekly_value(request, 'active')

def api_active_current_holdings(request):
    """Current holdings for the active portfolio."""
    return _current_holdings(request, 'active')

def api_active_closed_positions(request):
    """Closed positions for the active portfolio."""
    return _closed_positions(request, 'active')


# ============================================================
# Passive Portfolio Endpoints (portfolio ID=1)
# ============================================================

def api_passive_performance(request):
    """Yearly performance for the passive portfolio (current year first)."""
    return _yearly_performance(request, 'passive')

def api_passive_chart_performance(request):
    """Weekly NAV % return chart for the passive portfolio."""
    return _chart_weekly_performance(request, 'passive')

def api_passive_chart_value(request):
    """Weekly portfolio $ value chart for the passive portfolio."""
    return _chart_weekly_value(request, 'passive')

def api_passive_current_holdings(request):
    """Current holdings for the passive portfolio."""
    return _current_holdings(request, 'passive')

def api_passive_holdings_summary(request):
    """Holdings summary for passive portfolio — no dollar values exposed."""
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio('passive')
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    full_data = PortfolioEngineV3.get_current_holdings(portfolio)
    # Strip dollar values, keep only: ticker, weight, avg cost, price, P&L %
    summary = [{
        'ticker': h['ticker'],
        'weight_pct': h.get('weight_pct', 0),
        'avg_cost': round(h.get('avg_cost', 0), 2),
        'current_price': round(h.get('current_price', 0), 2),
        'pnl_pct': round(h.get('unrealized_pnl_pct', 0), 2),
    } for h in full_data]
    return cors_response({'data': summary})

def api_passive_closed_positions(request):
    """Closed positions for the passive portfolio."""
    return _closed_positions(request, 'passive')
