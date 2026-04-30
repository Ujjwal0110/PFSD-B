import os
import django
import sys

# Setup django environment
sys.path.append(os.path.join(os.getcwd(), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User

def populate_member_ids():
    users = User.objects.filter(member_id__isnull=True) | User.objects.filter(member_id='')
    print(f"Found {users.count()} users to update.")
    for user in users:
        user.save() # The save() method handles auto-generation
        print(f"Updated {user.username} with ID: {user.member_id}")

if __name__ == "__main__":
    populate_member_ids()
