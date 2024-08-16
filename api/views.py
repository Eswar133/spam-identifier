import traceback
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from .models import Contact, Spam
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
#THRESHOLD to determine spam likelihood 
SPAM__THRESHOLD = 20

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    
    def post(self, request):
        try:
            data = request.data
            username = data.get('username')
            password = data.get('password')
            name = data.get('name')
            phone_number = data.get('phone_number')
            email = data.get('email', None)

            if User.objects.filter(username=username).exists():
                return Response({'error': 'Username already exists'}, status=400)

            if Contact.objects.filter(phone_number=phone_number, is_registered=True).exists():
                return Response({'error': 'Phone number already registered'}, status=400)

            user = User.objects.create_user(username=username, password=password, first_name=name)
            Contact.objects.create(
                user=user,
                name=name,
                phone_number=phone_number,
                email=email,
                is_registered=True  # Set to True for registered users
            )

            return Response({'message': 'User registered successfully'}, status=201)
        except Exception as e:
            print (traceback.print_exc(),flush=True)
            return Response({'message': 'User registeration failed:'+str(e)}, status=400)
            

class LoginView(APIView):
    permission_classes = []    

    def post(self, request):
        data = request.data
        username = data.get('username')
        password = data.get('password')
        

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return Response({'message': 'Login successful'})
        else:
            return Response({'error': 'Invalid credentials'}, status=400)

class SearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.GET.get('query', '')
        phone_number = request.GET.get('phone_number', '')
        page_number = request.GET.get('page', 1)
        results = {"exact-matches": [], "relevant-matches":[]}
        exact_contacts = []
        relevant_contacts = []
        if query:
            exact_contacts = Contact.objects.filter(name__startswith=query)
            relevant_contacts = Contact.objects.filter(name__icontains=query).exclude(id__in=exact_contacts)
        elif phone_number:
            exact_contacts = Contact.objects.filter(phone_number=phone_number, is_registered = True)
            if not exact_contacts.exists():
                exact_contacts = Contact.objects.filter(phone_number=phone_number)

        paginator_exact_contacts = Paginator(exact_contacts, 10)
        paginator_relevant_contacts = Paginator(relevant_contacts, 10)
        
        page_obj_exact_contacts = paginator_exact_contacts.get_page(page_number)
        page_obj_relevant_contacts = paginator_relevant_contacts.get_page(1)
        
        for contact in page_obj_exact_contacts:
            spam_records = Spam.objects.filter(phone_number=contact.phone_number)
            email = None
            if contact.user == request.user or request.user in contact.user.contacts.values_list('user', flat=True):
                email = contact.email
            #compute percentage of spam likelihood using THRESHOLD
            spam_likelihood = max(SPAM__THRESHOLD, spam_records.count())*100/SPAM__THRESHOLD 
            results["exact-matches"].append({
                'user_id': str(contact.id),
                'name': contact.name,
                'phone_number': contact.phone_number,
                'spam_likelihood':str(int(spam_likelihood))+ "%"   
            })

        
        for contact in page_obj_relevant_contacts:
            spam_records = Spam.objects.filter(phone_number=contact.phone_number)
            email = None
            if contact.user == request.user or request.user in contact.user.contacts.values_list('user', flat=True):
                email = contact.email
            #compute percentage of spam likelihood using THRESHOLD
            spam_likelihood = max(SPAM__THRESHOLD, spam_records.count())*100/SPAM__THRESHOLD 
            results["relevant-matches"].append({
                'user_id': str(contact.id),
                'name': contact.name,
                'phone_number': contact.phone_number,
                'spam_likelihood':str(int(spam_likelihood))+ "%"   
            })
            
        return Response({
            'count': exact_contacts.count(),
            'results': results,
            'page': page_number,
            'total_pages': paginator_exact_contacts.num_pages
        })

class SpamView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        page_number = int(request.GET.get("page",1))

        spam_records = Spam.objects.all()

        results = []
        paginator = Paginator(spam_records, 50)
        current_spam_records = paginator.get_page(page_number)
        for spam in current_spam_records:
            marked_by = [ user.username for user in spam.marked_by_users.all() ]
            results.append({
                'phone_number': spam.phone_number,
                'marked_by': {"count": len(marked_by), "users": marked_by }
            })
        response = {
            'count': spam_records.count(),
            'results': results,
            'page': page_number
            } 
        return Response(response,status=200)

    def post(self, request):
        data = request.data
        phone_number = data.get('phone_number')

        spam, created = Spam.objects.get_or_create(phone_number=phone_number)
        spam.marked_by_users.add(request.user)

        return Response({'message': 'Number marked as spam successfully'})

class ContactsListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        page_number = int(request.GET.get("page_number",1))
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

        response = { "page":page_number,
                    "count": contacts_list.count(),
                    "total-pages": paginator.num_pages,
                    "contacts": results }

        return Response(response,status=200)

class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, contact_id):
        contact = get_object_or_404(Contact, id=contact_id)
        spam_likelihood = Spam.objects.filter(phone_number=contact.phone_number).exists()

        contact_info = {
            'user_id': contact.user.id,
            'name': contact.name,
            'phone_number': contact.phone_number,
            'email':"",
            'spam_likelihood': spam_likelihood
        }
        current_user = request.user
        if contact.is_registered and contact.user == current_user:
            contact_info['email'] = contact.email
            
        return Response(contact_info)
