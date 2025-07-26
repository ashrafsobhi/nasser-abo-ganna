import datetime
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt # For webhook, if needed
from django.contrib import messages
from django import forms # Import forms here for WhatsAppAddressUpdateForm
from django.db import transaction
from django.utils import timezone
from .models import (
    Product, Category, Cart, CartItem, Customer, Order, OrderItem,
    Coupon, Promotion, FAQ, BlogPost, Wishlist, WishlistItem, Address, StoredPaymentMethod,
    PhoneOTP, PushSubscription, AboutPage, TeamMember, Notification
)
from .whatsapp_service import (
    send_product_added_to_cart_notification,
    send_cart_summary_notification,
    send_new_order_notification,
    send_order_confirmation_whatsapp
)
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm # New import
from django.contrib.auth import login, logout, update_session_auth_hash, views as auth_views # New import & alias
from django.contrib import messages # New import
from .forms import (
    CustomUserCreationForm, InquiryForm, CustomerProfileForm,
    ProfilePictureForm, AddressForm, PhoneNumberForm, OTPForm, UserDetailForm, UnifiedLoginForm,
    ChangePhoneNumberForm, AddPaymentMethodForm, UserProfileForm
)
from django.db.models import Q, Sum, Count # New import for Sum and Count
from django.conf import settings # New import
import hmac # New import for Kashier
import hashlib # New import for Kashier
from decimal import Decimal # New import
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie # New import for webhook
from django.utils import timezone
from django.urls import reverse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.http import HttpResponse, JsonResponse
from urllib.parse import urlencode # New import for urlencode
import firebase_admin
from firebase_admin import credentials, auth
from django.contrib.auth.models import User
import os
import random
from .whatsapp_service import send_whatsapp_otp
from .models import PhoneOTP, Customer
from .forms import PhoneNumberForm, OTPForm
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from uuid import UUID
import uuid # New import for UUID

# Initialize Firebase Admin SDK
try:
    cred_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase Admin SDK initialization error: {e}")


@csrf_exempt
def social_login_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            id_token = data.get('id_token')

            if not id_token:
                return JsonResponse({'status': 'error', 'message': 'ID token is missing.'}, status=400)

            try:
                decoded_token = auth.verify_id_token(id_token)
                uid = decoded_token['uid']
                email = decoded_token.get('email')
                name = decoded_token.get('name', '')

                # Check if user exists
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    # Create a new user
                    username = email.split('@')[0]
                    # Ensure username is unique
                    if User.objects.filter(username=username).exists():
                        username = f"{username}_{uid[:6]}"

                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=User.objects.make_random_password() # Set a random unusable password
                    )
                    user.first_name = name
                    user.save()

                # Log the user in
                login(request, user)

                # Ensure a customer object exists for the user
                Customer.objects.get_or_create(user=user)

                return JsonResponse({'status': 'success', 'message': 'User logged in successfully.'})

            except auth.InvalidIdTokenError:
                return JsonResponse({'status': 'error', 'message': 'Invalid ID token.'}, status=401)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body.'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed.'}, status=405)


# Helper function for Kashier Hash Generation
# This function is not used and contains a logic error, so it will be removed.

# Helper function for Kashier Signature Validation
def validateSignature(request_data, secret):
    queryString = ""
    # Sort keys for consistent hash generation (important for validation)
    sorted_keys = sorted([key for key in request_data.keys() if key != "signature" and key != "mode"])
    for key in sorted_keys:
        queryString += f"&{key}={request_data[key]}"

    queryString = queryString[1:]  # Remove the initial '&'
    secret = bytes(secret, 'utf-8')
    queryString = queryString.encode()
    signature = hmac.new(secret, queryString, hashlib.sha256).hexdigest()

    return "success" if signature == request_data.get("signature") else "failure"


# Create your views here.

def home(request):
    # You can fetch featured products, categories, etc. here
    # For now, let's just pass a simple context
    products = Product.objects.filter(available=True)[:8] # Get 8 available products
    categories = Category.objects.all()
    promotions = Promotion.objects.filter(active=True)
    faqs = FAQ.objects.filter(active=True).order_by('display_order')
    blog_posts = BlogPost.objects.filter(active=True).order_by('-published_date')[:2]

    context = {
        'products': products,
        'categories': categories,
        'promotions': promotions,
        'faqs': faqs,
        'blog_posts': blog_posts,
        'welcome_message': 'مرحباً بك في متجر الهدايا!'
    }
    return render(request, 'home.html', context)

def store_view(request):
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    selected_category_obj = None

    category_slug = request.GET.get('category')
    if category_slug:
        selected_category_obj = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=selected_category_obj)

    context = {
        'categories': categories,
        'products': products,
        'selected_category': category_slug,
        'selected_category_object': selected_category_obj
    }
    return render(request, 'store.html', context)

def product_detail(request, id):
    product = get_object_or_404(Product, id=id, available=True)
    context = {'product': product}
    return render(request, 'product.html', context)

