from django.core.management.base import BaseCommand
from api.models import Contact, Spam
from django.contrib.auth.models import User
from faker import Faker
import random

class Command(BaseCommand):
    help = 'Populate the database with sample data'

    def handle(self, *args, **kwargs):
        fake = Faker()

        num_users = 100
        num_contacts_per_user = 10

        for _ in range(num_users):
            while True:
                username = fake.user_name() + str(random.randint(1000, 9999))
                if not User.objects.filter(username=username).exists():
                    break

            password = "password123"
            name = fake.name()
            phone_number = fake.phone_number()
            email = fake.email()
            
            user = User.objects.create_user(username=username, password=password, first_name=name)
            Contact.objects.create(user=user, name=name, phone_number=phone_number, email=email)
            
            for _ in range(num_contacts_per_user):
                contact_name = fake.name()
                contact_phone_number = fake.phone_number()
                contact_email = fake.email() if random.choice([True, False]) else None
                
                Contact.objects.create(user=user, name=contact_name, phone_number=contact_phone_number, email=contact_email)

        self.stdout.write(self.style.SUCCESS(f"Populated {num_users} users with {num_users * num_contacts_per_user} contacts."))
