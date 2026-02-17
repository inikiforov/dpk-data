"""
Views for dpk-data: index, portfolio, and settings.
All views require staff/admin login.
"""
import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.admin.views.decorators import staff_member_required
from decimal import Decimal


@staff_member_required
def index(request):
    """Homepage with links to tools."""
    return render(request, 'core/index.html')


# ============================================================
# Portfolio Views
# ============================================================

@staff_member_required
def portfolio_public(request):
    """
    Public portfolio view - read-only, no login required.
    Shows the ACTIVE portfolio performance data for public viewing.
    """
    from .models import Portfolio
    from .services import PortfolioEngineV3
    
    # Always show the active portfolio (ID=2)
    portfolio = Portfolio.objects.filter(id=2).first()
    
    context = {
        'portfolio': portfolio,
        'weekly_chart_data': {'nav_pct': [], 'value': []},
        'summary': None,
        'yearly_performance': [],
        'current_holdings': [],
        'closed_positions': [],
    }
    
    if portfolio:
        context['weekly_chart_data'] = PortfolioEngineV3.get_weekly_chart_data(portfolio)
        context['summary'] = PortfolioEngineV3.get_summary(portfolio)
        context['yearly_performance'] = PortfolioEngineV3.get_yearly_performance(portfolio)
        context['current_holdings'] = PortfolioEngineV3.get_current_holdings(portfolio)
        context['closed_positions'] = PortfolioEngineV3.get_closed_positions(portfolio)
    
    return render(request, 'core/portfolio_public.html', context)


@staff_member_required
@xframe_options_exempt
def portfolio_chart_embed(request):
    """Embeddable chart-only view for iframe use on external sites (e.g. WordPress)."""
    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    weekly_chart_data = PortfolioEngineV3.get_weekly_chart_data(portfolio) if portfolio else {'nav_pct': [], 'value': []}

    return render(request, 'core/portfolio_embed.html', {
        'weekly_chart_data': weekly_chart_data,
    })


@staff_member_required
@xframe_options_exempt
def embed_return_chart(request):
    """Embeddable return % chart only."""
    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    chart_data = PortfolioEngineV3.get_weekly_chart_data(portfolio)['nav_pct'] if portfolio else []

    return render(request, 'core/embed_return.html', {'chart_data': chart_data})


@staff_member_required
@xframe_options_exempt
def embed_value_chart(request):
    """Embeddable portfolio value chart only."""
    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    chart_data = PortfolioEngineV3.get_weekly_chart_data(portfolio)['value'] if portfolio else []

    return render(request, 'core/embed_value.html', {'chart_data': chart_data})


@staff_member_required
@xframe_options_exempt
def embed_holdings(request):
    """Embeddable current holdings table."""
    from .models import Portfolio
    from .services import PortfolioEngineV3

    portfolio = Portfolio.objects.filter(id=2).first()
    current_holdings = PortfolioEngineV3.get_current_holdings(portfolio) if portfolio else []

    return render(request, 'core/embed_holdings.html', {'current_holdings': current_holdings})


@staff_member_required
def lab_portfolio_v3(request):
    """Portfolio Tracker v3 - NAV/Unitization Engine (full management view)."""
    from .models import Portfolio
    from .services import PortfolioEngineV3
    
    portfolios = Portfolio.objects.all()
    selected_portfolio_id = request.GET.get('portfolio_id')
    rebuild = request.GET.get('rebuild') == 'true'
    refresh_prices = request.GET.get('refresh_prices') == 'true'
    
    if selected_portfolio_id:
        portfolio = portfolios.filter(id=selected_portfolio_id).first()
    else:
        portfolio = portfolios.first()
    
    context = {
        'portfolios': portfolios,
        'selected_portfolio': portfolio,
        'chart_data': [],
        'weekly_chart_data': {'nav_pct': [], 'value': []},
        'summary': None,
        'live_summary': None,
        'rebuild_result': None,
        'yearly_performance': [],
        'current_holdings': [],
        'closed_positions': [],
    }
    
    if portfolio:
        # Rebuild if requested (full historical rebuild)
        if rebuild:
            context['rebuild_result'] = PortfolioEngineV3.full_rebuild(portfolio)
        elif refresh_prices:
            # Just refresh live quotes for current display
            PortfolioEngineV3.update_live_quotes(portfolio)
        else:
            # Normal page load: update price history only
            PortfolioEngineV3.update_price_history(portfolio)
        
        # Get chart data and summary
        context['chart_data'] = PortfolioEngineV3.get_chart_data(portfolio)
        context['weekly_chart_data'] = PortfolioEngineV3.get_weekly_chart_data(portfolio)
        context['summary'] = PortfolioEngineV3.get_summary(portfolio)
        context['live_summary'] = PortfolioEngineV3.get_live_summary(portfolio)
        context['yearly_performance'] = PortfolioEngineV3.get_yearly_performance(portfolio)
        context['current_holdings'] = PortfolioEngineV3.get_current_holdings(portfolio)
        context['closed_positions'] = PortfolioEngineV3.get_closed_positions(portfolio)
    
    return render(request, 'core/lab_portfolio_v3.html', context)


# ============================================================
# Settings Views
# ============================================================