def quick_view_data(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    data = {
        'id': product.id,
        'name': product.name,
        'price': f'{product.price:.2f}',
        'description': product.description,
        'image_url': product.image.url if product.image else None,
        'product_url': product.get_absolute_url(),
    }
    return JsonResponse(data)

def cart(request):
    if request.user.is_authenticated:
        customer, created = Customer.objects.get_or_create(user=request.user)
        cart, created = Cart.objects.get_or_create(customer=customer)
        items = cart.items.all()
    else:
        # For unauthenticated users, we can use session-based cart or simplify for now
        # For simplicity, let's assume no cart for unauthenticated users for now
        # In a real application, you'd handle anonymous sessions.
        cart = {'get_cart_total':0, 'get_cart_items':0}
        items = []

    context = {'cart': cart, 'items': items}
    return render(request, 'cart.html', context)

@login_required
def checkout(request):
    customer = request.user.customer
    cart, created = Cart.objects.get_or_create(customer=customer)
    items = cart.items.all()
    cart_total = cart.get_cart_total

    # Initialize variables
    final_total = cart_total
    discount_amount = 0
    discount_percentage = 0
    coupon_code = request.session.get('coupon_code', None)
    coupon = None

    # Apply coupon from session if it exists
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code, active=True, valid_from__lte=timezone.now(), valid_to__gte=timezone.now())
            discount_percentage = coupon.discount
            discount_amount = (Decimal(discount_percentage) / 100) * cart_total
            final_total = cart_total - discount_amount
        except Coupon.DoesNotExist:
            # Coupon is invalid, remove from session
            request.session['coupon_code'] = None
            coupon_code = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'apply_coupon':
            coupon_code_from_form = request.POST.get('coupon_code')
            if coupon_code_from_form:
                request.session['coupon_code'] = coupon_code_from_form
                return redirect('store:checkout') # Reload the page to apply the coupon
            else:
                messages.error(request, 'الرجاء إدخال رمز كوبون.')

        elif action == 'place_order':
            # Extract form data
            address = request.POST.get('address')
            phone = request.POST.get('phone')
            notes = request.POST.get('notes')
            payment_method = request.POST.get('payment_method')
            save_card = request.POST.get('save_card') == 'on'

            # Create the order
            order = Order.objects.create(
                customer=customer,
                shipping_address=address,
                phone_number=phone,
                notes=notes,
                total_before_discount=cart_total,
                final_total=final_total,
                coupon=coupon,
                payment_method=payment_method,
            )

            # Move cart items to order items
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )

            # Clear the cart and coupon from session
            cart.items.all().delete()
            request.session['coupon_code'] = None

            if payment_method == 'cod':
                order.payment_status = 'pending'
                order.status = 'processing'
                order.complete = True
                order.save()

                # Send WhatsApp notification to admin
                try:
                    send_new_order_notification(order)
                except Exception as e:
                    print(f"Failed to send new order WhatsApp notification: {e}")

                # Send WhatsApp confirmation message to customer (new functionality)
                try:
                    print(f"DEBUG: Attempting to send WhatsApp confirmation for COD Order ID: {order.id}")
                    send_order_confirmation_whatsapp(order, request)
                except Exception as e:
                    print(f"Failed to send WhatsApp confirmation for COD order: {e}")

                messages.success(request, 'تم استلام طلبك بنجاح! سيتم التواصل معك للتأكيد.')
                return redirect('store:account')

            elif payment_method == 'kashier':
                # Correctly build the request for Kashier HPP
                merchant_id = settings.KASHIER_MERCHANT_ID
                secret_key = settings.KASHIER_SERVICE_SECRET_KEY
                order_id = str(order.id)
                amount = f"{final_total:.2f}"
                currency = "EGP"
                mode = "test"
                redirect_url = request.build_absolute_uri(reverse('store:kashier_success'))

                # Build the parameters first
                params = {
                    'merchantId': merchant_id,
                    'orderId': order_id,
                    'amount': amount,
                    'currency': currency,
                    'mode': mode,
                    'merchantRedirect': redirect_url,
                    'lang': 'ar'
                }

                if save_card:
                    params['cardTokenization'] = 'true'

                # Create the string for the hash from the params, with keys sorted alphabetically
                # Exclude the hash itself from the hash string
                hash_string_parts = []
                for key in sorted(params.keys()):
                    if key != 'hash':
                        hash_string_parts.append(f"{key}={params[key]}")

                hash_string = "&".join(hash_string_parts)

                # Generate the hash
                payment_hash = hmac.new(
                    secret_key.encode('utf-8'),
                    hash_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()

                # Add the hash to the parameters
                params['hash'] = payment_hash

                # Using urllib.parse.urlencode to correctly format the query string
                query_string = urlencode(params)

                payment_url = f"{settings.KASHIER_BASE_URL}/?{query_string}"

                # Send WhatsApp confirmation message to customer BEFORE redirecting to Kashier
                try:
                    print(f"DEBUG: Attempting to send WhatsApp confirmation for Kashier Order ID: {order.id}")
                    send_order_confirmation_whatsapp(order, request)
                except Exception as e:
                    print(f"Failed to send WhatsApp confirmation for Kashier order: {e}")

                return redirect(payment_url)

    context = {
        'items': items,
        'cart_total': cart_total,
        'final_total': final_total,
        'discount_amount': discount_amount,
        'discount_percentage': discount_percentage,
        'coupon_code': coupon_code,
        'customer': customer,
    }
    return render(request, 'checkout.html', context)


def shareable_coupon_view(request, coupon_code):
    coupon = get_object_or_404(Coupon, code__iexact=coupon_code, active=True)
    context = {
        'coupon': coupon
    }
    return render(request, 'coupon_share.html', context)


def inquiry_view(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إرسال رسالتك بنجاح! سنتواصل معك قريباً.')
            return redirect('store:inquiry')
    else:
        form = InquiryForm()

    context = {
        'form': form
    }
    return render(request, 'inquiry.html', context)


@login_required
def wishlist_view(request):
    customer = request.user.customer
    wishlist, created = Wishlist.objects.get_or_create(customer=customer)
    items = wishlist.items.all()
    context = {
        'wishlist': wishlist,
        'items': items
    }
    return render(request, 'wishlist.html', context)

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    customer = request.user.customer
    wishlist, created = Wishlist.objects.get_or_create(customer=customer)

    # Prevent adding duplicates
    WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)

    messages.success(request, f'تمت إضافة "{product.name}" إلى قائمة مفضلاتك.')

    # Redirect back to the same page the user was on
    return redirect(request.META.get('HTTP_REFERER', 'store:home'))

@login_required
def remove_from_wishlist(request, item_id):
    item = get_object_or_404(WishlistItem, id=item_id, wishlist__customer=request.user.customer)
    product_name = item.product.name
    item.delete()
    messages.info(request, f'تمت إزالة "{product_name}" من قائمة مفضلاتك.')
    return redirect('store:wishlist')


@login_required
def generate_invoice_pdf(request, order_id):
    try:
        order = Order.objects.get(id=order_id, customer=request.user.customer)
    except Order.DoesNotExist:
        return HttpResponse("Order not found or you do not have permission to view it.", status=404)

    template_path = 'invoice.html'
    context = {'order': order}

    # Create a Django response object, and specify content_type as pdf
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    # find the template and render it.
    template = get_template(template_path)
    html = template.render(context)

    # create a pdf
    pisa_status = pisa.CreatePDF(
       html, dest=response)
    # if error then show some funy view
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required(login_url='store:login')
def account_view(request):
    # Ensure the user has a Customer profile
    customer, created = Customer.objects.get_or_create(user=request.user)

    # Retrieve related objects for the customer's account page
    orders = Order.objects.filter(customer=customer).order_by('-date_ordered')
    addresses = Address.objects.filter(customer=customer).order_by('-is_default', 'street_address')
    payment_methods = StoredPaymentMethod.objects.filter(customer=customer).order_by('-is_default')
    wishlist_items = WishlistItem.objects.filter(wishlist__customer=customer).select_related('product')

    # Forms for profile details and address
    user_form = UserProfileForm(instance=request.user) 
    customer_form = CustomerProfileForm(instance=customer)
    
    # Try to get the default address, or the first one if no default exists
    # If no address exists, address_instance will be None
    address_instance = addresses.filter(is_default=True).first() or addresses.first()
    address_form = AddressForm(instance=address_instance)
    
    add_payment_form = AddPaymentMethodForm() # New form instance
    phone_form = ChangePhoneNumberForm()
    picture_form = ProfilePictureForm(instance=customer)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'user_profile_update': # Added for UserProfileForm
            user_form = UserProfileForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, _('تم تحديث معلومات المستخدم بنجاح.'))
                return redirect(f"{reverse('store:account')}?tab=profile")

        elif form_type == 'customer_profile_update':
            customer_form = CustomerProfileForm(request.POST, instance=customer)
            if customer_form.is_valid():
                customer_form.save()
                messages.success(request, _('تم تحديث ملفك الشخصي بنجاح.'))
                return redirect(f"{reverse('store:account')}?tab=profile")
        
        elif form_type == 'address_update':
            address_form = AddressForm(request.POST, instance=address_instance)
            if address_form.is_valid():
                address = address_form.save(commit=False)
                address.customer = customer
                # If this is the first address, or the only address, make it default
                if not customer.addresses.exists() or address_form.cleaned_data.get('is_default'):
                    # Unset other default addresses for this customer
                    Address.objects.filter(customer=customer, is_default=True).update(is_default=False)
                    address.is_default = True
                address.save()
                messages.success(request, _('تم تحديث العنوان بنجاح.'))
                return redirect(f"{reverse('store:account')}?tab=address")

        elif form_type == 'picture_update':
            picture_form = ProfilePictureForm(request.POST, request.FILES, instance=customer)
            if picture_form.is_valid():
                picture_form.save()
                messages.success(request, _('تم تحديث صورتك الشخصية بنجاح.'))
                return redirect(f"{reverse('store:account')}?tab=profile")

        elif form_type == 'phone_change_request':
            phone_form = ChangePhoneNumberForm(request.POST)
            if phone_form.is_valid():
                new_phone = phone_form.cleaned_data['phone_number']
                otp_code = PhoneOTP.generate_otp()

                # Store new phone and OTP for verification
                PhoneOTP.objects.update_or_create(
                    phone_number=new_phone,
                    defaults={'otp': otp_code, 'is_verified': False, 'created_at': timezone.now()}
                )

                try:
                    send_whatsapp_otp(new_phone, otp_code)
                    request.session['new_phone_to_verify'] = new_phone
                    request.session['user_id_for_phone_change'] = request.user.id
                    messages.info(request, _('تم إرسال رمز التحقق إلى رقمك الجديد.'))
                    return redirect('store:verify_phone_change')
                except Exception as e:
                    messages.error(request, _('حدث خطأ أثناء إرسال رمز التحقق.'))

        elif form_type == 'add_payment_method':
            add_payment_form = AddPaymentMethodForm(request.POST)
            if add_payment_form.is_valid():
                payment_method = add_payment_form.save(commit=False)
                payment_method.customer = customer
                # Set as default if it's the first payment method, or if explicitly requested
                if not customer.payment_methods.exists():
                    payment_method.is_default = True
                payment_method.save()
                messages.success(request, _('تم إضافة طريقة الدفع بنجاح.'))
                return redirect(f"{reverse('store:account')}?tab=payment")
            else:
                messages.error(request, _('حدث خطأ أثناء إضافة طريقة الدفع. يرجى مراجعة البيانات.'))

    # Dashboard Statistics
    total_orders_count = orders.count()
    total_spending = orders.filter(complete=True).aggregate(Sum('final_total'))['final_total__sum'] or 0
    wishlist_items_count = WishlistItem.objects.filter(wishlist__customer=customer).count()
    cart_items_count = CartItem.objects.filter(cart__customer=customer).count()

    context = {
        'customer': customer,
        'orders': orders,
        'addresses': addresses,
        'payment_methods': payment_methods,
        'wishlist_items': wishlist_items,
        'user_form': user_form,
        'customer_form': customer_form,
        'address_form': address_form,
        'add_payment_form': add_payment_form,
        'phone_form': phone_form,
        'picture_form': picture_form,
        'total_orders_count': total_orders_count,
        'total_spending': total_spending,
        'wishlist_items_count': wishlist_items_count,
        'cart_items_count': cart_items_count,
        'active_tab': request.GET.get('tab', 'profile') # Get active tab from URL parameter
    }
    return render(request, 'account.html', context)

