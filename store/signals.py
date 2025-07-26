from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Product, PushSubscription, Customer, Inquiry, Notification, Order
from pywebpush import webpush, WebPushException
import json
from django.conf import settings
from .whatsapp_service import send_whatsapp_otp, send_new_product_whatsapp
from django.utils.translation import gettext_lazy as _
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.defaultfilters import timesince

def send_new_product_push_notification(product):
    print(f"Preparing to send push notification for new product: {product.name}")
    
    # Payload can be customized
    payload = {
        "notification": {
            "title": "منتج جديد وصل للتو!",
            "body": f"لا تفوت {product.name} بسعر {product.price} جنيه فقط.",
            "icon": product.image.url if product.image else "/static/images/default-notification-icon.png",
            "image": product.image.url if product.image else None,
            "click_action": product.get_absolute_url()
        }
    }
    
    subscriptions = PushSubscription.objects.all()
    print(f"Found {subscriptions.count()} subscribers.")

    for sub in subscriptions:
        try:
            vapid_data = {
                'sub': json.dumps({
                    'endpoint': sub.endpoint,
                    'keys': {
                        'p256dh': sub.p256dh,
                        'auth': sub.auth
                    }
                }),
                'vapid_claims': {
                    "sub": settings.WEBPUSH_SETTINGS['VAPID_ADMIN_EMAIL']
                },
                'vapid_private_key': settings.WEBPUSH_SETTINGS['VAPID_PRIVATE_KEY'],
                'ttl': 60 * 60 * 24 # 1 day
            }
            webpush(**vapid_data)
            print(f"Sent push to {sub.user.username}")
        except WebPushException as ex:
            print(f"Web push failed for {sub.user.username}: {ex}")
            # The exception contains status code and headers.
            # If the status code is 410 (Gone), we should delete the subscription.
            if ex.response and ex.response.status_code == 410:
                sub.delete()
        except Exception as e:
            print(f"An unexpected error occurred during webpush: {e}")


@receiver(post_save, sender=Product)
def product_created_handler(sender, instance, created, **kwargs):
    """
    Handles actions to be taken after a new product is created.
    """
    if created:
        print(f"New product created: {instance.name}. Triggering notifications.")
        # 1. Send Web Push Notifications
        send_new_product_push_notification(instance)

        # 2. Send WhatsApp Notifications
        customers_with_phones = Customer.objects.filter(phone_number__isnull=False).exclude(phone_number__exact='')
        print(f"Found {customers_with_phones.count()} customers with phone numbers for WhatsApp.")
        for customer in customers_with_phones:
            try:
                send_new_product_whatsapp(customer.phone_number, instance)
            except Exception as e:
                print(f"Failed to send WhatsApp to {customer.phone_number}. Error: {e}")
        
        print("Signal handler finished.")

@receiver(post_save, sender=Inquiry)
def create_reply_notification(sender, instance, created, **kwargs):
    """
    Creates a notification when an admin replies to an inquiry.
    """
    # Check if the instance has a reply, if the user is linked, and if it's not a new inquiry
    if instance.reply and instance.user and instance.is_replied:
        # Prevent creating notifications multiple times for the same reply.
        # We check if a notification for this inquiry already exists.
        # A more robust way might be to check if `reply` has changed.
        
        notification_title = _("رد على استفسارك: ") + f"\"{instance.subject}\""
        
        # Check if a notification with this exact title and user already exists.
        # This is a simple way to avoid duplicate notifications on multiple saves.
        if not Notification.objects.filter(user=instance.user, title=notification_title).exists():
            Notification.objects.create(
                user=instance.user,
                title=notification_title,
                message=instance.reply
            )

@receiver(post_save, sender=Notification)
def send_notification_on_save(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        group_name = f'user_notifications_{instance.user.id}'

        message = {
            'type': 'send_notification',
            'message': {
                'id': instance.id,
                'title': instance.title,
                'message': instance.message,
                'read': instance.read,
                'created_at': f'{timesince(instance.created_at)} منذ',
            }
        }

        async_to_sync(channel_layer.group_send)(
            group_name,
            message
        )

@receiver(post_save, sender=Order)
def order_created_handler(sender, instance, created, **kwargs):
    """
    Handles actions to be taken after a new order is created.
    """
    if created:
        print(f"New order created: {instance.id}. Triggering notifications.")
        # 1. Send Web Push Notifications
        # send_new_product_push_notification(instance.product)

        # 2. Send WhatsApp Notifications
        # customers_with_phones = Customer.objects.filter(phone_number__isnull=False).exclude(phone_number__exact='')
        # print(f"Found {customers_with_phones.count()} customers with phone numbers for WhatsApp.")
        # for customer in customers_with_phones:
        #     try:
        #         send_new_product_whatsapp(customer.phone_number, instance.product)
        #     except Exception as e:
        #         print(f"Failed to send WhatsApp to {customer.phone_number}. Error: {e}")
        
        print("Signal handler finished.") 