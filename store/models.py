from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
import random
from django.conf import settings
import uuid # New import for UUID

class Category(models.Model):
    name = models.CharField(max_length=200, db_index=True, verbose_name="الاسم")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="المعرف")

    class Meta:
        ordering = ('name',)
        verbose_name = 'فئة'
        verbose_name_plural = 'الفئات'

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, verbose_name="الفئة")
    name = models.CharField(max_length=200, db_index=True, verbose_name="الاسم")
    slug = models.SlugField(max_length=200, db_index=True, verbose_name="المعرف")
    image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True, verbose_name="الصورة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name=_("سعر التكلفة")) # New field
    stock = models.IntegerField(default=0, verbose_name="الكمية المتوفرة")
    available = models.BooleanField(default=True, verbose_name="متوفر")
    created = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    class Meta:
        ordering = ('name',)
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"

    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.id])

    def __str__(self):
        return self.name

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("المستخدم"))
    phone_number = models.CharField(_("رقم الهاتف"), max_length=20, blank=True, null=True, unique=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True, verbose_name=_("الصورة الشخصية"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username if self.user else "مستخدم غير معروف"

    def get_full_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return "N/A"
    get_full_name.short_description = _("الاسم الكامل")

    def get_email(self):
        if self.user:
            return self.user.email
        return "N/A"
    get_email.short_description = _("البريد الإلكتروني")

    class Meta:
        verbose_name = _("عميل")
        verbose_name_plural = _("العملاء")

class Address(models.Model):
    ADDRESS_TYPE_CHOICES = (
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses', verbose_name="العميل")
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='shipping', verbose_name="نوع العنوان")
    street_address = models.CharField(max_length=255, verbose_name="عنوان الشارع")
    city = models.CharField(max_length=100, verbose_name="المدينة")
    state = models.CharField(max_length=100, blank=True, null=True, verbose_name="المحافظة/الولاية")
    zip_code = models.CharField(max_length=20, verbose_name="الرمز البريدي")
    country = models.CharField(max_length=100, verbose_name="الدولة")
    is_default = models.BooleanField(default=False, verbose_name="العنوان الافتراضي")

    class Meta:
        verbose_name = "عنوان"
        verbose_name_plural = "العناوين"
        unique_together = ('customer', 'address_type', 'is_default')

    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.get_address_type_display()} Address"

class StoredPaymentMethod(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payment_methods', verbose_name="العميل")
    nickname = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("اسم مستعار للبطاقة")) # New field
    gateway_token = models.CharField(max_length=255, help_text="Token from the payment gateway (e.g., Kashier, Stripe)")
    card_brand = models.CharField(max_length=50, verbose_name="نوع البطاقة (e.g., Visa)")
    last_four_digits = models.CharField(max_length=4, verbose_name="آخر 4 أرقام")
    is_default = models.BooleanField(default=False, verbose_name="طريقة الدفع الافتراضية")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "طريقة دفع مخزنة"
        verbose_name_plural = "طرق الدفع المخزنة"

    def __str__(self):
        if self.nickname:
            return f"{self.nickname} ({self.card_brand} **** {self.last_four_digits})"
        return f"{self.card_brand} **** {self.last_four_digits}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', _('قيد الانتظار')),
        ('processing', _('قيد التجهيز')),
        ('shipped', _('تم الشحن')),
        ('delivered', _('تم التسليم')),
        ('cancelled', _('ملغي')),
        ('returned', _('مرتجع')),
        ('confirmed', _('تم التأكيد')), # New status
        ('address_pending', _('بانتظار تأكيد العنوان')), # New status
        ('cancelled_by_customer', _('ملغي من قبل العميل')), # New status
    ]

    PAYMENT_CHOICES = (
        ('kashier', 'Kashier'),
        ('cod', 'Cash on Delivery'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="العميل")
    date_ordered = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الطلب")
    complete = models.BooleanField(default=False, verbose_name="مكتمل") # To know if the order process is finished
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name=_("الحالة"))
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Shipping and contact details
    shipping_address = models.TextField(verbose_name="عنوان الشحن")
    phone_number = models.CharField(max_length=20, verbose_name="رقم الهاتف")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات")

    # Financials
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الكوبون")
    total_before_discount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ قبل الخصم")
    final_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ النهائي")
    
    # Statuses
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='kashier', verbose_name="طريقة الدفع")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="حالة الدفع")
    
    def get_status_display_for_stage(self, stage_value):
        """Returns the display value for a given status machine name."""
        return dict(self.STATUS_CHOICES).get(stage_value, '')

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ['-date_ordered']
    # Ensuring Django detects a change for new migration generation

