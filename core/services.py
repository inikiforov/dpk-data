"""
Services for dpk-blog: LLMService (SEO) and PortfolioEngineV3 (portfolio performance).
Lab-specific services (FMPService, AlphaFactorService) are in dpk-lab.
"""
import yfinance as yf
from decimal import Decimal
from datetime import date, timedelta, datetime
from django.utils import timezone
from django.db.models import Sum
import pandas as pd
import os
from django.conf import settings


class LLMService:
    @staticmethod
    def get_api_key():
        # Check environment variable first (Production)
        key = os.environ.get('GOOGLE_API_KEY')
        if key:
            return key.strip().strip("'").strip('"')
            
        # Fallback to local SECRETS file (Development)
        try:
            secrets_path = os.path.join(settings.BASE_DIR, 'SECRETS')
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    for line in f:
                        if line.startswith('GOOGLE_API_KEY='):
                            return line.strip().split('=')[1]
            return None
        except Exception as e:
            print(f"Error reading Google API key: {e}")
            return None

    @staticmethod
    def get_seo_report(post, force_refresh=False, model_name="gemini-2.0-flash", 
                       main_keyword="", lsi_keywords="", post_title="", post_content="",
                       meta_title="", meta_description="", excerpt=""):
        """Get cached SEO report or generate a new one."""
        from .models import SEOReport

        # Check for cached report (for this specific post) - only if no keywords provided (initial load)
        if not force_refresh and not main_keyword:
            cached = SEOReport.objects.filter(post=post).first()
            if cached:
                return cached

        # Use provided content or fall back to post content
        actual_title = post_title or post.title
        actual_content = post_content or post.content_html or post.content or ""
        actual_meta_title = meta_title or post.meta_title or ""
        actual_meta_description = meta_description or post.meta_description or ""
        actual_excerpt = excerpt or post.excerpt or ""

        # Generate new report
        content = LLMService.analyze_seo(
            title=actual_title,
            html_content=actual_content,
            main_keyword=main_keyword,
            lsi_keywords=lsi_keywords,
            meta_title=actual_meta_title,
            meta_description=actual_meta_description,
            excerpt=actual_excerpt,
            model_name=model_name
        )
        
        # If content starts with "Error", don't save it
        if content and not content.startswith("Error"):
            # Delete old reports for this post
            SEOReport.objects.filter(post=post).delete()
            return SEOReport.objects.create(
                post=post,
                content=content,
                model=model_name
            )
        
        # Return a temporary object for error display
        if isinstance(content, str) and content.startswith("Error"):
            class ErrorReport:
                pass
            err = ErrorReport()
            err.content = content
            err.created_at = timezone.now()
            err.model = model_name
            return err
             
        return None

    @staticmethod
    def analyze_seo(title, html_content, main_keyword, lsi_keywords="", 
                    meta_title="", meta_description="", excerpt="", model_name="gemini-2.0-flash"):
        """Call Gemini API to analyze blog post for SEO optimization using comprehensive Russian prompt."""
        import re
        from bs4 import BeautifulSoup
        
        api_key = LLMService.get_api_key()
        if not api_key:
            return "Error: Google API Key not found. Please add GOOGLE_API_KEY to SECRETS file."

        # Parse HTML to extract structured information
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract headings with their hierarchy
        headings = []
        for tag in ['h1', 'h2', 'h3', 'h4']:
            for h in soup.find_all(tag):
                headings.append(f"<{tag}>{h.get_text(strip=True)}</{tag}>")
        headings_str = "\n".join(headings) if headings else "(Заголовки не найдены)"
        
        # Extract links with anchor text
        links = []
        for a in soup.find_all('a', href=True):
            anchor = a.get_text(strip=True)
            href = a['href']
            links.append(f"[{anchor}]({href})")
        links_str = "\n".join(links[:20]) if links else "(Ссылки не найдены)"
        
        # Extract images with alt text
        images = []
        for img in soup.find_all('img'):
            alt = img.get('alt', '(без alt)')
            images.append(f"- alt: \"{alt}\"")
        images_str = "\n".join(images[:10]) if images else "(Изображения не найдены)"
        
        # Extract lists (ul and ol)
        lists_info = []
        ul_count = len(soup.find_all('ul'))
        ol_count = len(soup.find_all('ol'))
        if ul_count > 0:
            lists_info.append(f"- Маркированных списков (ul): {ul_count}")
        if ol_count > 0:
            lists_info.append(f"- Нумерованных списков (ol): {ol_count}")
        
        # Count total list items
        li_count = len(soup.find_all('li'))
        if li_count > 0:
            lists_info.append(f"- Всего элементов списков (li): {li_count}")
            list_items = soup.find_all('li')[:5]
            lists_info.append("- Примеры пунктов списков:")
            for li in list_items:
                text = li.get_text(strip=True)[:100]
                lists_info.append(f"  • {text}")
        
        lists_str = "\n".join(lists_info) if lists_info else "(Списки не найдены)"
        
        # Extract tables
        tables_info = []
        tables = soup.find_all('table')
        if tables:
            tables_info.append(f"- Количество таблиц: {len(tables)}")
            for i, table in enumerate(tables[:3], 1):
                rows = table.find_all('tr')
                cols = len(table.find('tr').find_all(['td', 'th'])) if table.find('tr') else 0
                tables_info.append(f"- Таблица {i}: {len(rows)} строк × {cols} столбцов")
                if rows:
                    first_cells = rows[0].find_all(['td', 'th'])[:4]
                    sample = ' | '.join([cell.get_text(strip=True)[:20] for cell in first_cells])
                    if sample:
                        tables_info.append(f"  Заголовок: {sample}")
        tables_str = "\n".join(tables_info) if tables_info else "(Таблицы не найдены)"
        
        # Get clean text content
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Build meta information section
        meta_info = ""
        if meta_title:
            meta_info += f"- **Meta Title:** {meta_title}\n"
        if meta_description:
            meta_info += f"- **Meta Description:** {meta_description}\n"
        if not meta_info:
            meta_info = "(Мета-теги не заданы)"
        
        # LSI keywords handling
        lsi_section = f'"{lsi_keywords}"' if lsi_keywords else "(не указаны)"
        
        prompt = f"""# Role
Ты — ведущий SEO-стратег и контент-маркетолог с 10-летним опытом работы с алгоритмами Google (Core Updates, Helpful Content, E-E-A-T) и Яндекс (Вега, Баден-Баден, Проксима). Твоя специализация — On-Page SEO и оптимизация контента для роста органического трафика.

# Task
Проведи глубокий SEO-аудит предоставленного текста статьи. Твоя цель — выявить слабые места, которые мешают ранжированию, и предоставить список конкретных, внедряемых рекомендаций для улучшения видимости в поиске.

# Context
- Целевая поисковая система: Google и Яндекс.
- Цель: Максимизация органического трафика и улучшение поведенческих факторов (время на сайте, доскроллы).

**Заголовок статьи (H1):** {title}

**Текущие мета-теги:**
{meta_info}

**Структура заголовков в статье:**
{headings_str}

**Ссылки в статье:**
{links_str}

**Изображения и их alt-тексты:**
{images_str}

**Списки в статье:**
{lists_str}

**Таблицы в статье:**
{tables_str}

**Текст статьи:**
\"\"\"
{text_content[:12000]}
\"\"\"

**Основное ключевое слово (Main Keyword):** "{main_keyword}"
**Дополнительные ключи (LSI):** {lsi_section}

# Analysis Rules
1. **Google Focus:** Оценивай экспертность, авторитетность и полноту ответа (E-E-A-T). Проверь, отвечает ли контент на интент (намерение) пользователя.
2. **Yandex Focus:** Следи за "водностью" и переспамом (алгоритм Баден-Баден). Проверь читабельность и структуру для удержания внимания.
3. **Keywords:** Проверь плотность ключевого слова (оптимально 1-2.5%) и его наличие в важных зонах (H1, первый абзац, H2, последний абзац).
4. **Structure:** Оцени иерархию заголовков (H1-H3), наличие списков, таблиц и форматирования.

# Output Format
Твой ответ должен быть строго структурирован в формате Markdown. Не пиши общих фраз ("сделай статью лучше"), давай конкретные инструкции ("замени заголовок Х на Y").

## 1. Анализ Мета-тегов (Title и Description)
*Текущее состояние:* (Если предоставлены, иначе предложи создать)
*Рекомендация:* Предложи 3 варианта Title (до 60 символов, кликабельные, с ключом в начале) и 1 вариант Description (до 160 символов, с CTA).

## 2. Структура и Читабельность
*Оценка:* (Краткий анализ структуры)
*Проблемы:* (Например: слишком длинные абзацы, нет H2/H3, нет списков)
*Рекомендация:* Конкретные места в тексте, которые нужно разбить на списки или добавить подзаголовки.

## 3. Работа с Ключевыми Словами и LSI
*Основной ключ:* (Хватает ли вхождений или переспам? Укажи текущую плотность.)
*LSI и семантика:* Какие слова, связанные с темой, отсутствуют? (Предложи 5-10 терминов, которые сделают текст богаче для поисковиков).

## 4. Качество контента и E-E-A-T
*Полезность:* Отвечает ли статья на вопрос полностью? Чего не хватает?
*Улучшения:* Что добавить, чтобы стать лучше конкурентов (таблицы, цитаты экспертов, блоки FAQ)?

## 5. ACTION PLAN (Чек-лист изменений)
Составь пошаговый список из 5-7 самых важных действий, которые нужно сделать прямо сейчас, отсортированный по приоритету влияния на трафик.
1. ...
2. ...
"""

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text
                
        except Exception as e:
            print(f"Error calling Gemini API for SEO analysis: {e}")
            return f"Error generating SEO report: {str(e)}"


