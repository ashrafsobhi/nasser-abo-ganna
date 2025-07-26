from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Inquiry, Customer, Address, StoredPaymentMethod, Invoice, InvoiceItem # Added Invoice and InvoiceItem
from django.utils.translation import gettext_lazy as _
import phonenumbers
from django.contrib.auth.password_validation import validate_password
from django.forms import inlineformset_factory # Added inlineformset_factory
from decimal import Decimal # Added Decimal for calculations in forms


class PhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        max_length=20,
        label=_("رقم الهاتف"),
        widget=forms.TextInput(attrs={'placeholder': _('e.g., 01012345678')})
    )

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            raise forms.ValidationError(_("رقم الهاتف مطلوب."))
        try:
            # Assuming Egyptian numbers if no country code is provided
            parsed_number = phonenumbers.parse(phone_number, "EG")
            if not phonenumbers.is_valid_number(parsed_number):
                raise forms.ValidationError(_("الرجاء إدخال رقم هاتف صحيح."))
            # Format to E.164 standard (+20...)
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            raise forms.ValidationError(_("لا يمكن تحليل رقم الهاتف. الرجاء التأكد من أنه بالتنسيق الصحيح."))


class OTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        label=_("رمز التحقق"),
        widget=forms.TextInput(attrs={'placeholder': _('_ _ _ _ _ _'), 'autocomplete': 'one-time-code'})
    )


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required. Inform a valid email address.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].label = "اسم المستخدم"
        if 'email' in self.fields:
            self.fields['email'].label = "البريد الإلكتروني"
        if 'password' in self.fields:
            self.fields['password'].label = "كلمة المرور"
        if 'password2' in self.fields:
            self.fields['password2'].label = "تأكيد كلمة المرور"
        
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
            field.help_text = ''

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['phone_number']

class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['profile_picture']
        labels = {
            'profile_picture': _('تغيير الصورة الشخصية'),
        }

class ChangePhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        label=_("رقم الهاتف الجديد"),
        widget=forms.TextInput(attrs={'class': 'form-control form-control-rounded', 'placeholder': _('+201xxxxxxxxx')})
    )

    def clean_phone_number(self):
        phone_number_str = self.cleaned_data.get('phone_number')
        if not phone_number_str:
            raise forms.ValidationError(_("هذا الحقل مطلوب."))
        try:
            parsed_phone = phonenumbers.parse(phone_number_str, None)
            if not phonenumbers.is_valid_number(parsed_phone):
                raise forms.ValidationError(_("رقم الهاتف غير صالح."))
            
            formatted_phone = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)

            if Customer.objects.filter(phone_number=formatted_phone).exists():
                raise forms.ValidationError(_("هذا الرقم مسجل بالفعل في حساب آخر."))

            return formatted_phone
        except phonenumbers.phonenumberutil.NumberParseException:
            raise forms.ValidationError(_("الرجاء إدخال رقم هاتف صالح بالصيغة الدولية (مثال: +966xxxxxxxx)."))


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['street_address', 'city', 'state', 'zip_code', 'country', 'is_default']
        labels = {
            'street_address': 'عنوان الشارع',
            'city': 'المدينة',
            'state': 'المحافظة/الولاية',
            'zip_code': 'الرمز البريدي',
            'country': 'الدولة',
            'is_default': 'اجعله العنوان الافتراضي',
        }
        widgets = {
            'street_address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('اسمك الكامل')}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('بريدك الإلكتروني')}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('موضوع الرسالة')}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': _('اكتب رسالتك هنا...')}),
        }
        labels = {
            'name': _('الاسم'),
            'email': _('البريد الإلكتروني'),
            'subject': _('الموضوع'),
            'message': _('الرسالة'),
        }

class UserDetailForm(forms.Form):
    username = forms.CharField(
        label=_("اسم المستخدم"),
        max_length=150,
        help_text=_("مطلوب. 150 حرفًا أو أقل. أحرف وأرقام و @/./+/-/_ فقط."),
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label=_("كلمة المرور"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        validators=[validate_password]
    )
    password_confirm = forms.CharField(
        label=_("تأكيد كلمة المرور"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("هذا المستخدم موجود بالفعل."))
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError(_("كلمتا المرور غير متطابقتين."))

        return cleaned_data 

# New: Form for basic User profile fields (e.g., first_name, last_name, email)
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email'] # Customize as needed
        labels = {
            'first_name': _('الاسم الأول'),
            'last_name': _('الاسم الأخير'),
            'email': _('البريد الإلكتروني'),
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class UnifiedLoginForm(forms.Form):
    login_identifier = forms.CharField(
        label=_("اسم المستخدم أو البريد الإلكتروني أو رقم الهاتف"),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': _("ادخل...")
        })
    )
    password = forms.CharField(
        label=_("كلمة المرور"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '********'
        })
    )


class AddPaymentMethodForm(forms.ModelForm):
    class Meta:
        model = StoredPaymentMethod
        fields = ['nickname', 'card_brand', 'last_four_digits', 'gateway_token']
        labels = {
            'nickname': _('اسم مستعار (مثال: بطاقة العمل)'), # New label
            'card_brand': _('نوع البطاقة (مثل Visa, Mastercard)'),
            'last_four_digits': _('آخر 4 أرقام'),
            'gateway_token': _('رمز البوابة (للتجربة فقط، لا تدخل بيانات حقيقية)'),
        }
        widgets = {
            'nickname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('مثال: بطاقة المنزل')}), # New widget
            'card_brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('مثال: Visa')}),
            'last_four_digits': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('مثال: 1234'), 'maxlength': '4'}),
            'gateway_token': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('رمز وهمي للتجربة')}),
        }
    
    def clean_last_four_digits(self):
        last_four = self.cleaned_data['last_four_digits']
        if not last_four.isdigit() or len(last_four) != 4:
            raise forms.ValidationError(_("آخر 4 أرقام يجب أن تكون 4 أرقام فقط."))
        return last_four 


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'customer_name', 'customer_phone', 'customer_email', 'customer_address',
            'payment_method', 'is_paid', 'internal_notes',
            'tax_rate', 'discount_amount'
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('اسم العميل الكامل')}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('رقم هاتف العميل')}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('البريد الإلكتروني (اختياري)')}),
            'customer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('مدينة – شارع – رقم منزل')}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'is_paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('ملاحظات داخلية حول الفاتورة (اختياري)')}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': _('مثال: 14')}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': _('مبلغ الخصم')}),
        }

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'product_name', 'quantity', 'unit_price'] # Added 'product', kept 'product_name'
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control form-control-sm item-product-select'}), # New widget for product select
            'product_name': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': _('اسم المنتج/الخدمة (اختياري)')}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-quantity', 'min': '1', 'step': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-unit-price', 'min': '0.01', 'step': '0.01'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        product_name = cleaned_data.get('product_name')

        if not product and not product_name:
            raise forms.ValidationError(_("يجب اختيار منتج أو إدخال اسم منتج/خدمة."))
        elif product and product_name:
            # If both are provided, prefer the product from the database
            cleaned_data['product_name'] = product.name

        return cleaned_data

InvoiceItemFormSet = inlineformset_factory(
    Invoice, 
    InvoiceItem, 
    form=InvoiceItemForm, 
    extra=1, 
    can_delete=True, 
    can_delete_extra=True
) 