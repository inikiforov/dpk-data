"""
Public JSON API views for WordPress consumption.
No authentication required. CORS restricted to delopahnetkerosinom.ru.
"""
from django.http import JsonResponse

ALLOWED_ORIGIN = 'https://delopahnetkerosinom.ru'


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


def api_active_performance(request):
    """Yearly performance data for the active portfolio."""
    if request.method == 'OPTIONS':
        return cors_preflight()

    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)

    data = PortfolioEngineV3.get_yearly_performance(portfolio)
    return cors_response({'data': data})


def api_active_current_holdings(request):
    """Current holdings for the active portfolio."""
    if request.method == 'OPTIONS':
        return cors_preflight()

    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)

    data = PortfolioEngineV3.get_current_holdings(portfolio)
    return cors_response({'data': data})


def api_active_performance_chart_weekly(request):
    """Weekly chart data (NAV % return and portfolio value) for the active portfolio."""
    if request.method == 'OPTIONS':
        return cors_preflight()

    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    if not portfolio:
        return cors_response({'error': 'Portfolio not found'}, status=404)

    data = PortfolioEngineV3.get_weekly_chart_data(portfolio)
    return cors_response(data)
