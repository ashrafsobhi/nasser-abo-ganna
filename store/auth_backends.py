from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Customer
import phonenumbers

UserModel = get_user_model()

class UnifiedAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login_identifier = username  # The identifier from the form

        # Try to find user by phone number
        try:
            # Attempt to parse as a phone number
            parsed_phone = phonenumbers.parse(login_identifier, None)
            if phonenumbers.is_valid_number(parsed_phone):
                formatted_phone = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
                # Find customer by formatted phone number
                customer = Customer.objects.filter(phone_number=formatted_phone).first()
                if customer and customer.user and customer.user.check_password(password):
                    return customer.user
        except Exception:
            # Not a phone number, proceed to next checks
            pass

        # Try to find user by username or email
        try:
            # Case-insensitive search for username or email
            user = UserModel.objects.get(Q(username__iexact=login_identifier) | Q(email__iexact=login_identifier))
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            # User not found by any identifier
            return None
        
        return None

    def get_user(self, user_id):
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None 