"""
Public JSON API views for WordPress consumption.
No authentication required. CORS restricted to delopahnetkerosinom.ru.
"""
from django.http import JsonResponse, HttpResponse


def api_index(request):
    """Public API documentation page with clickable endpoint links."""
    html = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>dpk-data API</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 720px; margin: 0 auto; padding: 2rem 1rem; color: #222; }
  h1 { font-size: 1.4rem; margin-bottom: 0.3rem; }
  .subtitle { color: #888; margin-bottom: 2rem; font-size: 0.9rem; }
  h2 { font-size: 1.1rem; margin: 2rem 0 0.8rem; border-bottom: 1px solid #eee; padding-bottom: 0.3rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { text-align: left; padding: 6px 8px; border-bottom: 2px solid #333; }
  td { padding: 6px 8px; border-bottom: 1px solid #eee; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .note { color: #888; font-size: 0.8rem; margin-top: 2rem; }
</style>
</head><body>
<h1>dpk-data API</h1>
<p class="subtitle">Public JSON endpoints for portfolio data</p>

<h2>Active Portfolio</h2>
<table>
<tr><th>Endpoint</th><th>Description</th></tr>
<tr><td><a href="/data/active/performance/">/data/active/performance/</a></td><td>Yearly returns (newest first)</td></tr>
<tr><td><a href="/data/active/chart-performance/">/data/active/chart-performance/</a></td><td>Weekly NAV % chart data</td></tr>
<tr><td><a href="/data/active/chart-value/">/data/active/chart-value/</a></td><td>Weekly $ value chart data</td></tr>
<tr><td><a href="/data/active/holdings/">/data/active/holdings/</a></td><td>Current holdings (full)</td></tr>
<tr><td><a href="/data/active/closed-positions/">/data/active/closed-positions/</a></td><td>Closed positions with realized P&amp;L</td></tr>
</table>

<h2>Passive Portfolio <span style="font-weight:normal; color:#888;">(% only)</span></h2>
<table>
<tr><th>Endpoint</th><th>Description</th></tr>
<tr><td><a href="/data/passive/performance-summary/">/data/passive/performance-summary/</a></td><td>Year + return % only</td></tr>
<tr><td><a href="/data/passive/chart-performance/">/data/passive/chart-performance/</a></td><td>Weekly NAV % chart data</td></tr>
<tr><td><a href="/data/passive/holdings-summary/">/data/passive/holdings-summary/</a></td><td>Ticker, weight, avg cost, price, P&amp;L %</td></tr>
</table>

<p class="note">CORS: restricted to delopahnetkerosinom.ru &middot; Cache: 5 min</p>
</body></html>"""
    return HttpResponse(html)

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

def api_passive_performance_summary(request):
    """Yearly return % only for the passive portfolio — no NAV or dollar values."""
    if request.method == 'OPTIONS':
        return cors_preflight()
    from .services import PortfolioEngineV3
    portfolio = _get_portfolio('passive')
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)
    full_data = PortfolioEngineV3.get_yearly_performance(portfolio)
    full_data.sort(key=lambda x: x['year'], reverse=True)
    summary = [{'year': d['year'], 'return_pct': round(d['return_pct'], 2)} for d in full_data]
    return cors_response({'data': summary})

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