@login_required
def verify_phone_change(request):
    new_phone = request.session.get('new_phone_to_verify')
    user_id = request.session.get('user_id_for_phone_change')

    if not new_phone or not user_id or request.user.id != user_id:
        messages.error(request, _('طلب غير صالح أو انتهت صلاحية الجلسة.'))
        return redirect('store:account')

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data['otp']
            try:
                phone_otp = PhoneOTP.objects.get(phone_number=new_phone, otp=otp_entered.strip())

                if (timezone.now() - phone_otp.created_at).total_seconds() > 600:
                    messages.error(request, _('انتهت صلاحية رمز التحقق.'))
                    return redirect('store:verify_phone_change')

                # Update customer's phone number
                customer = Customer.objects.get(user_id=user_id)
                customer.phone_number = new_phone
                customer.save()

                # Clean up session
                del request.session['new_phone_to_verify']
                del request.session['user_id_for_phone_change']
                phone_otp.delete()

                messages.success(request, _('تم تحديث رقم هاتفك بنجاح!'))
                return redirect('store:account')

            except PhoneOTP.DoesNotExist:
                messages.error(request, _('رمز التحقق غير صحيح.'))

    else:
        form = OTPForm()

    return render(request, 'account/verify_phone_change.html', {'form': form})


@login_required
def add_address_view(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.customer = request.user.customer
            # Logic to handle default address
            if address.is_default:
                Address.objects.filter(customer=request.user.customer, is_default=True).update(is_default=False)
            address.save()
            messages.success(request, 'تمت إضافة العنوان بنجاح.')
        else:
            messages.error(request, 'حدث خطأ. يرجى مراجعة البيانات.')
    return redirect('store:account')

@login_required
def edit_address_view(request, address_id):
    address = get_object_or_404(Address, id=address_id, customer=request.user.customer)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save(commit=False)
            # Logic to handle default address
            if address.is_default:
                Address.objects.filter(customer=request.user.customer, is_default=True).exclude(id=address.id).update(is_default=False)
            address.save()
            messages.success(request, 'تم تحديث العنوان بنجاح.')
            return redirect('store:account')
    # This view is POST-only for now, redirecting on GET
    return redirect('store:account')

@login_required
def delete_address_view(request, address_id):
    address = get_object_or_404(Address, id=address_id, customer=request.user.customer)
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'تم حذف العنوان بنجاح.')
    return redirect('store:account')