class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="المنتج")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, verbose_name="الطلب")
    quantity = models.IntegerField(default=0, null=True, blank=True, verbose_name="الكمية")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="السعر عند الشراء")
    date_added = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")

    @property
    def get_total(self):
        # Use the stored price if it exists, otherwise use the product's current price
        total = (self.price or self.product.price) * self.quantity
        return total

    class Meta:
        verbose_name = "عنصر الطلب"
        verbose_name_plural = "عناصر الطلب"

class Cart(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, null=True, blank=True, verbose_name="العميل")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return f"سلة مشتريات {self.customer.get_full_name()}"

    @property
    def get_cart_total(self):
        cartitems = self.items.all()
        total = sum([item.get_total for item in cartitems])
        return total

    @property
    def get_cart_items(self):
        cartitems = self.items.all()
        total = sum([item.quantity for item in cartitems])
        return total

    class Meta:
        verbose_name = "سلة مشتريات"
        verbose_name_plural = "سلال المشتريات"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE, verbose_name="سلة المشتريات")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="المنتج")
    quantity = models.PositiveIntegerField(default=1, verbose_name="الكمية")

    def __str__(self):
        return f'{self.quantity} x {self.product.name}'
    
    @property
    def get_total(self):
        total = self.product.price * self.quantity
        return total

    class Meta:
        verbose_name = "عنصر السلة"
        verbose_name_plural = "عناصر السلة"

