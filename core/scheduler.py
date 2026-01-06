"""
Portfolio price update scheduler using APScheduler.

This module runs background tasks to:
1. Update live quotes every 15 minutes during market hours
2. Perform end-of-day updates after market close

To start the scheduler, import and call start_scheduler() in your Django app's ready() method
or run it as a standalone process.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

logger = logging.getLogger(__name__)

scheduler = None


def update_live_quotes_job():
    """
    Job to update live quotes for all portfolios.
    Runs every 15 minutes during market hours.
    """
    from core.models import Portfolio, SiteSettings
    from core.services import PortfolioEngineV3
    from django.utils import timezone
    
    # Only run if market is open
    if not PortfolioEngineV3.is_us_market_open():
        logger.info("[Scheduler] Market is closed, skipping live quote update")
        return
    
    logger.info("[Scheduler] Running live quote update...")
    
    total_updated = 0
    for portfolio in Portfolio.objects.all():
        try:
            result = PortfolioEngineV3.update_live_quotes(portfolio)
            updated = result.get('updated', 0)
            total_updated += updated
            logger.info(
                f"[Scheduler] {portfolio.name}: Updated {updated} quotes"
            )
        except Exception as e:
            logger.error(f"[Scheduler] Error updating {portfolio.name}: {e}")
    
    # Update SiteSettings with last update time
    try:
        settings = SiteSettings.get_settings()
        settings.last_quote_update = timezone.now()
        settings.last_update_count = total_updated
        settings.save()
        logger.info(f"[Scheduler] Recorded update: {total_updated} tickers at {settings.last_quote_update}")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to update SiteSettings: {e}")


def eod_update_job():
    """
    Job to perform end-of-day updates for all portfolios.
    Runs once after market close (4:30 PM ET).
    """
    from core.models import Portfolio
    from core.services import PortfolioEngineV3
    
    logger.info("[Scheduler] Running end-of-day update...")
    
    for portfolio in Portfolio.objects.all():
        try:
            result = PortfolioEngineV3.incremental_eod_update(portfolio)
            if result.get('status') == 'success':
                logger.info(
                    f"[Scheduler] {portfolio.name}: EOD NAV={result['nav']:.2f}"
                )
            else:
                logger.warning(
                    f"[Scheduler] {portfolio.name}: {result.get('message', result.get('status'))}"
                )
        except Exception as e:
            logger.error(f"[Scheduler] EOD error for {portfolio.name}: {e}")


def start_scheduler():
    """
    Start the APScheduler with configured jobs.
    Should be called once when Django starts.
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running")
        return
    
    scheduler = BackgroundScheduler()
    
    # Live quote update: every 15 minutes, Monday-Friday, 9:30 AM - 4:00 PM ET
    # Using cron expression for simplicity
    scheduler.add_job(
        update_live_quotes_job,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour='9-15',  # 9 AM to 3 PM (we check market hours in job)
            minute='*/15',  # Every 15 minutes
            timezone='US/Eastern'
        ),
        id='live_quotes',
        name='Update Live Quotes',
        replace_existing=True
    )
    
    # Also run at 4:00 PM for last update before close
    scheduler.add_job(
        update_live_quotes_job,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour='16',
            minute='0',
            timezone='US/Eastern'
        ),
        id='live_quotes_close',
        name='Update Live Quotes (Close)',
        replace_existing=True
    )
    
    # End-of-day update: 4:30 PM ET, Monday-Friday
    scheduler.add_job(
        eod_update_job,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour='16',
            minute='30',
            timezone='US/Eastern'
        ),
        id='eod_update',
        name='End of Day Update',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("[Scheduler] Portfolio price scheduler started")
    
    return scheduler


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("[Scheduler] Portfolio price scheduler stopped")
