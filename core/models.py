"""
dpk-data models: Portfolio entities.
Lab-specific models (StockValuation, FinancialStatement, etc.) are in dpk-lab.
"""
from django.db import models


# ============================================================
# Portfolio Models
# ============================================================

class Portfolio(models.Model):
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Trade(models.Model):
    SIDE_CHOICES = [('BUY', 'Buy'), ('SELL', 'Sell')]
    
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='trades')
    ticker = models.CharField(max_length=10)
    date = models.DateTimeField()
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=15, decimal_places=4)
    price = models.DecimalField(max_digits=15, decimal_places=4)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} {self.ticker} @ {self.price}"


class CashTransaction(models.Model):
    TYPE_CHOICES = [('DEPOSIT', 'Deposit'), ('WITHDRAWAL', 'Withdrawal')]
    
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='cash_transactions')
    date = models.DateTimeField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} {self.amount} ({self.date.date()})"


class MarketDataCache(models.Model):
    ticker = models.CharField(max_length=10)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=15, decimal_places=4)
    dividend = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('ticker', 'date')
        indexes = [
            models.Index(fields=['ticker', 'date']),
        ]

    def __str__(self):
        return f"{self.ticker} - {self.date}: {self.close_price}"


class YearlyPerformance(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='yearly_performances')
    year = models.IntegerField()
    return_pct = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('portfolio', 'year')
        ordering = ['-year']

    def __str__(self):
        return f"{self.portfolio.name} - {self.year}: {self.return_pct}%"


class DailyPortfolioValuation(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='daily_valuations')
    date = models.DateField()
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2)
    market_value = models.DecimalField(max_digits=15, decimal_places=2)
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    daily_return = models.DecimalField(max_digits=10, decimal_places=6) # TWR for the day
    daily_dividend = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    external_cash_flow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    class Meta:
        unique_together = ('portfolio', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]

    def __str__(self):
        return f"{self.portfolio.name} - {self.date}: {self.total_value}"


class PortfolioDailyValueV2(models.Model):
    """
    Stores daily portfolio value for Portfolio Tracker v2.
    Simpler model focused on tracking total value over time.
    """
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='daily_values_v2')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    invested_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Holdings market value
    total_dividends = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Cumulative dividends
    total_deposits = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Cumulative deposits
    total_withdrawals = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Cumulative withdrawals

    class Meta:
        unique_together = ('portfolio', 'date')
        ordering = ['date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]

    def __str__(self):
        return f"{self.portfolio.name} - {self.date}: ${self.total_value}"


class YearlyTickerPerformance(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='yearly_ticker_performances')
    ticker = models.CharField(max_length=10)
    year = models.IntegerField()
    price_return = models.DecimalField(max_digits=10, decimal_places=2)
    div_return = models.DecimalField(max_digits=10, decimal_places=2)
    total_return = models.DecimalField(max_digits=10, decimal_places=2)
    dividend_cash = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('portfolio', 'ticker', 'year')
        ordering = ['ticker', '-year']
        indexes = [
            models.Index(fields=['portfolio', 'ticker', 'year']),
        ]

    def __str__(self):
        return f"{self.ticker} - {self.year}: {self.total_return}%"


# ============================================================
# Portfolio Tracker V3 Models - NAV/Unitization Engine
# ============================================================

class PriceHistory(models.Model):
    """
    Daily closing prices for all tickers.
    CASH always has price = 1.0
    """
    ticker = models.CharField(max_length=10, db_index=True)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=15, decimal_places=4)
    
    class Meta:
        unique_together = ('ticker', 'date')
        ordering = ['ticker', 'date']
        indexes = [
            models.Index(fields=['ticker', 'date']),
        ]
    
    def __str__(self):
        return f"{self.ticker} - {self.date}: ${self.close_price}"


class DividendHistory(models.Model):
    """
    Dividend payments by ticker (per share amount).
    """
    ticker = models.CharField(max_length=10, db_index=True)
    date = models.DateField()  # Ex-dividend date
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    
    class Meta:
        unique_together = ('ticker', 'date')
        ordering = ['ticker', 'date']
        indexes = [
            models.Index(fields=['ticker', 'date']),
        ]
    
    def __str__(self):
        return f"{self.ticker} - {self.date}: ${self.amount}"


class TransactionLog(models.Model):
    """
    Unified transaction log combining trades, cash transactions, and dividends.
    This is the source of truth for the NAV calculation loop.
    """
    TYPE_CHOICES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('DIVIDEND', 'Dividend'),
    ]
    SOURCE_CHOICES = [
        ('trade', 'Trade'),
        ('cash_transaction', 'Cash Transaction'),
        ('dividend', 'Dividend'),
    ]
    
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='transaction_logs')
    date = models.DateTimeField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    ticker = models.CharField(max_length=10, blank=True, null=True)  # For BUY/SELL/DIVIDEND
    shares = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    price = models.DecimalField(max_digits=15, decimal_places=4, blank=True, null=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # Total cash impact
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source_id = models.IntegerField(blank=True, null=True)  # ID from source table
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, blank=True, null=True)
    
    class Meta:
        ordering = ['date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
            models.Index(fields=['portfolio', 'type']),
        ]
    
    def __str__(self):
        if self.ticker:
            return f"{self.date.date()} {self.type} {self.ticker}: ${self.amount}"
        return f"{self.date.date()} {self.type}: ${self.amount}"


class DailySnapshot(models.Model):
    """
    Daily portfolio snapshot storing calculated NAV values.
    This is the output of the NAV calculation loop.
    """
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='daily_snapshots')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2)
    total_units = models.DecimalField(max_digits=15, decimal_places=6)
    nav = models.DecimalField(max_digits=15, decimal_places=4)  # NAV per unit
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    class Meta:
        unique_together = ('portfolio', 'date')
        ordering = ['date']
        indexes = [
            models.Index(fields=['portfolio', 'date']),
        ]
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.date}: NAV={self.nav}, Value=${self.total_value}"


class LiveQuote(models.Model):
    """
    Stores latest intraday prices for live display.
    Updated periodically during market hours via APScheduler.
    Used for display-only "today" calculations - not persisted to DailySnapshot until EOD.
    """
    ticker = models.CharField(max_length=10, unique=True, db_index=True)
    price = models.DecimalField(max_digits=15, decimal_places=4)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['ticker']
    
    def __str__(self):
        return f"{self.ticker}: ${self.price} (@ {self.updated_at})"


class SiteSettings(models.Model):
    """
    Singleton model for site-wide settings.
    Only one instance should exist.
    """
    INTERVAL_CHOICES = [
        (5, '5 minutes'),
        (15, '15 minutes'),
        (30, '30 minutes'),
        (60, '1 hour'),
    ]
    
    live_quotes_enabled = models.BooleanField(default=False, help_text="Enable automatic live quote updates during market hours")
    live_quotes_interval = models.IntegerField(choices=INTERVAL_CHOICES, default=15, help_text="How often to update live quotes (minutes)")
    last_quote_update = models.DateTimeField(null=True, blank=True, help_text="Last time quotes were updated")
    last_update_count = models.IntegerField(default=0, help_text="Number of tickers updated in last update")
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return "Site Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