@staff_member_required
def lab_settings(request):
    """Settings page for managing site configuration."""
    from .models import SiteSettings, PriceHistory
    from django.utils import timezone
    
    settings = SiteSettings.get_settings()
    
    if request.method == 'POST':
        # Handle settings update
        settings.live_quotes_enabled = request.POST.get('live_quotes_enabled') == 'on'
        settings.live_quotes_interval = int(request.POST.get('live_quotes_interval', 15))
        settings.save()
        
        return redirect('lab_settings')
    
    # Get last price update info
    last_price = PriceHistory.objects.order_by('-date').first()
    
    context = {
        'settings': settings,
        'last_price_date': last_price.date if last_price else None,
    }
    
    return render(request, 'core/lab_settings.html', context)


@staff_member_required
def lab_update_prices(request):
    """Manually trigger price update."""
    from .models import SiteSettings, Portfolio, PriceHistory
    from .services import PortfolioEngineV3
    from django.utils import timezone
    import yfinance as yf
    from datetime import date
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        # Get all tickers from active portfolio
        portfolio = Portfolio.objects.filter(id=2).first()
        if not portfolio:
            return JsonResponse({'success': False, 'error': 'No active portfolio found'})
        
        # Get current holdings to find tickers
        holdings = PortfolioEngineV3.get_current_holdings(portfolio)
        tickers = [h['ticker'] for h in holdings]
        
        if not tickers:
            return JsonResponse({'success': False, 'error': 'No tickers in portfolio'})
        
        # Fetch latest prices
        updated_count = 0
        today = date.today()
        
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='1d')
                if not hist.empty:
                    close_price = float(hist['Close'].iloc[-1])
                    
                    # Update or create price history
                    PriceHistory.objects.update_or_create(
                        ticker=ticker,
                        date=today,
                        defaults={'close_price': close_price}
                    )
                    updated_count += 1
            except Exception as e:
                print(f"Error updating {ticker}: {e}")
                continue
        
        # Update settings with last update info
        settings = SiteSettings.get_settings()
        settings.last_quote_update = timezone.now()
        settings.last_update_count = updated_count
        settings.save()
        
        return JsonResponse({
            'success': True,
            'updated_count': updated_count,
            'tickers': tickers,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================
# Fintest Views
# ============================================================

def fintest(request):
    """Public financial literacy test (Russian FINRA quiz clone)."""
    return render(request, 'core/fintest.html')


def fintest_questions(request):
    """API: Get active questions for the current edition."""
    from .models import FintestQuestion, SiteSettings
    
    settings = SiteSettings.get_settings()
    active_edition = settings.fintest_active_edition
    
    questions = FintestQuestion.objects.filter(is_active=True, edition=active_edition).order_by('order')
    data = []
    
    for q in questions:
        data.append({
            'id': q.id,
            'text': q.text,
            'options': [
                {'id': 'A', 'text': q.option_a},
                {'id': 'B', 'text': q.option_b},
                {'id': 'C', 'text': q.option_c},
                {'id': 'D', 'text': q.option_d},
                {'id': 'E', 'text': q.option_e},
            ]
        })
        
    return JsonResponse({
        'questions': data,
        'edition': active_edition
    })


def fintest_submit(request):
    """API: Submit quiz answers and save results."""
    from .models import FintestQuestion, FintestResult, SiteSettings
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        data = json.loads(request.body)
        survey = data.get('survey', {})
        answers = data.get('answers', {}) # map of question_id -> selected_option (A/B/C/D/E)
        
        # Determine edition (use active from settings to be safe)
        settings = SiteSettings.get_settings()
        active_edition = settings.fintest_active_edition
        
        # Fetch active questions for this edition
        questions = FintestQuestion.objects.filter(is_active=True, edition=active_edition)
        results = []
        total_correct = 0
        
        for q in questions:
            selected = answers.get(str(q.id))
            is_correct = (selected == q.correct_answer)
            if is_correct:
                total_correct += 1
                
            results.append({
                'id': q.id,
                'text': q.text,
                'selected': selected,
                'correct_answer': q.correct_answer,
                'is_correct': is_correct,
                'explanation': q.explanation,
                'options': [
                    {'id': 'A', 'text': q.option_a},
                    {'id': 'B', 'text': q.option_b},
                    {'id': 'C', 'text': q.option_c},
                    {'id': 'D', 'text': q.option_d},
                    {'id': 'E', 'text': q.option_e},
                ]
            })
            
        # Check for repeat user cookie
        is_repeat = request.COOKIES.get('fintest_completed') == 'true'

        # Save result to DB
        result_obj = FintestResult.objects.create(
            edition=active_edition,
            age_group=survey.get('age', ''),
            experience=survey.get('experience', ''),
            total_questions=len(questions),
            total_correct=total_correct,
            answers_json=results,
            is_repeat_user=is_repeat
        )
        
        response = JsonResponse({
            'score_percent': int((total_correct / len(questions)) * 100) if questions else 0,
            'total_correct': total_correct,
            'total_questions': len(questions),
            'results': results
        })

        # Set cookie to mark user as completed (expires in 1 year)
        response.set_cookie('fintest_completed', 'true', max_age=365*24*60*60)
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