@login_required
def set_default_payment_view(request, method_id):
    customer = request.user.customer
    # Reset current default
    StoredPaymentMethod.objects.filter(customer=customer, is_default=True).update(is_default=False)
    # Set new default
    method = get_object_or_404(StoredPaymentMethod, id=method_id, customer=customer)
    method.is_default = True
    method.save()
    messages.success(request, 'تم تحديث طريقة الدفع الافتراضية.')
    return redirect('store:account')

@login_required
def delete_payment_method_view(request, method_id):
    customer = request.user.customer
    method = get_object_or_404(StoredPaymentMethod, id=method_id, customer=customer)
    # Here you might also want to call Kashier's API to delete the token from their vault
    method.delete()
    messages.success(request, 'تم حذف طريقة الدفع بنجاح.')
    return redirect('store:account')

@login_required
@require_POST
def subscribe_to_push(request):
    try:
        data = json.loads(request.body)
        fcm_token = data.get('token')

        if not fcm_token:
            return JsonResponse({'status': 'error', 'message': 'FCM token is required.'}, status=400)

        # Using FCM token as the unique endpoint identifier
        # In a more complex scenario, you might want to store the full subscription object
        PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{fcm_token}",
            defaults={
                'p256dh': data.get('p256dh', fcm_token), # Use token as placeholder if not available
                'auth': data.get('auth', fcm_token) # Use token as placeholder if not available
            }
        )
        return JsonResponse({'status': 'success', 'message': 'Subscribed successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def order_detail_view(request, order_id):
    customer = request.user.customer
    try:
        order = Order.objects.get(id=order_id, customer=customer)
    except Order.DoesNotExist:
        messages.error(request, "الطلب غير موجود أو لا تملك صلاحية لعرضه.")
        return redirect('store:account')

    # Determine the recipient's display name
    if order.customer:
        recipient_display_name = order.customer.get_full_name()
    else:
        # For anonymous users, get the first line of the shipping address
        recipient_display_name = order.shipping_address.split('\n')[0].strip()

    # Define the ordered stages for the tracking timeline
    ordered_stages = ['address_pending', 'confirmed', 'processing', 'shipped', 'delivered']

    # Get the index of the current order status in the ordered_stages list
    try:
        current_stage_index = ordered_stages.index(order.status)
    except ValueError:
        current_stage_index = -1 # Status not in the ordered list (e.g., cancelled, returned)

    context = {
        'order': order,
        'recipient_display_name': recipient_display_name,
        'ordered_stages': ordered_stages, # Pass to template
        'current_stage_index': current_stage_index, # Pass to template
    }
    return render(request, 'order_detail.html', context)

def get_product_price(request):
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'error': 'Product ID is required.'}, status=400)
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({'price': str(product.price)}) # Convert Decimal to string for JSON
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def contact_view(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save(commit=False)
            if request.user.is_authenticated:
                inquiry.user = request.user
            inquiry.save()
            messages.success(request, 'تم إرسال استفسارك بنجاح! سنتصل بك قريباً.')
            return redirect('store:contact')
    else:
        initial_data = {}
        # If user is logged in, pre-fill the form
        if request.user.is_authenticated:
            # The name and email are on the User model, not the Customer model.
            initial_data['name'] = request.user.get_full_name() or request.user.username
            initial_data['email'] = request.user.email
            # Phone number is on the customer model
            if hasattr(request.user, 'customer'):
                initial_data['phone'] = request.user.customer.phone_number

        form = InquiryForm(initial=initial_data)

    return render(request, 'contact.html', {'form': form})

def about_view(request):
    try:
        about_page = AboutPage.objects.prefetch_related('team_members').first()
    except AboutPage.DoesNotExist:
        about_page = None
    
    context = {
        'about_page': about_page
    }
    return render(request, 'about.html', context)

@login_required
def notification_list_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark all notifications as read when the user views the list
    unread_notifications = notifications.filter(read=False)
    for notification in unread_notifications:
        notification.read = True
    Notification.objects.bulk_update(unread_notifications, ['read'])
    
    return render(request, 'notifications.html', {'notifications': notifications})

def privacy_policy_view(request):
    return render(request, 'privacy_policy.html')

def shipping_policy_view(request):
    return render(request, 'shipping_policy.html')

@login_required
def add_to_cart_from_detail(request, product_id):
    if not request.user.is_authenticated:
        messages.error(request, _("يجب تسجيل الدخول لإضافة منتجات إلى سلة التسوق."))
        return redirect('store:login')

    # Ensure the user has a Customer profile
    customer, created = Customer.objects.get_or_create(user=request.user)

    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(customer=customer)

    quantity = int(request.POST.get('quantity', 1))
    action = request.POST.get('action')

    if product.stock <= 0 or quantity <= 0:
        messages.error(request, 'المنتج غير متوفر حالياً.')
        return redirect('store:product_detail', id=product_id)

    if quantity > product.stock:
        messages.warning(request, f'الكمية المطلوبة غير متوفرة. المتوفر فقط: {product.stock}')
        return redirect('store:product_detail', id=product_id)

    cart_item, created = cart.items.get_or_create(product=product)

    # Add to existing quantity or set if new
    if created:
        cart_item.quantity = quantity
    else:
        cart_item.quantity += quantity

    # Ensure not to exceed stock
    if cart_item.quantity > product.stock:
        cart_item.quantity = product.stock
        messages.info(request, f'تم تعديل الكمية في السلة لتطابق المخزون المتاح: {product.stock}')

    cart_item.save()

    # Send WhatsApp notifications to admin
    try:
        send_product_added_to_cart_notification(product, customer, request)
        send_cart_summary_notification(cart, customer)
    except Exception as e:
        print(f"Failed to send 'add to cart' WhatsApp notification from detail view: {e}")

    if action == 'buy_now':
        messages.success(request, f'تم إضافة {product.name} إلى السلة. استكمل عملية الشراء.')
        return redirect('store:checkout')
    else: # Default action is 'add_to_cart'
        messages.success(request, f'تم إضافة {quantity} من "{product.name}" إلى سلتك بنجاح!')
        return redirect('store:cart')

@login_required
def add_to_cart(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('productId')
        action = data.get('action')

        if not product_id or not action:
            return JsonResponse({'status': 'error', 'message': 'Missing product ID or action.'}, status=400)

        customer = request.user.customer
        product = get_object_or_404(Product, id=product_id)
        cart, _ = Cart.objects.get_or_create(customer=customer)
        
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

        original_quantity = cart_item.quantity

        if action == 'add':
            # If the item was just created, its quantity is already 1 (the default).
            # We only increment it if it already existed in the cart.
            if not created:
                cart_item.quantity += 1
        
        elif action == 'remove':
            cart_item.quantity -= 1

        elif action == 'delete':
            cart_item.delete()
            # We can also send a summary notification after deletion
            try:
                send_cart_summary_notification(cart, customer)
            except Exception as e:
                print(f"Failed to send 'cart summary' WhatsApp notification after deletion: {e}")
            return JsonResponse({'status': 'success', 'message': 'Item removed successfully.'})

        # Ensure quantity does not exceed available stock
        if cart_item.quantity > product.stock:
            cart_item.quantity = product.stock
            # It's good to inform the user about this adjustment. 
            # This requires changes in frontend javascript to handle messages.
            # For now, we just cap the quantity.

        # If quantity is zero or less, remove the item. Otherwise, save the new quantity.
        if cart_item.quantity <= 0:
            cart_item.delete()
        else:
            cart_item.save()
        
        # Send a notification only if the cart's state has actually changed.
        if cart.items.count() > 0:
             try:
                # We send a summary, which is more appropriate for cart updates.
                send_cart_summary_notification(cart, customer)
             except Exception as e:
                print(f"Failed to send 'cart summary' WhatsApp notification from JSON API: {e}")

        return JsonResponse({'status': 'success', 'message': 'Cart updated successfully.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Customer.DoesNotExist:
        # This can happen if a user exists but a customer profile was not created.
        return JsonResponse({'status': 'error', 'message': 'User profile not found.'}, status=404)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)
    except Exception as e:
        # Log the full error for debugging purposes
        print(f"An unexpected error occurred in add_to_cart: {e}")
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Customer.objects.create(user=user, name=user.username, email=user.email) # Create a Customer profile
            login(request, user)
            messages.success(request, 'تم تسجيل حسابك بنجاح!')
            return redirect('store:home')
        else:
            messages.error(request, 'حدث خطأ أثناء التسجيل. يرجى تصحيح الأخطاء.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'تم تسجيل الخروج بنجاح.')
    return redirect('store:home')

@login_required
def profile_edit_view(request):
    customer = get_object_or_404(Customer, user=request.user)
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث ملفك الشخصي بنجاح!')
            return redirect('store:account')
        else:
            messages.error(request, 'حدث خطأ أثناء تحديث الملف الشخصي. يرجى تصحيح الأخطاء.')
    else:
        form = CustomerProfileForm(instance=customer)
    return render(request, 'account/profile_edit.html', {'form': form})

def search_products_view(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')

    products = Product.objects.all()
    categories = Category.objects.all() # Get all categories for the filter dropdown

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        ).distinct()

    if category_id:
        products = products.filter(category__id=category_id)

    context = {'products': products, 'query': query, 'categories': categories, 'selected_category': category_id}
    return render(request, 'search_results.html', context)

def kashier_success_view(request):
    # This view will be redirected to by Kashier after a successful payment.
    # You should verify the payment here using the webhook data or Kashier's API.
    # For now, we'll just show a success message.
    messages.success(request, 'تم الدفع بنجاح! شكراً لك على طلبك.')
    return redirect('store:home')

def kashier_failure_view(request):
    # This view will be redirected to by Kashier after a failed payment.
    messages.error(request, 'فشل الدفع. يرجى المحاولة مرة أخرى أو اختيار طريقة دفع أخرى.')
    return redirect('store:checkout')

@csrf_exempt # Disable CSRF token for webhook endpoint
def kashier_webhook_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # It's good practice to log the entire payload for debugging
            print("Kashier Webhook Payload:", data)

            # Extract necessary data for validation and order update
            event = data.get("event")
            payload = data.get("data", {})

            # Validate the signature using the raw request body
            # Note: Kashier's documentation on signature validation should be followed closely.
            # This is a generic implementation.
            # signature = request.headers.get('X-Kashier-Signature')
            # if not validate_kashier_signature(request.body, signature, settings.KASHIER_WEBHOOK_SECRET):
            #     return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=403)

            if event == "payment.success":
                order_id = payload.get('orderId')
                order = get_object_or_404(Order, id=order_id)
                order.payment_status = 'paid'
                order.complete = True
                order.transaction_id = payload.get('transactionId')
                order.save()

                # Check for and save tokenized card
                card_data = payload.get("card", {})
                token = card_data.get("token")

                if token and order.customer:
                    StoredPaymentMethod.objects.get_or_create(
                        customer=order.customer,
                        gateway_token=token,
                        defaults={
                            'card_brand': card_data.get("brand", "Unknown"),
                            'last_four_digits': card_data.get("last4", "0000"),
                        }
                    )
                    # If this is the first card, make it the default
                    if not order.customer.payment_methods.exclude(gateway_token=token).exists():
                         StoredPaymentMethod.objects.filter(gateway_token=token).update(is_default=True)

                return JsonResponse({'status': 'success'})

            elif event == "payment.failed":
                order_id = payload.get('orderId')
                order = get_object_or_404(Order, id=order_id)
                order.payment_status = 'failed'
                order.save()
                return JsonResponse({'status': 'failed', 'message': 'Payment failed'})

            return JsonResponse({'status': 'ignored', 'message': f'Event {event} not handled'})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # If the request is not a POST, it's likely a user being redirected by mistake.
    # Send them to the home page instead of showing a 405 error.
    messages.info(request, "العودة إلى الصفحة الرئيسية.")
    return redirect('store:home')


# --- Authentication Views ---

def unified_login_view(request):
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        form = UnifiedLoginForm(request.POST)
        if form.is_valid():
            login_identifier = form.cleaned_data.get('login_identifier')
            password = form.cleaned_data.get('password')

            # Use our custom backend to authenticate
            user = authenticate(request, username=login_identifier, password=password)

            if user is not None:
                login(request, user)
                # Redirect to the 'next' page if it exists, otherwise to the default
                next_page = request.GET.get('next')
                return redirect(next_page or settings.LOGIN_REDIRECT_URL)
            else:
                messages.error(request, _('بيانات الاعتماد غير صحيحة. يرجى المحاولة مرة أخرى.'))
    else:
        form = UnifiedLoginForm()

    return render(request, 'registration/login.html', {'form': form})

# Phone Authentication Views

def phone_login_request_otp(request):
    if request.method == 'POST':
        form = PhoneNumberForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']

            # Generate OTP
            otp_code = PhoneOTP.generate_otp()

            # Save OTP to the database
            PhoneOTP.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    'otp': otp_code,
                    'is_verified': False,
                    'created_at': timezone.now()
                }
            )

            # Send OTP via WhatsApp
            try:
                send_whatsapp_otp(phone_number, otp_code)
                messages.success(request, _('تم إرسال رمز التحقق إلى واتساب الخاص بك.'))
                request.session['phone_number_for_otp'] = phone_number
                return redirect('store:phone_login_verify_otp')
            except Exception as e:
                error_message = f"Error sending WhatsApp message to {phone_number}: {e}"
                print(error_message) # For debugging
                messages.error(request, _('حدث خطأ أثناء إرسال رمز التحقق. الرجاء المحاولة مرة أخرى.'))
                return redirect('store:login')

    # This part is for GET requests or invalid forms, redirect back to login
    return redirect('store:login')


def phone_login_verify_otp(request):
    phone_number = request.session.get('phone_number_for_otp')
    if not phone_number:
        messages.error(request, _('انتهت صلاحية الجلسة. الرجاء طلب رمز جديد.'))
        return redirect('store:login')

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data['otp']
            try:
                phone_otp = PhoneOTP.objects.get(phone_number=phone_number)

                # Check if OTP is still valid (e.g., within 10 minutes)
                time_difference = timezone.now() - phone_otp.created_at
                if time_difference.total_seconds() > 600:
                    messages.error(request, _('انتهت صلاحية رمز التحقق. الرجاء طلب رمز جديد.'))
                    return redirect('store:phone_login_verify_otp')

                # DEBUG: Print values to check comparison
                print(f"DEBUG: OTP Entered: '{otp_entered.strip()}' (Type: {type(otp_entered)})")
                print(f"DEBUG: OTP Stored:  '{phone_otp.otp.strip()}' (Type: {type(phone_otp.otp)})")

                # Compare OTPs after stripping any whitespace
                if phone_otp.otp and phone_otp.otp.strip() == otp_entered.strip():
                    phone_otp.is_verified = True
                    phone_otp.save()

                    # Find or create user
                    customer, created = Customer.objects.get_or_create(
                        phone_number=phone_number
                    )

                    if created:
                        # If the customer is new, we need a corresponding User object
                        # We can use the phone number to create a unique username
                        username = f"user_{phone_number.replace('+', '')}"
                        user, user_created = User.objects.get_or_create(
                            username=username,
                            defaults={'password': User.objects.make_random_password()}
                        )
                        customer.user = user
                        customer.name = username
                        customer.email = f"{username}@example.com" # Placeholder email
                        customer.save()

                    login(request, customer.user)
                    del request.session['phone_number_for_otp']
                    messages.success(request, _('تم تسجيل الدخول بنجاح.'))
                    return redirect(settings.LOGIN_REDIRECT_URL)
                else:
                    messages.error(request, _('رمز التحقق غير صحيح.'))
            except PhoneOTP.DoesNotExist:
                messages.error(request, _('حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.'))
                return redirect('store:login') # Redirect to login on critical error
    else:
        form = OTPForm()

    return render(request, 'registration/otp_verify.html', {'form': form, 'phone_number': phone_number})


# New Registration Flow
# ========================

def register_phone_request_otp(request):
    """ Step 1: User submits their phone number. """
    if request.method == 'POST':
        form = PhoneNumberForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']

            # Check if a customer with this phone number already exists
            if Customer.objects.filter(phone_number=phone_number).exists():
                messages.error(request, _("هذا الرقم مسجل بالفعل. الرجاء تسجيل الدخول."))
                return redirect('store:login')

            otp_code = PhoneOTP.generate_otp()
            PhoneOTP.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    'otp': otp_code,
                    'is_verified': False,
                    'created_at': timezone.now()
                }
            )
            try:
                send_whatsapp_otp(phone_number, otp_code)
                request.session['registration_phone_number'] = phone_number
                messages.success(request, _('تم إرسال رمز التحقق إلى واتساب الخاص بك.'))
                return redirect('store:register_phone_verify_otp')
            except Exception as e:
                messages.error(request, _('حدث خطأ أثناء إرسال رمز التحقق.'))
                print(f"WhatsApp sending error: {e}")

    else:
        form = PhoneNumberForm()

    return render(request, 'registration/register_phone_request.html', {'form': form})


