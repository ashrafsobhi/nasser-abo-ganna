from django.urls import path
from . import views
from . import admin_views
from django.contrib.auth import login, logout, update_session_auth_hash, views as auth_views # Import auth views
from django.contrib import messages # Import
from .forms import (
    CustomUserCreationForm, InquiryForm, CustomerProfileForm,
    ProfilePictureForm, AddressForm, PhoneNumberForm, OTPForm
)
from django.db.models import Q # Import
from django.conf import settings # Import
from urllib.parse import urlencode # Import for urlencode
import firebase_admin
from firebase_admin import credentials, auth
from django.contrib.auth.models import User
import os
import random
from .whatsapp_service import send_whatsapp_otp
from .models import PhoneOTP

app_name = 'store'

urlpatterns = [
    # Admin-specific URLs
    path('admin/statistics/', admin_views.statistics_view, name='admin_statistics'),

    # Auth URLs
    path('login/', views.unified_login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('register/', views.register_view, name='register'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    
    # Phone Login (Passwordless)
    path('phone-login/', views.phone_login_request_otp, name='phone_login_request_otp'),
    path('phone-login/verify/', views.phone_login_verify_otp, name='phone_login_verify_otp'),

    # New Phone Registration
    path('register/phone/', views.register_phone_request_otp, name='register_phone_request_otp'),
    path('register/phone/verify/', views.register_phone_verify_otp, name='register_phone_verify_otp'),
    path('register/phone/complete/', views.register_phone_complete, name='register_phone_complete'),

    # Account Management
    path('account/', views.account_view, name='account'),
    path('account/verify-phone-change/', views.verify_phone_change, name='verify_phone_change'),

    # Frontend URLs
    path('', views.home, name='home'),
    path('store/', views.store_view, name='store'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('quick-view/<int:product_id>/', views.quick_view_data, name='quick_view_data'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('address/add/', views.add_address_view, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address_view, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address_view, name='delete_address'),
    path('payment-method/set-default/<int:method_id>/', views.set_default_payment_view, name='set_default_payment'),
    path('payment-method/delete/<int:method_id>/', views.delete_payment_method_view, name='delete_payment_method'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('invoice/<int:order_id>/', views.generate_invoice_pdf, name='generate_invoice'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('shipping-policy/', views.shipping_policy_view, name='shipping_policy'),
    path('add_to_cart/', views.add_to_cart, name='add_to_cart'),
    path('add_from_detail/<int:product_id>/', views.add_to_cart_from_detail, name='add_to_cart_from_detail'),
    path('coupon/<str:coupon_code>/', views.shareable_coupon_view, name='shareable_coupon'),
    path('search/', views.search_products_view, name='search'),
    path('inquiry/', views.inquiry_view, name='inquiry'),
    path('kashier/success/', views.kashier_success_view, name='kashier_success'),
    path('kashier/failure/', views.kashier_failure_view, name='kashier_failure'),
    path('kashier/webhook/', views.kashier_webhook_view, name='kashier_webhook'),
    path('social-login/', views.social_login_view, name='social_login'),
    path('orders/<int:order_id>/<uuid:order_uuid>/confirm-whatsapp/', views.confirm_order_whatsapp, name='confirm_order_whatsapp'),

    # Push Notifications
    path('subscribe-push/', views.subscribe_to_push, name='subscribe_push'),

    # Notifications
    path('notifications/', views.notification_list_view, name='notification_list'),

    # AJAX endpoints
    path('get-product-price/', views.get_product_price, name='get_product_price'),

    # Public Invoice View (for sharing with customers)
    path('public-invoice/<uuid:invoice_uuid>/', views.customer_invoice_public_view, name='customer_invoice_public'),

    # Fallback for registration to handle both GET and POST
    path('register/', views.register_view, name='register'),
] 