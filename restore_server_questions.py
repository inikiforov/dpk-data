import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import FintestQuestion

def restore_questions():
    print("--- Restoring User-Edited Questions ---")
    
    # 1. Identify the questions created by the recent seed script
    # We assume these are the ones with the highest IDs
    all_questions = FintestQuestion.objects.order_by('-id')
    
    if not all_questions.exists():
        print("No questions found.")
        return

    print(f"Total questions in DB: {all_questions.count()}")
    
    # The seed script creates exactly 11 questions. 
    # Let's inspect the last 11 created (most recent).
    recent_batch = all_questions[:11]
    
    print("\nMost recent 11 questions (likely the unwanted duplicates):")
    for q in recent_batch:
        print(f"[ID: {q.id}] {q.text[:50]}... (Active: {q.is_active})")
        
    confirm = input("\nDo you want to DELETE these 11 questions and re-activate the previous ones? (yes/no): ")
    
    if confirm.lower() == 'yes':
        # Delete the unwanted new ones
        ids_to_delete = [q.id for q in recent_batch]
        FintestQuestion.objects.filter(id__in=ids_to_delete).delete()
        print(f"Deleted questions: {ids_to_delete}")
        
        # Reactivate the remaining ones
        # We assume the user wants ALL remaining questions active, or at least the most recent set.
        # Let's limit to the previous 11 for safety, or just activate all and let user manage in admin.
        # Safest is to activate the *next* 11 most recent ones.
        
        remaining_questions = FintestQuestion.objects.order_by('-id')[:11]
        for q in remaining_questions:
            q.is_active = True
            q.save()
            print(f"Re-activated: [ID: {q.id}] {q.text[:50]}...")
            
        print("\nDone! Please verify on the site.")
    else:
        print("Operation cancelled.")

if __name__ == '__main__':
    restore_questions()