# ============================================================
# Portfolio Engine V3 - NAV/Unitization Method
# ============================================================

class PortfolioEngineV3:
    """
    Portfolio Performance Engine using Unitization/NAV method.
    Correctly handles external cash flows for Time-Weighted Return calculation.
    """
    
    @staticmethod
    def populate_price_history(portfolio):
        """
        Fetch prices from yfinance for all tickers in trades, from first trade date to today.
        Also ensures CASH has price = 1.0 for all dates.
        """
        from .models import Trade, PriceHistory
        
        trades = Trade.objects.filter(portfolio=portfolio)
        if not trades.exists():
            return {'status': 'no_trades', 'message': 'No trades found'}
        
        # Get unique tickers and date range
        tickers = list(trades.values_list('ticker', flat=True).distinct())
        first_trade_date = trades.order_by('date').first().date.date()
        today = date.today()
        
        print(f"[PortfolioEngineV3] Fetching prices for {len(tickers)} tickers from {first_trade_date} to {today}")
        
        prices_added = 0
        
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(start=first_trade_date.isoformat(), end=(today + timedelta(days=1)).isoformat(), auto_adjust=False)
                
                if not hist.empty:
                    hist.index = pd.to_datetime(hist.index).date
                    
                    for d, row in hist.iterrows():
                        if pd.notna(row['Close']):
                            _, created = PriceHistory.objects.update_or_create(
                                ticker=ticker,
                                date=d,
                                defaults={'close_price': Decimal(str(row['Close']))}
                            )
                            if created:
                                prices_added += 1
                                
            except Exception as e:
                print(f"[PortfolioEngineV3] Error fetching {ticker}: {e}")
        
        # Add CASH prices (always 1.0)
        current_date = first_trade_date
        while current_date <= today:
            _, created = PriceHistory.objects.update_or_create(
                ticker='CASH',
                date=current_date,
                defaults={'close_price': Decimal('1.0')}
            )
            if created:
                prices_added += 1
            current_date += timedelta(days=1)
        
        return {'status': 'success', 'prices_added': prices_added}
    
    @staticmethod
    def update_price_history(portfolio):
        """
        Check last date in PriceHistory and fetch missing data up to today.
        Called on page load to sync latest prices.
        """
        from .models import Trade, PriceHistory
        
        trades = Trade.objects.filter(portfolio=portfolio)
        if not trades.exists():
            return {'status': 'no_trades'}
        
        tickers = list(trades.values_list('ticker', flat=True).distinct())
        today = date.today()
        prices_added = 0
        
        for ticker in tickers:
            last_price = PriceHistory.objects.filter(ticker=ticker).order_by('-date').first()
            
            if last_price and last_price.date >= today:
                continue  # Already up to date
            
            start_date = (last_price.date + timedelta(days=1)) if last_price else trades.order_by('date').first().date.date()
            
            try:
                t = yf.Ticker(ticker)
                hist = t.history(start=start_date.isoformat(), end=(today + timedelta(days=1)).isoformat(), auto_adjust=False)
                
                if not hist.empty:
                    hist.index = pd.to_datetime(hist.index).date
                    
                    for d, row in hist.iterrows():
                        if pd.notna(row['Close']):
                            _, created = PriceHistory.objects.update_or_create(
                                ticker=ticker,
                                date=d,
                                defaults={'close_price': Decimal(str(row['Close']))}
                            )
                            if created:
                                prices_added += 1
                                
            except Exception as e:
                print(f"[PortfolioEngineV3] Error updating {ticker}: {e}")
        
        # Update CASH prices
        last_cash = PriceHistory.objects.filter(ticker='CASH').order_by('-date').first()
        start_cash = (last_cash.date + timedelta(days=1)) if last_cash else trades.order_by('date').first().date.date()
        
        current_date = start_cash
        while current_date <= today:
            PriceHistory.objects.update_or_create(
                ticker='CASH',
                date=current_date,
                defaults={'close_price': Decimal('1.0')}
            )
            current_date += timedelta(days=1)
        
        return {'status': 'success', 'prices_added': prices_added}
    
    @staticmethod
    def populate_dividend_history(portfolio):
        """
        Fetch dividends from yfinance for all tickers during holding periods.
        """
        from .models import Trade, DividendHistory
        
        trades = Trade.objects.filter(portfolio=portfolio)
        if not trades.exists():
            return {'status': 'no_trades'}
        
        tickers = list(trades.values_list('ticker', flat=True).distinct())
        first_trade_date = trades.order_by('date').first().date.date()
        today = date.today()
        
        dividends_added = 0
        
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(start=first_trade_date.isoformat(), end=(today + timedelta(days=1)).isoformat(), actions=True)
                
                if not hist.empty and 'Dividends' in hist.columns:
                    hist.index = pd.to_datetime(hist.index).date
                    
                    for d, row in hist.iterrows():
                        div_amount = row.get('Dividends', 0)
                        if div_amount and div_amount > 0:
                            _, created = DividendHistory.objects.update_or_create(
                                ticker=ticker,
                                date=d,
                                defaults={'amount': Decimal(str(div_amount))}
                            )
                            if created:
                                dividends_added += 1
                                
            except Exception as e:
                print(f"[PortfolioEngineV3] Error fetching dividends for {ticker}: {e}")
        
        return {'status': 'success', 'dividends_added': dividends_added}
    
    @staticmethod
    def build_transaction_log(portfolio):
        """
        Combine Trade, CashTransaction, and DividendHistory into TransactionLog.
        Clears existing TransactionLog for this portfolio and rebuilds.
        """
        from .models import Trade, CashTransaction, DividendHistory, TransactionLog
        
        # Clear existing transaction log for this portfolio
        TransactionLog.objects.filter(portfolio=portfolio).delete()
        
        transactions = []
        
        # Add trades
        for trade in Trade.objects.filter(portfolio=portfolio):
            trade_value = trade.quantity * trade.price
            
            if trade.side == 'BUY':
                amount = -trade_value - trade.fees  # Cash decreases
            else:  # SELL
                amount = trade_value - trade.fees  # Cash increases
            
            transactions.append(TransactionLog(
                portfolio=portfolio,
                date=trade.date,
                type=trade.side,
                ticker=trade.ticker,
                shares=trade.quantity,
                price=trade.price,
                amount=amount,
                commission=trade.fees,
                source_id=trade.id,
                source_type='trade'
            ))
        
        # Add cash transactions
        for cash_txn in CashTransaction.objects.filter(portfolio=portfolio):
            if cash_txn.type == 'DEPOSIT':
                amount = cash_txn.amount
            else:  # WITHDRAWAL
                amount = -cash_txn.amount
            
            transactions.append(TransactionLog(
                portfolio=portfolio,
                date=cash_txn.date,
                type=cash_txn.type,
                ticker=None,
                shares=None,
                price=None,
                amount=amount,
                commission=Decimal('0'),
                source_id=cash_txn.id,
                source_type='cash_transaction'
            ))
        
        # Add dividends (need to calculate shares held at each dividend date)
        trades_list = list(Trade.objects.filter(portfolio=portfolio).order_by('date'))
        tickers_traded = set(t.ticker for t in trades_list)
        
        for dividend in DividendHistory.objects.filter(ticker__in=tickers_traded):
            # Calculate shares held on this date
            shares_held = Decimal('0')
            for trade in trades_list:
                if trade.ticker == dividend.ticker and trade.date.date() <= dividend.date:
                    if trade.side == 'BUY':
                        shares_held += trade.quantity
                    else:
                        shares_held -= trade.quantity
            
            if shares_held > 0:
                div_amount = shares_held * dividend.amount
                
                transactions.append(TransactionLog(
                    portfolio=portfolio,
                    date=timezone.make_aware(datetime.combine(dividend.date, datetime.min.time())),
                    type='DIVIDEND',
                    ticker=dividend.ticker,
                    shares=shares_held,
                    price=dividend.amount,  # Per-share dividend
                    amount=div_amount,
                    commission=Decimal('0'),
                    source_id=dividend.id,
                    source_type='dividend'
                ))
        
        # Bulk create
        TransactionLog.objects.bulk_create(transactions)
        
        return {'status': 'success', 'transactions_created': len(transactions)}
    
    @staticmethod
    def calculate_nav(portfolio):
        """
        Main NAV calculation loop using unitization method.
        """
        from .models import TransactionLog, PriceHistory, DailySnapshot
        
        # Get all transactions sorted by date
        transactions = list(TransactionLog.objects.filter(portfolio=portfolio).order_by('date'))
        
        if not transactions:
            return {'status': 'no_transactions', 'message': 'No transactions found. Build transaction log first.'}
        
        # Clear existing snapshots
        DailySnapshot.objects.filter(portfolio=portfolio).delete()
        
        # Find date range
        first_date = transactions[0].date.date()
        today = date.today()
        
        # Initialize
        total_units = Decimal('0')
        current_nav = Decimal('100.0')
        
        # Holdings ledger: {ticker: shares}
        holdings = {'CASH': Decimal('0')}
        
        # Group transactions by date
        txn_by_date = {}
        for txn in transactions:
            txn_date = txn.date.date()
            if txn_date not in txn_by_date:
                txn_by_date[txn_date] = []
            txn_by_date[txn_date].append(txn)
        
        # Build price lookup
        prices_qs = PriceHistory.objects.filter(date__gte=first_date, date__lte=today)
        price_lookup = {}
        for p in prices_qs:
            if p.ticker not in price_lookup:
                price_lookup[p.ticker] = {}
            price_lookup[p.ticker][p.date] = p.close_price
        
        snapshots = []
        current_date = first_date
        
        while current_date <= today:
            day_transactions = txn_by_date.get(current_date, [])
            
            # Separate by type for processing order
            dividends = [t for t in day_transactions if t.type == 'DIVIDEND']
            trades = [t for t in day_transactions if t.type in ('BUY', 'SELL')]
            external_flows = [t for t in day_transactions if t.type in ('DEPOSIT', 'WITHDRAWAL')]
            
            # Step 1: Process Dividends
            for div in dividends:
                holdings['CASH'] += div.amount
            
            # Step 2: Process Trades
            for trade in trades:
                ticker = trade.ticker
                if ticker not in holdings:
                    holdings[ticker] = Decimal('0')
                
                if trade.type == 'BUY':
                    holdings['CASH'] -= abs(trade.amount)
                    holdings[ticker] += trade.shares
                else:  # SELL
                    holdings['CASH'] += trade.amount
                    holdings[ticker] -= trade.shares
            
            # Step 3: Mark-to-Market
            total_value = Decimal('0')
            for ticker, shares in holdings.items():
                if shares == 0:
                    continue
                
                if ticker == 'CASH':
                    total_value += shares
                else:
                    price = Decimal('0')
                    if ticker in price_lookup:
                        if current_date in price_lookup[ticker]:
                            price = price_lookup[ticker][current_date]
                        else:
                            for d in sorted(price_lookup[ticker].keys(), reverse=True):
                                if d <= current_date:
                                    price = price_lookup[ticker][d]
                                    break
                    
                    total_value += shares * price
            
            # Step 4: Calculate NAV
            if total_units > 0:
                current_nav = total_value / total_units
            
            # Step 5: Process External Flows
            for flow in external_flows:
                if flow.type == 'DEPOSIT':
                    if current_nav > 0:
                        new_units = flow.amount / current_nav
                    else:
                        current_nav = Decimal('100.0')
                        new_units = flow.amount / current_nav
                    
                    total_units += new_units
                    holdings['CASH'] += flow.amount
                    total_value += flow.amount
                    
                elif flow.type == 'WITHDRAWAL':
                    if current_nav > 0:
                        units_redeemed = abs(flow.amount) / current_nav
                        total_units -= units_redeemed
                    
                    holdings['CASH'] -= abs(flow.amount)
                    total_value -= abs(flow.amount)
            
            # Step 6: Store Daily Snapshot
            if total_units > 0:
                snapshots.append(DailySnapshot(
                    portfolio=portfolio,
                    date=current_date,
                    total_value=total_value,
                    total_units=total_units,
                    nav=current_nav,
                    cash_balance=holdings['CASH']
                ))
            
            current_date += timedelta(days=1)
        
        # Bulk create snapshots
        DailySnapshot.objects.bulk_create(snapshots)
        
        # Calculate overall return
        if snapshots:
            first_nav = Decimal('100.0')
            last_nav = snapshots[-1].nav
            total_return = ((last_nav - first_nav) / first_nav) * 100
        else:
            total_return = Decimal('0')
        
        return {
            'status': 'success',
            'days_calculated': len(snapshots),
            'first_date': first_date.isoformat(),
            'last_date': today.isoformat(),
            'final_nav': float(current_nav) if snapshots else 100.0,
            'total_return_pct': float(total_return)
        }
    
    @staticmethod
    def get_chart_data(portfolio):
        """Return NAV chart data for display."""
        from .models import DailySnapshot
        
        snapshots = DailySnapshot.objects.filter(portfolio=portfolio).order_by('date')
        
        return [
            [int(datetime.combine(s.date, datetime.min.time()).timestamp() * 1000), float(s.nav)]
            for s in snapshots
        ]
    
    @staticmethod
    def get_weekly_chart_data(portfolio):
        """Return weekly chart data with both NAV % performance and total value."""
        from .models import DailySnapshot
        
        snapshots = list(DailySnapshot.objects.filter(portfolio=portfolio).order_by('date'))
        
        if not snapshots:
            return {'nav_pct': [], 'value': []}
        
        # Sample weekly (every 7th day)
        weekly_snapshots = []
        last_date = None
        for s in snapshots:
            if last_date is None or (s.date - last_date).days >= 7:
                weekly_snapshots.append(s)
                last_date = s.date
        
        # Always include the last snapshot
        if snapshots[-1] not in weekly_snapshots:
            weekly_snapshots.append(snapshots[-1])
        
        nav_pct_data = []
        value_data = []
        
        for s in weekly_snapshots:
            timestamp = int(datetime.combine(s.date, datetime.min.time()).timestamp() * 1000)
            nav_pct = float(s.nav) - 100  # % change from baseline
            nav_pct_data.append([timestamp, round(nav_pct, 2)])
            value_data.append([timestamp, float(s.total_value)])
        
        return {
            'nav_pct': nav_pct_data,
            'value': value_data
        }
    
    @staticmethod
    def get_summary(portfolio):
        """Return summary metrics for display."""
        from .models import DailySnapshot
        
        snapshots = list(DailySnapshot.objects.filter(portfolio=portfolio).order_by('date'))
        
        if not snapshots:
            return None
        
        first = snapshots[0]
        last = snapshots[-1]
        
        total_return = ((last.nav - Decimal('100.0')) / Decimal('100.0')) * 100
        
        return {
            'total_value': float(last.total_value),
            'nav': float(last.nav),
            'total_units': float(last.total_units),
            'cash_balance': float(last.cash_balance),
            'total_return_pct': float(total_return),
            'inception_date': first.date.isoformat(),
            'days_tracked': len(snapshots)
        }
    
    @staticmethod
    def get_yearly_performance(portfolio):
        """Calculate year-by-year performance from NAV snapshots."""
        from .models import DailySnapshot, TransactionLog, PriceHistory
        from collections import defaultdict
        
        snapshots = list(DailySnapshot.objects.filter(portfolio=portfolio).order_by('date'))
        
        if not snapshots:
            return []
        
        today = date.today()
        current_year = today.year
        
        # Group snapshots by year
        by_year = defaultdict(list)
        for s in snapshots:
            by_year[s.date.year].append(s)
        
        yearly_data = []
        prev_year_end_nav = Decimal('100.0')
        
        for year in sorted(by_year.keys()):
            year_snapshots = by_year[year]
            first_snap = year_snapshots[0]
            last_snap = year_snapshots[-1]
            
            start_nav = prev_year_end_nav
            
            # For current year, calculate live NAV
            if year == current_year:
                live_data = PortfolioEngineV3._calculate_live_nav(portfolio, last_snap)
                if live_data:
                    end_nav = Decimal(str(live_data['nav']))
                    end_value = Decimal(str(live_data['total_value']))
                    end_cash = Decimal(str(live_data['cash_balance']))
                else:
                    end_nav = last_snap.nav
                    end_value = last_snap.total_value
                    end_cash = last_snap.cash_balance
            else:
                end_nav = last_snap.nav
                end_value = last_snap.total_value
                end_cash = last_snap.cash_balance
            
            # Calculate return for this year
            if start_nav > 0:
                year_return = ((end_nav - start_nav) / start_nav) * 100
            else:
                year_return = Decimal('0')
            
            yearly_data.append({
                'year': year,
                'start_nav': float(start_nav),
                'end_nav': float(end_nav),
                'return_pct': float(year_return),
                'end_value': float(end_value),
                'end_cash': float(end_cash),
                'is_live': year == current_year
            })
            
            prev_year_end_nav = end_nav
        
        return yearly_data
    
    @staticmethod
    def _calculate_live_nav(portfolio, last_snapshot):
        """Calculate today's NAV using latest PriceHistory prices."""
        from .models import TransactionLog, PriceHistory
        
        today = date.today()
        
        txns = TransactionLog.objects.filter(portfolio=portfolio).order_by('date')
        
        holdings = {'CASH': Decimal('0')}
        
        for t in txns:
            if t.type == 'DEPOSIT':
                holdings['CASH'] += t.amount
            elif t.type == 'WITHDRAWAL':
                holdings['CASH'] -= abs(t.amount)
            elif t.type == 'DIVIDEND':
                holdings['CASH'] += t.amount
            elif t.type == 'BUY' and t.ticker:
                holdings['CASH'] -= abs(t.amount)
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] += t.shares
            elif t.type == 'SELL' and t.ticker:
                holdings['CASH'] += t.amount
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] -= t.shares
        
        total_value = holdings.get('CASH', Decimal('0'))
        has_prices = False
        
        for ticker, shares in holdings.items():
            if ticker == 'CASH' or shares <= 0:
                continue
            
            price_obj = PriceHistory.objects.filter(ticker=ticker).order_by('-date').first()
            if price_obj:
                total_value += shares * price_obj.close_price
                has_prices = True
        
        if not has_prices:
            return None
        
        total_units = last_snapshot.total_units if last_snapshot.total_units > 0 else Decimal('1')
        live_nav = total_value / total_units
        
        return {
            'total_value': float(total_value),
            'nav': float(live_nav),
            'cash_balance': float(holdings.get('CASH', 0))
        }
    
    @staticmethod
    def full_rebuild(portfolio):
        """Full rebuild: price history, dividend history, transaction log, and NAV calculation."""
        results = {}
        
        print(f"[PortfolioEngineV3] Starting full rebuild for {portfolio.name}")
        
        results['prices'] = PortfolioEngineV3.populate_price_history(portfolio)
        print(f"[PortfolioEngineV3] Prices: {results['prices']}")
        
        results['dividends'] = PortfolioEngineV3.populate_dividend_history(portfolio)
        print(f"[PortfolioEngineV3] Dividends: {results['dividends']}")
        
        results['transactions'] = PortfolioEngineV3.build_transaction_log(portfolio)
        print(f"[PortfolioEngineV3] Transactions: {results['transactions']}")
        
        results['nav'] = PortfolioEngineV3.calculate_nav(portfolio)
        print(f"[PortfolioEngineV3] NAV: {results['nav']}")
        
        return results
    
    @staticmethod
    def get_current_holdings(portfolio):
        """Calculate current holdings with unrealized P&L using FIFO cost basis."""
        from .models import TransactionLog, PriceHistory, LiveQuote
        
        txns = TransactionLog.objects.filter(portfolio=portfolio).order_by('date')
        
        # Track lots for FIFO cost basis
        lots = {}
        
        for t in txns:
            if t.type == 'BUY' and t.ticker:
                if t.ticker not in lots:
                    lots[t.ticker] = []
                cost_per_share = abs(float(t.amount)) / float(t.shares) if t.shares else 0
                lots[t.ticker].append([float(t.shares), cost_per_share])
            elif t.type == 'SELL' and t.ticker:
                if t.ticker in lots:
                    shares_to_sell = float(t.shares)
                    while shares_to_sell > 0 and lots[t.ticker]:
                        lot = lots[t.ticker][0]
                        if lot[0] <= shares_to_sell:
                            shares_to_sell -= lot[0]
                            lots[t.ticker].pop(0)
                        else:
                            lot[0] -= shares_to_sell
                            shares_to_sell = 0
        
        # Calculate current holdings
        holdings = []
        today = date.today()
        
        for ticker, ticker_lots in lots.items():
            if not ticker_lots:
                continue
            
            total_shares = sum(lot[0] for lot in ticker_lots)
            if total_shares <= 0:
                continue
            
            total_cost = sum(lot[0] * lot[1] for lot in ticker_lots)
            avg_cost = total_cost / total_shares if total_shares else 0
            
            # Get current price
            current_price = 0
            market_open = PortfolioEngineV3.is_us_market_open()
            
            if market_open:
                live_quote = LiveQuote.objects.filter(ticker=ticker).first()
                if live_quote:
                    current_price = float(live_quote.price)
                else:
                    price_obj = PriceHistory.objects.filter(ticker=ticker, date__lte=today).order_by('-date').first()
                    current_price = float(price_obj.close_price) if price_obj else 0
            else:
                price_obj = PriceHistory.objects.filter(ticker=ticker, date__lte=today).order_by('-date').first()
                if price_obj:
                    current_price = float(price_obj.close_price)
                else:
                    live_quote = LiveQuote.objects.filter(ticker=ticker).first()
                    current_price = float(live_quote.price) if live_quote else 0
            
            current_value = total_shares * current_price
            unrealized_pnl = current_value - total_cost
            unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost else 0
            
            holdings.append({
                'ticker': ticker,
                'shares': round(total_shares, 2),
                'avg_cost': round(avg_cost, 2),
                'current_price': round(current_price, 2),
                'current_value': round(current_value, 2),
                'total_cost': round(total_cost, 2),
                'unrealized_pnl': round(unrealized_pnl, 2),
                'unrealized_pnl_pct': round(unrealized_pnl_pct, 2)
            })
        
        # Calculate total portfolio value and add weight %
        total_portfolio_value = sum(h['current_value'] for h in holdings)
        for h in holdings:
            h['weight_pct'] = round((h['current_value'] / total_portfolio_value * 100) if total_portfolio_value else 0, 1)
        
        # Sort by current value descending
        holdings.sort(key=lambda x: x['current_value'], reverse=True)
        return holdings
    
    @staticmethod
    def get_closed_positions(portfolio):
        """Calculate closed positions with realized P&L using FIFO cost basis."""
        from .models import TransactionLog
        
        txns = TransactionLog.objects.filter(portfolio=portfolio).order_by('date')
        
        lots = {}
        closed = {}
        
        for t in txns:
            if t.type == 'BUY' and t.ticker:
                if t.ticker not in lots:
                    lots[t.ticker] = []
                cost_per_share = abs(float(t.amount)) / float(t.shares) if t.shares else 0
                lots[t.ticker].append([float(t.shares), cost_per_share, t.date.date()])
            elif t.type == 'SELL' and t.ticker:
                if t.ticker not in lots:
                    continue
                    
                shares_to_sell = float(t.shares)
                proceeds_per_share = float(t.amount) / float(t.shares) if t.shares else 0
                
                while shares_to_sell > 0 and lots[t.ticker]:
                    lot = lots[t.ticker][0]
                    
                    if t.ticker not in closed:
                        closed[t.ticker] = {
                            'shares_sold': 0,
                            'total_proceeds': 0,
                            'total_cost': 0,
                            'first_buy': lot[2],
                            'last_sell': t.date.date()
                        }
                    
                    if lot[0] <= shares_to_sell:
                        sold_shares = lot[0]
                        closed[t.ticker]['shares_sold'] += sold_shares
                        closed[t.ticker]['total_proceeds'] += sold_shares * proceeds_per_share
                        closed[t.ticker]['total_cost'] += sold_shares * lot[1]
                        closed[t.ticker]['last_sell'] = t.date.date()
                        shares_to_sell -= sold_shares
                        lots[t.ticker].pop(0)
                    else:
                        closed[t.ticker]['shares_sold'] += shares_to_sell
                        closed[t.ticker]['total_proceeds'] += shares_to_sell * proceeds_per_share
                        closed[t.ticker]['total_cost'] += shares_to_sell * lot[1]
                        closed[t.ticker]['last_sell'] = t.date.date()
                        lot[0] -= shares_to_sell
                        shares_to_sell = 0
        
        result = []
        for ticker, data in closed.items():
            realized_pnl = data['total_proceeds'] - data['total_cost']
            realized_pnl_pct = (realized_pnl / data['total_cost'] * 100) if data['total_cost'] else 0
            holding_days = (data['last_sell'] - data['first_buy']).days
            
            remaining = sum(lot[0] for lot in lots.get(ticker, []))
            is_fully_closed = remaining <= 0.01
            
            result.append({
                'ticker': ticker,
                'shares_sold': round(data['shares_sold'], 2),
                'total_proceeds': round(data['total_proceeds'], 2),
                'total_cost': round(data['total_cost'], 2),
                'realized_pnl': round(realized_pnl, 2),
                'realized_pnl_pct': round(realized_pnl_pct, 2),
                'first_buy': data['first_buy'].isoformat(),
                'last_sell': data['last_sell'].isoformat(),
                'holding_days': holding_days,
                'fully_closed': is_fully_closed
            })
        
        result.sort(key=lambda x: x['last_sell'], reverse=True)
        return result
    
    @staticmethod
    def is_us_market_open():
        """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, Monday-Friday)."""
        import pytz
        
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        if now_et.weekday() > 4:
            return False
        
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close
    
    @staticmethod
    def is_trading_day(check_date=None):
        """Check if a given date is a US trading day (weekday)."""
        if check_date is None:
            check_date = date.today()
        return check_date.weekday() < 5
    
    @staticmethod
    def update_live_quotes(portfolio):
        """Fetch current prices from yfinance for tickers currently held in portfolio."""
        from .models import LiveQuote, TransactionLog
        
        txns = TransactionLog.objects.filter(portfolio=portfolio).order_by('date')
        
        holdings = {}
        for t in txns:
            if t.type == 'BUY' and t.ticker:
                holdings[t.ticker] = holdings.get(t.ticker, Decimal('0')) + t.shares
            elif t.type == 'SELL' and t.ticker:
                holdings[t.ticker] = holdings.get(t.ticker, Decimal('0')) - t.shares
        
        current_tickers = [ticker for ticker, shares in holdings.items() if shares > 0]
        
        if not current_tickers:
            return {'status': 'no_tickers', 'updated': 0}
        
        updated = 0
        errors = []
        
        try:
            tickers_str = ' '.join(current_tickers)
            data = yf.download(tickers_str, period='1d', progress=False, threads=True)
            
            if not data.empty:
                if len(current_tickers) == 1:
                    ticker = current_tickers[0]
                    if 'Close' in data.columns and not data['Close'].empty:
                        price = float(data['Close'].iloc[-1])
                        LiveQuote.objects.update_or_create(
                            ticker=ticker,
                            defaults={'price': Decimal(str(price))}
                        )
                        updated += 1
                else:
                    if 'Close' in data.columns:
                        close_data = data['Close']
                        for ticker in current_tickers:
                            if ticker in close_data.columns:
                                price_series = close_data[ticker].dropna()
                                if not price_series.empty:
                                    price = float(price_series.iloc[-1])
                                    LiveQuote.objects.update_or_create(
                                        ticker=ticker,
                                        defaults={'price': Decimal(str(price))}
                                    )
                                    updated += 1
        except Exception as e:
            errors.append(f"Batch download error: {str(e)}")
            print(f"[LiveQuote] Batch download error: {e}")
        
        return {
            'status': 'success',
            'updated': updated,
            'total_tickers': len(current_tickers),
            'errors': errors
        }
    
    @staticmethod
    def get_live_summary(portfolio):
        """Calculate today's tentative NAV using LiveQuote prices."""
        from .models import DailySnapshot, TransactionLog, LiveQuote, PriceHistory
        
        today = date.today()
        
        last_snapshot = DailySnapshot.objects.filter(
            portfolio=portfolio,
            date__lt=today
        ).order_by('-date').first()
        
        if not last_snapshot:
            return None
        
        live_quotes = {lq.ticker: lq.price for lq in LiveQuote.objects.all()}
        
        if not live_quotes:
            return None
        
        txns = TransactionLog.objects.filter(portfolio=portfolio).order_by('date')
        
        holdings = {'CASH': Decimal('0')}
        
        for t in txns:
            if t.type == 'DEPOSIT':
                holdings['CASH'] += t.amount
            elif t.type == 'WITHDRAWAL':
                holdings['CASH'] -= abs(t.amount)
            elif t.type == 'DIVIDEND':
                holdings['CASH'] += t.amount
            elif t.type == 'BUY' and t.ticker:
                holdings['CASH'] -= abs(t.amount)
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] += t.shares
            elif t.type == 'SELL' and t.ticker:
                holdings['CASH'] += t.amount
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] -= t.shares
        
        total_value = holdings.get('CASH', Decimal('0'))
        
        for ticker, shares in holdings.items():
            if ticker == 'CASH' or shares <= 0:
                continue
            
            if ticker in live_quotes:
                total_value += shares * live_quotes[ticker]
            else:
                price_obj = PriceHistory.objects.filter(ticker=ticker).order_by('-date').first()
                if price_obj:
                    total_value += shares * price_obj.close_price
        
        total_units = last_snapshot.total_units
        live_nav = total_value / total_units if total_units > 0 else Decimal('100.0')
        total_return = ((live_nav - Decimal('100.0')) / Decimal('100.0')) * 100
        
        most_recent_quote = LiveQuote.objects.order_by('-updated_at').first()
        
        return {
            'total_value': float(total_value),
            'nav': float(live_nav),
            'total_units': float(total_units),
            'cash_balance': float(holdings.get('CASH', 0)),
            'total_return_pct': float(total_return),
            'is_live': True,
            'market_open': PortfolioEngineV3.is_us_market_open(),
            'last_quote_update': most_recent_quote.updated_at if most_recent_quote else None,
            'prev_nav': float(last_snapshot.nav),
            'prev_value': float(last_snapshot.total_value),
            'day_change_pct': float((live_nav - last_snapshot.nav) / last_snapshot.nav * 100) if last_snapshot.nav > 0 else 0
        }
    
    @staticmethod
    def incremental_eod_update(portfolio):
        """Perform end-of-day update: add today's DailySnapshot using close prices."""
        from .models import DailySnapshot, TransactionLog, PriceHistory
        
        today = date.today()
        
        if not PortfolioEngineV3.is_trading_day(today):
            return {'status': 'not_trading_day', 'message': f'{today} is not a trading day'}
        
        # Fetch today's close prices
        trades = TransactionLog.objects.filter(portfolio=portfolio, ticker__isnull=False)
        tickers = list(trades.values_list('ticker', flat=True).distinct())
        
        prices_updated = 0
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1d", auto_adjust=False)
                
                if not hist.empty:
                    close_price = Decimal(str(hist['Close'].iloc[-1]))
                    PriceHistory.objects.update_or_create(
                        ticker=ticker,
                        date=today,
                        defaults={'close_price': close_price}
                    )
                    prices_updated += 1
            except Exception as e:
                print(f"[EOD Update] Error fetching {ticker}: {e}")
        
        # Add CASH price
        PriceHistory.objects.update_or_create(
            ticker='CASH',
            date=today,
            defaults={'close_price': Decimal('1.0')}
        )
        
        # Get previous snapshot
        prev_snapshot = DailySnapshot.objects.filter(
            portfolio=portfolio,
            date__lt=today
        ).order_by('-date').first()
        
        if not prev_snapshot:
            return {'status': 'no_previous_snapshot', 'message': 'No previous snapshot found. Run full rebuild first.'}
        
        # Calculate today's holdings and value
        txns = list(TransactionLog.objects.filter(portfolio=portfolio).order_by('date'))
        
        holdings = {'CASH': Decimal('0')}
        total_units = Decimal('0')
        
        for t in txns:
            txn_date = t.date.date()
            
            if t.type == 'DEPOSIT':
                if total_units == 0:
                    nav_at_deposit = Decimal('100.0')
                else:
                    snap = DailySnapshot.objects.filter(
                        portfolio=portfolio,
                        date__lt=txn_date
                    ).order_by('-date').first()
                    nav_at_deposit = snap.nav if snap else Decimal('100.0')
                
                new_units = t.amount / nav_at_deposit
                total_units += new_units
                holdings['CASH'] += t.amount
                
            elif t.type == 'WITHDRAWAL':
                snap = DailySnapshot.objects.filter(
                    portfolio=portfolio,
                    date__lt=txn_date
                ).order_by('-date').first()
                nav_at_withdrawal = snap.nav if snap else Decimal('100.0')
                
                units_redeemed = abs(t.amount) / nav_at_withdrawal
                total_units -= units_redeemed
                holdings['CASH'] -= abs(t.amount)
                
            elif t.type == 'DIVIDEND':
                holdings['CASH'] += t.amount
                
            elif t.type == 'BUY' and t.ticker:
                holdings['CASH'] -= abs(t.amount)
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] += t.shares
                
            elif t.type == 'SELL' and t.ticker:
                holdings['CASH'] += t.amount
                if t.ticker not in holdings:
                    holdings[t.ticker] = Decimal('0')
                holdings[t.ticker] -= t.shares
        
        # Mark-to-market
        total_value = holdings.get('CASH', Decimal('0'))
        
        for ticker, shares in holdings.items():
            if ticker == 'CASH' or shares <= 0:
                continue
            
            price_obj = PriceHistory.objects.filter(ticker=ticker, date=today).first()
            if not price_obj:
                price_obj = PriceHistory.objects.filter(ticker=ticker, date__lt=today).order_by('-date').first()
            
            if price_obj:
                total_value += shares * price_obj.close_price
        
        # Calculate NAV
        nav = total_value / total_units if total_units > 0 else Decimal('100.0')
        
        # Create or update today's snapshot
        snapshot, created = DailySnapshot.objects.update_or_create(
            portfolio=portfolio,
            date=today,
            defaults={
                'total_value': total_value,
                'total_units': total_units,
                'nav': nav,
                'cash_balance': holdings.get('CASH', Decimal('0'))
            }
        )
        
        total_return = ((nav - Decimal('100.0')) / Decimal('100.0')) * 100
        
        return {
            'status': 'success',
            'date': today.isoformat(),
            'prices_updated': prices_updated,
            'nav': float(nav),
            'total_value': float(total_value),
            'total_return_pct': float(total_return),
            'created': created
        }