class Inquiry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("المستخدم"))
    name = models.CharField(_("الاسم"), max_length=100)
    email = models.EmailField(_("البريد الإلكتروني"))
    phone = models.CharField(_("رقم الهاتف"), max_length=20, blank=True)
    subject = models.CharField(_("الموضوع"), max_length=200)
    message = models.TextField(_("الرسالة"))
    is_replied = models.BooleanField(_("تم الرد"), default=False)
    reply = models.TextField(_("الرد"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{_('استفسار من')} {self.name} - {self.subject}"

    class Meta:
        verbose_name = "استفسار"
        verbose_name_plural = "الاستفسارات"
        ordering = ['-created_at']

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="رمز الكوبون")
    discount = models.PositiveIntegerField(help_text="نسبة مئوية للخصم (مثال: 10 تعني 10%)", verbose_name="قيمة الخصم (%)")
    valid_from = models.DateTimeField(verbose_name="صالح من تاريخ")
    valid_to = models.DateTimeField(verbose_name="صالح حتى تاريخ")
    active = models.BooleanField(default=True, verbose_name="فعال")

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "كوبون"
        verbose_name_plural = "كوبونات الخصم"

class SiteConfiguration(models.Model):
    site_name = models.CharField(_("اسم الموقع"), max_length=255, default="متجري")
    logo = models.ImageField(_("شعار الموقع"), upload_to='site/', blank=True, null=True)
    contact_email = models.EmailField(_("البريد الإلكتروني للتواصل"), max_length=255, blank=True)
    phone_number = models.CharField(_("رقم الهاتف الأساسي"), max_length=20, blank=True)
    address = models.TextField(_("العنوان"), blank=True)
    
    # Social Media Links
    facebook_url = models.URLField(_("رابط فيسبوك"), blank=True, null=True)
    instagram_url = models.URLField(_("رابط انستغرام"), blank=True, null=True)
    twitter_url = models.URLField(_("رابط تويتر (X)"), blank=True, null=True)
    whatsapp_number = models.CharField(_("رقم واتساب"), max_length=20, blank=True, null=True, help_text=_("استخدم الصيغة الدولية، مثال: +201234567890"))

    def __str__(self):
        return str(_("إعدادات الموقع"))

    def save(self, *args, **kwargs):
        if not self.pk and SiteConfiguration.objects.exists():
            raise ValidationError(_('يمكن وجود إعداد واحد للموقع فقط.'))
        return super(SiteConfiguration, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("إعدادات الموقع")
        verbose_name_plural = _("إعدادات الموقع")

class Promotion(models.Model):
    title = models.CharField(max_length=200, verbose_name="العنوان")
    image = models.ImageField(upload_to='promotions/', verbose_name="الصورة")
    link = models.URLField(max_length=200, blank=True, null=True, verbose_name="الرابط (اختياري)")
    active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "عرض ترويجي"
        verbose_name_plural = "العروض الترويجية"
        ordering = ['-created_at']

class FAQ(models.Model):
    question = models.CharField(max_length=255, verbose_name="السؤال")
    answer = models.TextField(verbose_name="الإجابة")
    display_order = models.PositiveIntegerField(default=0, help_text="يستخدم لترتيب عرض الأسئلة، الأقل يظهر أولاً.", verbose_name="ترتيب العرض")
    active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "سؤال شائع"
        verbose_name_plural = "الأسئلة الشائعة"
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.question

class BlogCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم التصنيف")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="المعرف")

    class Meta:
        verbose_name = "تصنيف مدونة"
        verbose_name_plural = "تصنيفات المدونة"
        ordering = ['name']

    def __str__(self):
        return self.name

class BlogPost(models.Model):
    title = models.CharField(max_length=200, verbose_name="العنوان")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="المعرف")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_posts', verbose_name="المؤلف")
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts', verbose_name="التصنيف")
    image = models.ImageField(upload_to='blog/%Y/%m/%d', blank=True, null=True, verbose_name="الصورة")
    content = models.TextField(verbose_name="المحتوى")
    views = models.PositiveIntegerField(default=0, verbose_name="عدد المشاهدات")
    published_date = models.DateTimeField(default=timezone.now, verbose_name="تاريخ النشر")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "مقالة مدونة"
        verbose_name_plural = "مقالات المدونة"
        ordering = ['-published_date']

    def __str__(self):
        return self.title

class Wishlist(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, verbose_name="العميل")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"قائمة مفضلات {self.customer.get_full_name()}"

    class Meta:
        verbose_name = "قائمة مفضلات"
        verbose_name_plural = "قوائم المفضلات"

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, related_name='items', on_delete=models.CASCADE, verbose_name="قائمة المفضلات")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="المنتج")
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "عنصر مفضلة"
        verbose_name_plural = "عناصر المفضلات"
        unique_together = ('wishlist', 'product') # Ensure a product is not added twice to the same wishlist

    def __str__(self):
        return f"{self.product.name} في مفضلة {self.wishlist.customer.get_full_name()}"


class PhoneOTP(models.Model):
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], max_length=17, unique=True, verbose_name=_("رقم الهاتف"))
    otp = models.CharField(max_length=6, blank=True, null=True, verbose_name=_("رمز التحقق"))
    is_verified = models.BooleanField(default=False, verbose_name="تم التحقق")
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("تاريخ الإنشاء"))

    def __str__(self):
        return f'OTP for {self.phone_number}'

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))

    class Meta:
        verbose_name = _("رمز تحقق عبر الهاتف")
        verbose_name_plural = _("رموز التحقق عبر الهاتف")

class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Push Subscription for {self.user.username}"

    class Meta:
        verbose_name = _("اشتراك إشعار الدفع")
        verbose_name_plural = _("اشتراكات إشعارات الدفع")

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("المستخدم"))
    title = models.CharField(_("العنوان"), max_length=200)
    message = models.TextField(_("الرسالة"))
    read = models.BooleanField(_("مقروء"), default=False)
    image_url = models.URLField(_("رابط الصورة"), blank=True, null=True, help_text=_("اختياري: رابط لصورة كبيرة تظهر في الإشعار."))
    target_url = models.URLField(_("الرابط الهدف"), blank=True, null=True, help_text=_("اختياري: الرابط الذي يتم فتحه عند النقر على الإشعار."))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("إشعار")
        verbose_name_plural = _("الإشعارات")
        ordering = ['-created_at']

