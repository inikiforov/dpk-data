"""
Admin configuration for dpk-data.
Portfolio management.
"""
from django.contrib import admin
from .models import (
    Portfolio, Trade, CashTransaction, 
    MarketDataCache, TransactionLog, DailySnapshot,
    PriceHistory, DividendHistory, LiveQuote, SiteSettings
)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('name', 'currency', 'created_at')
    actions = ['update_live_quotes', 'run_eod_update', 'full_rebuild_v3']

    @admin.action(description='🔄 Update Live Quotes (intraday prices)')
    def update_live_quotes(self, request, queryset):
        from .services import PortfolioEngineV3
        for portfolio in queryset:
            try:
                result = PortfolioEngineV3.update_live_quotes(portfolio)
                self.message_user(
                    request, 
                    f"✅ {portfolio.name}: Updated {result.get('updated', 0)}/{result.get('total_tickers', 0)} live quotes"
                )
            except Exception as e:
                self.message_user(request, f"❌ Error updating live quotes for {portfolio.name}: {str(e)}", level='error')
    
    @admin.action(description='📊 Run EOD Update (incremental NAV)')
    def run_eod_update(self, request, queryset):
        from .services import PortfolioEngineV3
        for portfolio in queryset:
            try:
                result = PortfolioEngineV3.incremental_eod_update(portfolio)
                if result.get('status') == 'success':
                    self.message_user(
                        request,
                        f"✅ {portfolio.name}: NAV={result['nav']:.2f}, Value=${result['total_value']:,.2f}, Return={result['total_return_pct']:.2f}%"
                    )
                else:
                    self.message_user(
                        request,
                        f"⚠️ {portfolio.name}: {result.get('message', result.get('status'))}",
                        level='warning'
                    )
            except Exception as e:
                self.message_user(request, f"❌ Error running EOD for {portfolio.name}: {str(e)}", level='error')
    
    @admin.action(description='🔧 Full Rebuild V3 (prices, dividends, transactions, NAV)')
    def full_rebuild_v3(self, request, queryset):
        from .services import PortfolioEngineV3
        for portfolio in queryset:
            try:
                result = PortfolioEngineV3.full_rebuild(portfolio)
                nav_result = result.get('nav', {})
                self.message_user(
                    request,
                    f"✅ {portfolio.name}: Full rebuild complete. NAV={nav_result.get('final_nav', 0):.2f}, Return={nav_result.get('total_return_pct', 0):.2f}%"
                )
            except Exception as e:
                self.message_user(request, f"❌ Error rebuilding {portfolio.name}: {str(e)}", level='error')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'ticker', 'side', 'quantity', 'price', 'date')
    list_filter = ('portfolio', 'side', 'ticker')
    search_fields = ('ticker',)


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'type', 'amount', 'date')
    list_filter = ('portfolio', 'type')


@admin.register(MarketDataCache)
class MarketDataCacheAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'date', 'close_price', 'dividend', 'updated_at')
    list_filter = ('ticker',)
    search_fields = ('ticker',)


# ============================================================
# Portfolio V3 Admin
# ============================================================

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'portfolio', 'type', 'ticker', 'shares', 'amount', 'source_type')
    list_filter = ('portfolio', 'type', 'source_type')
    search_fields = ('ticker',)
    ordering = ['-date']
    actions = ['rebuild_transaction_log', 'recalculate_nav']
    
    @admin.action(description='Rebuild Transaction Log (from trades/cash/dividends)')
    def rebuild_transaction_log(self, request, queryset):
        from .services import PortfolioEngineV3
        portfolios = set(t.portfolio for t in queryset)
        for portfolio in portfolios:
            try:
                result = PortfolioEngineV3.build_transaction_log(portfolio)
                self.message_user(request, f"Rebuilt {result['transactions_created']} transactions for {portfolio.name}.")
            except Exception as e:
                self.message_user(request, f"Error rebuilding {portfolio.name}: {e}", level='error')
    
    @admin.action(description='Recalculate NAV')
    def recalculate_nav(self, request, queryset):
        from .services import PortfolioEngineV3
        portfolios = set(t.portfolio for t in queryset)
        for portfolio in portfolios:
            try:
                result = PortfolioEngineV3.calculate_nav(portfolio)
                self.message_user(request, f"Calculated {result['days_calculated']} days for {portfolio.name}. Final NAV: {result['final_nav']:.2f}")
            except Exception as e:
                self.message_user(request, f"Error calculating NAV for {portfolio.name}: {e}", level='error')


@admin.register(DailySnapshot)
class DailySnapshotAdmin(admin.ModelAdmin):
    list_display = ('date', 'portfolio', 'nav', 'total_value', 'total_units', 'cash_balance')
    list_filter = ('portfolio',)
    ordering = ['-date']


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'date', 'close_price')
    list_filter = ('ticker',)
    search_fields = ('ticker',)
    ordering = ['-date', 'ticker']


@admin.register(DividendHistory)
class DividendHistoryAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'date', 'amount')
    list_filter = ('ticker',)
    search_fields = ('ticker',)
    ordering = ['-date', 'ticker']


@admin.register(LiveQuote)
class LiveQuoteAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'price', 'updated_at')
    search_fields = ('ticker',)
    ordering = ['ticker']
    readonly_fields = ('updated_at',)
    actions = ['refresh_all_quotes']
    
    @admin.action(description='🔄 Refresh All Live Quotes')
    def refresh_all_quotes(self, request, queryset):
        from .models import Portfolio
        from .services import PortfolioEngineV3
        
        total_updated = 0
        for portfolio in Portfolio.objects.all():
            try:
                result = PortfolioEngineV3.update_live_quotes(portfolio)
                total_updated += result.get('updated', 0)
            except Exception as e:
                self.message_user(request, f"Error updating {portfolio.name}: {str(e)}", level='error')
        
        self.message_user(request, f"✅ Refreshed {total_updated} live quotes across all portfolios")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('fintest_active_edition', 'live_quotes_enabled', 'live_quotes_interval', 'last_quote_update')
    list_editable = ('fintest_active_edition',)
    list_display_links = None # Allow editing all fields including first one


# ============================================================
# Fintest Admin
# ============================================================

from .models import FintestQuestion, FintestResult

class ActiveFilter(admin.SimpleListFilter):
    title = 'Is Active'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(is_active=False)
        if self.value() == 'all':
            return queryset
        return queryset.filter(is_active=True)

@admin.register(FintestQuestion)
class FintestQuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'text_preview', 'edition', 'correct_answer', 'is_active')
    list_display_links = ('text_preview',)
    list_editable = ('order', 'is_active', 'correct_answer', 'edition')
    list_filter = (ActiveFilter, 'edition')
    
    fieldsets = (
        ('General', {
            'fields': ('edition', 'order', 'is_active', 'text')
        }),
        ('Options', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d', 'option_e'),
            'description': 'Leave options blank if fewer than 5 are needed.'
        }),
        ('Answer', {
            'fields': ('correct_answer', 'explanation')
        }),
    )

    def text_preview(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
    text_preview.short_description = "Question Text"


@admin.register(FintestResult)
class FintestResultAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'edition', 'age_group', 'experience', 'score_display', 'is_repeat_user')
    list_filter = ('edition', 'age_group', 'experience', 'created_at', 'is_repeat_user')
    readonly_fields = ('created_at', 'edition', 'answers_json', 'is_repeat_user')

    def score_display(self, obj):
        pct = int((obj.total_correct / obj.total_questions) * 100) if obj.total_questions > 0 else 0
        return f"{obj.total_correct}/{obj.total_questions} ({pct}%)"
