from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.views import View
from django.core.paginator import Paginator
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import logout
from .models import Contact, Spam
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import traceback

SPAM__THRESHOLD = 20

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        try:
            data = request.POST
            username = data.get('username')
            password = data.get('password')
            name = data.get('name')
            phone_number = data.get('phone_number')
            email = data.get('email', None)

            if User.objects.filter(username=username).exists():
                return render(request, 'register.html', {'error': 'Username already exists'})

            if Contact.objects.filter(phone_number=phone_number, is_registered=True).exists():
                return render(request, 'register.html', {'error': 'Phone number already registered'})

            user = User.objects.create_user(username=username, password=password, first_name=name)
            Contact.objects.create(
                user=user,
                name=name,
                phone_number=phone_number,
                email=email,
                is_registered=True
            )
            return redirect('login')
        except Exception as e:
            print(traceback.print_exc(), flush=True)
            return render(request, 'register.html', {'error': f'User registration failed: {str(e)}'})


class LoginView(View):
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        data = request.POST
        username = data.get('username')
        password = data.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})


class SearchView(View):
    def get(self, request):
        query = request.GET.get('query', '')
        phone_number = request.GET.get('phone_number', '')
        page_number = request.GET.get('page', 1)
        results = {"exact_matches": [], "relevant_matches": []}
        exact_contacts = Contact.objects.none()
        relevant_contacts = Contact.objects.none()

        if query:
            exact_contacts = Contact.objects.filter(name__startswith=query)
            relevant_contacts = Contact.objects.filter(name__icontains=query).exclude(id__in=exact_contacts)
        elif phone_number:
            exact_contacts = Contact.objects.filter(phone_number=phone_number, is_registered=True)
            if not exact_contacts.exists():
                exact_contacts = Contact.objects.filter(phone_number=phone_number)

        paginator_exact_contacts = Paginator(exact_contacts, 10)
        page_obj_exact_contacts = paginator_exact_contacts.get_page(page_number)

        for contact in page_obj_exact_contacts:
            spam_records = Spam.objects.filter(phone_number=contact.phone_number)
            spam_likelihood = max(SPAM__THRESHOLD, spam_records.count()) * 100 / SPAM__THRESHOLD
            results["exact_matches"].append({
                'user_id': str(contact.id),
                'name': contact.name,
                'phone_number': contact.phone_number,
                'spam_likelihood': str(int(spam_likelihood)) + "%"   
            })

        return render(request, 'search.html', {
            'count': exact_contacts.count(),
            'results': results,
            'page': page_number,
            'total_pages': paginator_exact_contacts.num_pages,
            'page_range': paginator_exact_contacts.page_range  # Add this line
        })


class SpamView(View):
    def get(self, request):
        page_number = int(request.GET.get("page", 1))
        spam_records = Spam.objects.all()

        results = []
        paginator = Paginator(spam_records, 50)
        current_spam_records = paginator.get_page(page_number)
        for spam in current_spam_records:
            marked_by = [user.username for user in spam.marked_by_users.all()]
            results.append({
                'phone_number': spam.phone_number,
                'marked_by': {"count": len(marked_by), "users": marked_by}
            })

        response = {
            'count': spam_records.count(),
            'results': results,
            'page': page_number
        }
        return render(request, 'spam.html', response)

    def post(self, request):
        data = request.POST
        phone_number = data.get('phone_number')

        spam, created = Spam.objects.get_or_create(phone_number=phone_number)
        spam.marked_by_users.add(request.user)

        return redirect('contacts_list')


class ContactsListView(View):
    def get(self, request):
        page_number = int(request.GET.get("page_number", 1))
        contacts_list = Contact.objects.filter().order_by('name').distinct()
        results = []

        paginator = Paginator(contacts_list, 50)
        current_page_contacts = paginator.get_page(page_number)
        for contact in current_page_contacts:
            spam_likelihood = Spam.objects.filter(phone_number=contact.phone_number).exists()
            results.append({
                'user_id': contact.user.id,
                'name': contact.name,
                'phone_number': contact.phone_number,
                'email': contact.email,
                'spam_likelihood': spam_likelihood
            })

        page_range = paginator.page_range
        response = {
            "page": page_number,
            "count": contacts_list.count(),
            "total_pages": paginator.num_pages,
            "contacts": results,
            "page_range": page_range,
        }
        return render(request, 'contacts.html', response)


class ContactDetailView(View):
    def get(self, request, contact_id):
        contact = get_object_or_404(Contact, id=contact_id)
        spam_likelihood = Spam.objects.filter(phone_number=contact.phone_number).exists()

        contact_info = {
            'user_id': contact.user.id,
            'name': contact.name,
            'phone_number': contact.phone_number,
            'email': "",
            'spam_likelihood': spam_likelihood
        }
        current_user = request.user
        if contact.is_registered and contact.user == current_user:
            contact_info['email'] = contact.email

        return render(request, 'contact_detail.html', contact_info)

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')