def register_phone_verify_otp(request):
    """ Step 2: User submits the OTP. """
    phone_number = request.session.get('registration_phone_number')
    if not phone_number:
        messages.error(request, _('انتهت صلاحية الجلسة. الرجاء المحاولة مرة أخرى.'))
        return redirect('store:register_phone_request_otp')

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data['otp']
            try:
                phone_otp = PhoneOTP.objects.get(phone_number=phone_number, otp=otp_entered.strip())

                # Check expiry (e.g., 10 minutes)
                if (timezone.now() - phone_otp.created_at).total_seconds() > 600:
                    messages.error(request, _('انتهت صلاحية رمز التحقق.'))
                    return redirect('store:register_phone_verify_otp')

                phone_otp.is_verified = True
                phone_otp.save()

                request.session['verified_phone_number'] = phone_number
                del request.session['registration_phone_number']

                return redirect('store:register_phone_complete')

            except PhoneOTP.DoesNotExist:
                messages.error(request, _('رمز التحقق غير صحيح.'))

    else:
        form = OTPForm()

    return render(request, 'registration/register_phone_verify.html', {'form': form})


def register_phone_complete(request):
    """ Step 3: User sets their username and password. """
    phone_number = request.session.get('verified_phone_number')
    if not phone_number:
        messages.error(request, _('لم يتم التحقق من رقم الهاتف. الرجاء البدء من جديد.'))
        return redirect('store:register_phone_request_otp')

    if request.method == 'POST':
        form = UserDetailForm(request.POST) # Use the correct, custom form
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Create User and Customer
            user = User.objects.create_user(username=username, password=password)
            customer = Customer.objects.create(
                user=user,
                phone_number=phone_number
            )

            # Clean up session and log user in
            if 'verified_phone_number' in request.session:
                del request.session['verified_phone_number']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            messages.success(request, _('تم إنشاء حسابك وتسجيل دخولك بنجاح!'))
            return redirect(settings.LOGIN_REDIRECT_URL)
        else:
            # For better debugging if an error occurs again
            print("DEBUG: UserDetailForm is not valid.")
            print(form.errors.as_json())
            messages.error(request, _('الرجاء تصحيح الأخطاء الموجودة في النموذج.'))

    else:
        form = UserDetailForm() # Use the correct, custom form

    return render(request, 'registration/register_phone_complete.html', {'form': form})

