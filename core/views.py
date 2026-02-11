"""
Views for dpk-blog: index, portfolio, blog, and settings.
Lab analysis tools are in dpk-lab project.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from .models import BlogPost


def index(request):
    """Homepage with portfolio summary and recent blog posts."""
    from .models import Portfolio
    from .services import PortfolioEngineV3
    
    # Get active portfolio (ID=2) for index page display
    portfolio = Portfolio.objects.filter(id=2).first()
    
    # Get last 3 blog posts
    recent_posts = BlogPost.objects.filter(published=True).order_by('-created_at')[:3]
    
    context = {
        'current_holdings': [],
        'weekly_chart_data': {'nav_pct': [], 'value': []},
        'recent_posts': recent_posts,
    }
    
    if portfolio:
        context['current_holdings'] = PortfolioEngineV3.get_current_holdings(portfolio)
        context['weekly_chart_data'] = PortfolioEngineV3.get_weekly_chart_data(portfolio)
    
    return render(request, 'core/index.html', context)


# ============================================================
# Blog Views
# ============================================================

def blog_index(request):
    """Public blog listing."""
    posts = BlogPost.objects.filter(published=True).order_by('-created_at')
    return render(request, 'core/blog_index.html', {'posts': posts})


@login_required
def blog_drafts(request):
    """Show all draft (unpublished) posts for editing."""
    drafts = BlogPost.objects.filter(published=False).order_by('-updated_at')
    return render(request, 'core/blog_drafts.html', {'drafts': drafts})


def post_detail(request, slug):
    """Single blog post view."""
    post = get_object_or_404(BlogPost, slug=slug, published=True)
    return render(request, 'core/post_detail.html', {'post': post})


@login_required
def blog_editor(request, slug=None):
    """WYSIWYG blog post editor."""
    post = None
    if slug:
        post = get_object_or_404(BlogPost, slug=slug)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        if post is None:
            post = BlogPost()
        
        post.title = data.get('title', 'Untitled')
        post.content_html = data.get('content_html', '')
        post.published = data.get('published', False)
        
        # Post options
        if 'slug' in data and data['slug']:
            post.slug = data['slug']
        elif not post.slug:
            from django.utils.text import slugify
            post.slug = slugify(post.title)
        
        post.featured_image = data.get('featured_image', '')
        post.excerpt = data.get('excerpt', '')[:300]
        
        # SEO fields
        post.meta_title = data.get('meta_title', '')[:70]
        post.meta_description = data.get('meta_description', '')[:160]
        post.og_image = data.get('og_image', '')
        
        post.save()
        
        return JsonResponse({
            'success': True,
            'slug': post.slug,
            'message': 'Post saved successfully'
        })
    
    return render(request, 'core/blog_editor.html', {'post': post})


@login_required  
def blog_upload_image(request):
    """Handle image uploads from the editor."""
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os
    from datetime import datetime
    
    if request.method != 'POST' or 'image' not in request.FILES:
        return JsonResponse({'error': 'No image provided'}, status=400)
    
    image = request.FILES['image']
    
    # Generate unique filename
    ext = os.path.splitext(image.name)[1] or '.png'
    filename = f"blog_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    
    # Save to media folder
    path = default_storage.save(f'uploads/{filename}', ContentFile(image.read()))
    url = default_storage.url(path)
    
    return JsonResponse({
        'success': True,
        'url': url
    })


@login_required
def blog_seo_report(request, slug):
    """Generate or retrieve SEO report for a blog post."""
    import markdown
    from .services import LLMService
    
    post = get_object_or_404(BlogPost, slug=slug)
    
    if request.method == 'POST':
        # Parse JSON body
        data = json.loads(request.body)
        
        force_refresh = data.get('refresh', False)
        model_name = data.get('model', 'gemini-2.0-flash')
        main_keyword = data.get('main_keyword', '')
        lsi_keywords = data.get('lsi_keywords', '')
        post_title = data.get('post_title', post.title)
        post_content = data.get('post_content', post.content_html or post.content)
        meta_title = data.get('meta_title', post.meta_title)
        meta_description = data.get('meta_description', post.meta_description)
        excerpt = data.get('excerpt', post.excerpt)
        
        # Pass all data to LLMService
        report = LLMService.get_seo_report(
            post=post,
            force_refresh=force_refresh,
            model_name=model_name,
            main_keyword=main_keyword,
            lsi_keywords=lsi_keywords,
            post_title=post_title,
            post_content=post_content,
            meta_title=meta_title,
            meta_description=meta_description,
            excerpt=excerpt
        )
    else:
        # GET fallback (for cached reports)
        force_refresh = request.GET.get('refresh', '').lower() == 'true'
        model_name = request.GET.get('model', 'gemini-2.0-flash')
        report = LLMService.get_seo_report(post, force_refresh=force_refresh, model_name=model_name)
    
    if report:
        # Convert markdown to HTML for display
        html_content = markdown.markdown(report.content, extensions=['extra', 'nl2br', 'tables'])
        
        return JsonResponse({
            'success': True,
            'content': report.content,
            'html_content': html_content,
            'model': report.model,
            'created_at': report.created_at.strftime('%d %b %Y в %H:%M')
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Ошибка генерации SEO-отчёта'
    }, status=500)


# ============================================================
# Portfolio Views
# ============================================================

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


@login_required
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

@login_required
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


@login_required
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
