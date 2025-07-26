import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from .models import Order # Import Order model
import logging

logger = logging.getLogger(__name__)


def send_whatsapp_otp(phone_number, otp_code):
    """
    Sends a one-time password to the user's WhatsApp number.
    """
    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    message = _("رمز التحقق الخاص بك هو: {}").format(otp_code)
    
    payload = {
        'token': settings.ULTRMSG_TOKEN,
        'to': phone_number,
        'body': message
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        print(f"WhatsApp OTP response to {phone_number}: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp OTP to {phone_number}: {e}")
        raise  # Re-raise the exception to be handled by the calling view

def send_product_added_to_cart_notification(product, customer, request):
    """
    Sends a notification with the product image and details to the admin.
    """
    if not settings.WHATSAPP_ADMIN_NUMBER:
        return

    # 1. Send Product Image
    image_url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/image"
    product_image_url = request.build_absolute_uri(product.image.url) if product.image else None
    
    # Use customer.user.username or customer.get_full_name() for registered customers
    # For guest customers, the name might be available in the order details if passed
    customer_display_name = customer.get_full_name() if customer else _("عميل غير معروف")

    caption = (
        f"*{_('تمت إضافة منتج إلى السلة')}*\n\n"
        f"👤 *{_('العميل')}:* {customer_display_name}\n"
        f"🛍️ *{_('المنتج')}:* {product.name}\n"
        f"💰 *{_('السعر')}:* {product.price} EGP\n"
    )

    if product_image_url:
        payload = {
            'token': settings.ULTRMSG_TOKEN,
            'to': settings.WHATSAPP_ADMIN_NUMBER,
            'image': product_image_url,
            'caption': caption
        }
        try:
            requests.post(image_url, data=payload)
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp image notification: {e}")

def send_cart_summary_notification(cart, customer):
    """
    Sends a summary of the current cart to the admin.
    """
    if not settings.WHATSAPP_ADMIN_NUMBER:
        return

    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    
    items_list = ""
    for item in cart.items.all():
        items_list += f"- {item.quantity} x {item.product.name} @ {item.product.price} EGP\n"

    customer_display_name = customer.get_full_name() if customer else _("عميل غير معروف")

    message_body = (
        f"*{_('تحديث سلة المشتريات')}*\n\n"
        f"👤 *{_('العميل')}:* {customer_display_name}\n\n"
        f"*_{_('محتويات السلة الحالية')}:_*\n"
        f"{items_list}\n"
        f"---------------------\n"
        f"*{_('إجمالي السلة')}:* {cart.get_cart_total} EGP"
    )

    payload = {
        'token': settings.ULTRMSG_TOKEN,
        'to': settings.WHATSAPP_ADMIN_NUMBER,
        'body': message_body
    }
    try:
        requests.post(url, data=payload)
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp cart summary: {e}")

def send_new_order_notification(order):
    """
    Sends a detailed notification for a new order to the admin.
    """
    if not settings.WHATSAPP_ADMIN_NUMBER:
        return

    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    
    items_list = ""
    for item in order.orderitem_set.all():
        items_list += f"- {item.quantity} x {item.product.name} @ {item.price} EGP\n"

    # Use order.customer.get_full_name() or fall back to an empty string if customer is None
    customer_display_name = order.customer.get_full_name() if order.customer else ""
    customer_username = order.customer.user.username if order.customer and order.customer.user else ""
    # If the customer is anonymous and name was passed with the order, use that.
    # For this implementation, we'll use the phone number or a generic name if no customer object.
    if not customer_display_name and not customer_username:
        customer_display_name = _("عميل زائر") # Fallback for anonymous users
    elif not customer_display_name:
        customer_display_name = customer_username # Use username if full name not available

    message_body = (
        f"🎉 *{_('طلب جديد تم استلامه!')}* 🎉\n\n"
        f"🔢 *{_('رقم الطلب')}:* {order.id}\n"
        f"👤 *{_('العميل')}:* {customer_display_name}\n"
        f"📞 *{_('رقم هاتف العميل')}:* {order.phone_number}\n"
        f"📍 *{_('عنوان الشحن')}:* {order.shipping_address}\n\n"
        f"*_{_('المنتجات المطلوبة')}:_*\n"
        f"{items_list}\n"
        f"---------------------\n"
        f"💸 *{_('المبلغ قبل الخصم')}:* {order.total_before_discount} EGP\n"
        f"💰 *{_('المبلغ النهائي')}:* {order.final_total} EGP\n"
        f"💳 *{_('طريقة الدفع')}:* {order.get_payment_method_display()}\n"
        f"📋 *{_('حالة الطلب')}:* {order.get_status_display()}"
    )

    payload = {
        'token': settings.ULTRMSG_TOKEN,
        'to': settings.WHATSAPP_ADMIN_NUMBER,
        'body': message_body
    }
    try:
        requests.post(url, data=payload)
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp new order notification: {e}")

def send_order_status_update_notification(order):
    """
    Sends a WhatsApp notification to the customer about their order status update.
    """
    if not order.phone_number or not settings.ULTRMSG_INSTANCE_ID or not settings.ULTRMSG_TOKEN:
        print("Missing phone number or WhatsApp API credentials for status update notification.")
        return

    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    
    # Customize the message for status update
    message_body = (
        f"🔔 *{_('تحديث حالة طلبك!')}* 🔔\n\n"
        f"*{_('عزيزي العميل')},*\n"
        f"{_('يسعدنا إعلامك بأن حالة طلبك رقم')} *#{order.id}* "
        f"{_('قد تغيرت إلى')}: *{order.get_status_display()}*\n\n"
        f"*{_('تفاصيل طلبك')}:*\n"
        f"📦 *{_('المنتجات')}:* {order.orderitem_set.count()} {_('منتجات')}\n"
        f"💰 *{_('الإجمالي')}:* {order.final_total:.2f} {_('ريال')}\n"
        f"🗓️ *{_('تاريخ الطلب')}:* {order.date_ordered.strftime("%d %b, %Y %H:%M")}\n"
        f"شكراً لتسوقك معنا!\n"
        f"{settings.BASE_URL}" # Link to your store or order detail page
    )

    payload = {
        'token': settings.ULTRMSG_TOKEN,
        'to': order.phone_number,
        'body': message_body
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"Successfully sent order status update WhatsApp notification to {order.phone_number}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp status update to {order.phone_number}: {e}")
        # Consider logging this error properly in production

def send_new_product_whatsapp(phone_number, product):
    """
    Sends a WhatsApp notification to a user about a new product.
    """
    if not settings.ULTRMSG_INSTANCE_ID or not settings.ULTRMSG_TOKEN:
        print("WhatsApp API credentials are not set.")
        return

    # Construct the message
    # You can customize this message as you like
    message_body = (
        f"🎉 *منتج جديد ومميز وصل لمتجرنا!*\n\n"
        f"*{product.name}*\n"
        f"_{product.description[:100]}..._\n\n"
        f"*السعر:* {product.price} جنيه\n\n"
        f"الكمية محدودة! لا تفوت فرصة الحصول عليه الآن 👇\n"
        f"{settings.BASE_URL}{product.get_absolute_url()}" # Assumes BASE_URL is in settings
    )

    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    params = {
        "token": settings.ULTRMSG_TOKEN,
        "to": phone_number,
        "body": message_body,
        "priority": "10"
    }

    try:
        response = requests.post(url, data=params)
        response.raise_for_status()
        print(f"Successfully sent new product WhatsApp notification to {phone_number}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send new product WhatsApp notification to {phone_number}. Response: {response.text}")
        # Optionally, re-raise the exception if you want the caller to handle it
        # raise e 


def send_order_confirmation_whatsapp(order_instance, request):
    logger.debug(f"Inside send_order_confirmation_whatsapp for Order ID: {order_instance.id}")

    # Re-fetch the order from the database to ensure all fields, including UUID, are populated.
    try:
        order = Order.objects.get(id=order_instance.id)
    except Order.DoesNotExist:
        logger.error(f"Order with ID {order_instance.id} not found when attempting to send WhatsApp confirmation.")
        return

    logger.debug(f"Value of order.uuid: {order.uuid}")
    logger.debug(f"Type of order.uuid: {type(order.uuid)}")
    
    if not order.uuid:
        logger.error("ERROR: order.uuid is None or empty. Cannot build confirmation URL. Skipping WhatsApp message.")
        return # Exit early if UUID is missing

    """
    Sends a WhatsApp message to the customer with order details and a link for confirmation.
    """
    if not order.phone_number or not settings.ULTRMSG_INSTANCE_ID or not settings.ULTRMSG_TOKEN:
        logger.warning("Missing phone number or WhatsApp API credentials for order confirmation notification.")
        return

    # Build the confirmation URL
    confirmation_url = request.build_absolute_uri(
        reverse('store:confirm_order_whatsapp', args=[order.id, order.uuid])
    )

    items_list = ""
    for item in order.orderitem_set.all():
        items_list += f"- {item.quantity} x {item.product.name} @ {item.price} EGP\n"

    message_body = (
        f"🛒 *{_('تم استلام طلبك بنجاح!')}*\n\n"
        f"*{_('رقم الطلب')}:* #{order.id}\n"
        f"*{_('الاسم')}:* {order.customer.get_full_name() if order.customer else ''}\n"
        f"*{_('العنوان')}:* {order.shipping_address}\n"
        f"*{_('الإجمالي')}:* {order.final_total:.2f} {_('ريال')}\n\n"
        f"*{_('تفاصيل المنتجات')}:*\n"
        f"{items_list}\n"
        f"*{_('هل ترغب في تأكيد الطلب؟')}*\n\n"
        f"{_('للتأكيد أو تعديل العنوان أو الإلغاء، يرجى النقر على الرابط التالي:')}\n"
        f"{confirmation_url}"
    )

    url = f"https://api.ultramsg.com/{settings.ULTRMSG_INSTANCE_ID}/messages/chat"
    payload = {
        'token': settings.ULTRMSG_TOKEN,
        'to': order.phone_number,
        'body': message_body
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        logger.info(f"Successfully sent order confirmation WhatsApp notification to {order.phone_number}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending order confirmation WhatsApp to {order.phone_number}: {e}")
        # Consider logging this error properly in production 