def customer_invoice_public_view(request, invoice_uuid):
    from accounting.models import Invoice, InvoiceItem
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    invoice_items = invoice.items.all()
    context = {
        'invoice': invoice,
        'invoice_items': invoice_items,
        'site_name': _("متجر الهدايا"), # Can be fetched from SiteConfiguration if available
    }
    return render(request, 'store/customer_invoice_public.html', context)


@csrf_exempt
def processOrder(request):
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    customer_phone_number = data['form']['phone_number']
    customer_name = data['form']['name']

    # Update or create customer profile
    if request.user.is_authenticated:
        customer, created = Customer.objects.get_or_create(user=request.user)
        customer.phone_number = customer_phone_number
        # Assuming you have a name field or can derive it from user
        if not customer.user.first_name and customer_name:
            customer.user.first_name = customer_name
            customer.user.save()
        customer.save()
    else:
        # For guest checkout, create a temporary user and customer if phone_number is used for identification
        # Or, allow checkout as guest and store phone/name with the order only
        # For now, let's assume that the phone_number is enough for guest orders without a customer object tied to a user
        customer = None # No Django Customer object for anonymous guest here, details stored with order

    order = Order.objects.create(
        customer=customer, # This will be null for anonymous checkouts
        phone_number=customer_phone_number,
        shipping_address=data['form']['address'],
        total_before_discount=Decimal(data['order_total']),
        final_total=Decimal(data['final_total']),
        payment_method=data['payment_method'],
        transaction_id=transaction_id,
        status='address_pending', # Set initial status to pending address confirmation
    )

    # Handle order items
    for item_data in data['items']:
        product = Product.objects.get(id=item_data['product']['id'])
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item_data['quantity'],
            price=product.price  # Capture price at time of order
        )
        # Decrease product stock
        product.stock -= item_data['quantity']
        product.save()

    # Clear cart after order is processed
    if request.user.is_authenticated:
        customer_cart = Cart.objects.get(customer=customer)
        customer_cart.cartitem_set.all().delete()
    else:
        # For anonymous users, clear cart from session or handle as appropriate
        # Since cart is tied to a session, we would clear it from there.
        pass

    # Send new order notification to admin (existing functionality)
    send_new_order_notification(order)
    
    # Re-fetch the order to ensure UUID and other auto-generated fields are present
    # This is crucial as UUID is generated on initial save.
    order.refresh_from_db()
    print(f"DEBUG: Order UUID after refresh_from_db: {order.uuid}") # Added for debugging

    # Send WhatsApp confirmation message to customer (new functionality)
    print(f"DEBUG: Attempting to send WhatsApp confirmation for Order ID: {order.id}")
    send_order_confirmation_whatsapp(order, request)

    return JsonResponse('Payment submitted..', safe=False)



