import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import FintestQuestion, SiteSettings

def debug_fintest():
    print("--- Fintest Debug Info ---")
    
    # 1. Check Settings
    settings = SiteSettings.get_settings()
    print(f"Active Edition in Settings: '{settings.fintest_active_edition}'")
    
    # 2. Check Questions
    all_qs = FintestQuestion.objects.all().order_by('id')
    print(f"Total Questions in DB: {all_qs.count()}")
    
    active_qs = all_qs.filter(is_active=True)
    print(f"Total ACTIVE Questions: {active_qs.count()}")
    
    active_in_edition = active_qs.filter(edition=settings.fintest_active_edition)
    print(f"Total ACTIVE Questions in edition '{settings.fintest_active_edition}': {active_in_edition.count()}")
    
    print("\nListing ALL Questions:")
    print(f"{'ID':<5} | {'Active':<6} | {'Edition':<8} | {'Order':<5} | {'Text Preview'}")
    print("-" * 60)
    for q in all_qs:
        text_prev = (q.text[:30] + '..') if len(q.text) > 30 else q.text
        print(f"{q.id:<5} | {str(q.is_active):<6} | {q.edition:<8} | {q.order:<5} | {text_prev}")
        
    print("\nDone.")

if __name__ == '__main__':
    debug_fintest()
