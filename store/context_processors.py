from .models import Customer, SiteConfiguration, Cart, Notification
from django.conf import settings

def global_context(request):
    user_data = request.user
    customer_obj = None
    site_config = None
    cart_items_count = 0
    notifications = []
    unread_notifications_count = 0

    if request.user.is_authenticated:
        try:
            customer_obj = Customer.objects.get(user=request.user)
            cart, created = Cart.objects.get_or_create(customer=customer_obj)
            cart_items_count = cart.get_cart_items if cart else 0
        except Customer.DoesNotExist:
            customer_obj = None

        # Fetch notifications for the logged-in user
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        unread_notifications_count = Notification.objects.filter(user=request.user, read=False).count()

    # Fetch the first SiteConfiguration object, or None if it doesn't exist
    try:
        site_config = SiteConfiguration.objects.first()
    except SiteConfiguration.DoesNotExist:
        site_config = None

    context = {
        'user': user_data,
        'customer': customer_obj,
        'site_config': site_config,  # Add site_config to the context
        'cart_items_count': cart_items_count,
        'BASE_URL': settings.BASE_URL,
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
    }
    return context 