# New Form for Address Update
class WhatsAppAddressUpdateForm(forms.Form):
    # Using CharField for flexibility, could use TextField for multi-line
    new_address = forms.CharField(label=_("العنوان الجديد"), widget=forms.Textarea(attrs={'rows': 3}))



@csrf_exempt # Consider more robust security for production
def confirm_order_whatsapp(request, order_id, order_uuid):
    order = get_object_or_404(Order, id=order_id, uuid=order_uuid)

    # Check if the order is already confirmed or cancelled
    if order.status == 'confirmed':
        messages.info(request, _("تم تأكيد هذا الطلب مسبقًا."))
        return render(request, 'store/whatsapp_confirmation_status.html', {'order': order})
    elif order.status == 'cancelled_by_customer':
        messages.info(request, _("تم إلغاء هذا الطلب مسبقًا."))
        return render(request, 'store/whatsapp_confirmation_status.html', {'order': order})

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            with transaction.atomic():
                order.status = 'confirmed'
                order.save()
            messages.success(request, _("تم تأكيد طلبك بنجاح! سيتم البدء في تجهيزه."))
            return render(request, 'store/whatsapp_confirmation_status.html', {'order': order})

        elif action == 'edit_address':
            form = WhatsAppAddressUpdateForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    order.shipping_address = form.cleaned_data['new_address']
                    order.status = 'address_updated_pending_confirmation' # A new temporary status, or keep as 'address_pending'
                    order.save()
                messages.success(request, _("تم تحديث العنوان بنجاح. سيتم مراجعة الطلب."))
                return render(request, 'store/whatsapp_confirmation_status.html', {'order': order})
            else:
                messages.error(request, _("حدث خطأ في تحديث العنوان."))
                # Fall through to display form with errors
        
        elif action == 'cancel':
            with transaction.atomic():
                order.status = 'cancelled_by_customer'
                order.save()
            messages.warning(request, _("تم إلغاء طلبك بنجاح."))
            return render(request, 'store/whatsapp_confirmation_status.html', {'order': order})

    else: # GET request
        form = WhatsAppAddressUpdateForm(initial={'new_address': order.shipping_address})

    context = {
        'order': order,
        'form': form,
        'current_address': order.shipping_address, # Pass current address for display
    }
    return render(request, 'store/whatsapp_order_confirmation.html', context)
