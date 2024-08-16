from django.contrib.auth.models import User
from django.db import models

class Contact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    is_registered = models.BooleanField(default=False)
    def __str__(self):
        return f"{self.name} ({self.phone_number})"

class Spam(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    marked_by_users = models.ManyToManyField(User, related_name='marked_spam', blank=True)

    def __str__(self):
        return f"Spam: {self.phone_number}"