class AboutPage(models.Model):
    title = models.CharField(_("العنوان الرئيسي"), max_length=200)
    content = models.TextField(_("المحتوى"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.pk and AboutPage.objects.exists():
            raise ValidationError(_('يمكن وجود صفحة "من نحن" واحدة فقط.'))
        return super(AboutPage, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("صفحة من نحن")
        verbose_name_plural = _("صفحة من نحن")

class TeamMember(models.Model):
    about_page = models.ForeignKey(AboutPage, related_name='team_members', on_delete=models.CASCADE, verbose_name=_("صفحة من نحن"))
    name = models.CharField(_("الاسم"), max_length=100)
    role = models.CharField(_("المنصب"), max_length=100)
    image = models.ImageField(_("الصورة"), upload_to='team/')
    display_order = models.PositiveIntegerField(default=0, verbose_name=_("ترتيب العرض"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("عضو الفريق")
        verbose_name_plural = _("أعضاء الفريق")
        ordering = ['display_order']


class Expense(models.Model):
    description = models.CharField(_("الوصف"), max_length=255)
    amount = models.DecimalField(_("المبلغ"), max_digits=10, decimal_places=2)
    date = models.DateField(_("التاريخ"), default=timezone.now)
    category = models.CharField(_("الفئة"), max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"

    class Meta:
        verbose_name = _("مصروف")
        verbose_name_plural = _("المصروفات")
        ordering = ['-description'] # Order by description to avoid potential issues with `date` as default field


class Invoice(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', _('كاش')),
        ('visa', _('فيزا')),
        ('bank_transfer', _('تحويل بنكي')),
        ('cod', _('عند الاستلام')),
    ]

    customer_name = models.CharField(_("الاسم الكامل"), max_length=255)
    customer_phone = models.CharField(_("رقم الهاتف"), max_length=20, blank=True, null=True)
    customer_email = models.EmailField(_("البريد الإلكتروني"), blank=True, null=True)
    customer_address = models.TextField(_("العنوان (مدينة – شارع – رقم منزل)"), blank=True, null=True)

    date_issued = models.DateTimeField(_("تاريخ الفاتورة"), auto_now_add=True)
    
    payment_method = models.CharField(_("طريقة الدفع"), max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cash')
    is_paid = models.BooleanField(_("هل تم الدفع؟"), default=False)
    internal_notes = models.TextField(_("ملاحظات داخلية"), blank=True, null=True)

    total_amount = models.DecimalField(_("إجمالي المبلغ (قبل الضريبة والخصم)"), max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(_("نسبة الضريبة المضافة (%)"), max_digits=5, decimal_places=2, default=0.00, help_text=_("مثال: 14 لـ 14%"))
    discount_amount = models.DecimalField(_("الخصم اليدوي"), max_digits=10, decimal_places=2, default=0.00)
    final_total = models.DecimalField(_("الإجمالي النهائي"), max_digits=10, decimal_places=2, default=0.00)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_("معرف الفاتورة الفريد")) # New field for shareable link

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{_('فاتورة رقم')} {self.pk} - {self.customer_name}"

    class Meta:
        verbose_name = _("فاتورة")
        verbose_name_plural = _("الفواتير")
        ordering = ['-date_issued']

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE, verbose_name=_("الفاتورة"))
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("المنتج")) # New ForeignKey to Product
    product_name = models.CharField(_("اسم المنتج/الخدمة (إذا لم يتم اختيار منتج)"), max_length=255, blank=True, null=True) # Now optional
    quantity = models.PositiveIntegerField(_("الكمية"), default=1)
    unit_price = models.DecimalField(_("سعر الوحدة"), max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(_("الإجمالي الفرعي"), max_digits=10, decimal_places=2, editable=False, default=0.00)

    def save(self, *args, **kwargs):
        if self.product and not self.unit_price:
            self.unit_price = self.product.price # Automatically set unit_price from product
        elif not self.product and not self.product_name:
            raise ValidationError(_("يجب تحديد منتج أو اسم منتج/خدمة."))

        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        if self.product:
            return f'{self.quantity} x {self.product.name} ({self.invoice.customer_name})'
        return f'{self.quantity} x {self.product_name or "خدمة يدوية"} ({self.invoice.customer_name})'

    class Meta:
        verbose_name = _("عنصر فاتورة")
        verbose_name_plural = _("عناصر الفاتورة")
