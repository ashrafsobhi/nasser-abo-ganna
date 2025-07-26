from django.db import models
from django.conf import settings
from store.models import Order, Product, Customer
import uuid
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

# Create your models here.

class Invoice(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', _('كاش')),
        ('visa', _('فيزا')),
        ('bank_transfer', _('تحويل بنكي')),
        ('cod', _('عند الاستلام')),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='invoice', null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    
    # New fields for customer details, independent of the customer foreign key
    customer_name = models.CharField(_("الاسم الكامل"), max_length=255)
    customer_phone = models.CharField(_("رقم الهاتف"), max_length=20, blank=True, null=True)
    customer_email = models.EmailField(_("البريد الإلكتروني"), blank=True, null=True)
    customer_address = models.TextField(_("العنوان (مدينة – شارع – رقم منزل)"), blank=True, null=True)

    invoice_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    invoice_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Financials (total_amount is now pre-tax/discount)
    total_amount = models.DecimalField(_("إجمالي المبلغ (قبل الضريبة والخصم)"), max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(_("نسبة الضريبة المضافة (%)"), max_digits=5, decimal_places=2, default=0.00, help_text=_("مثال: 14 لـ 14%"))
    discount_amount = models.DecimalField(_("الخصم اليدوي"), max_digits=10, decimal_places=2, default=0.00)
    final_total = models.DecimalField(_("الإجمالي النهائي"), max_digits=10, decimal_places=2, default=0.00)

    payment_method = models.CharField(_("طريقة الدفع"), max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cash')
    is_paid = models.BooleanField(_("هل تم الدفع؟"), default=False)
    internal_notes = models.TextField(_("ملاحظات داخلية"), blank=True, null=True)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_("معرف الفاتورة الفريد"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("فاتورة")
        verbose_name_plural = _("الفواتير")
        ordering = ['invoice_date']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate a simple invoice number based on timestamp or sequence
            # For a more robust solution, consider a custom manager or function
            self.invoice_number = f"INV-{self.pk or 'TEMP'}-{self.invoice_date.strftime('%Y%m%d%H%M%S')}"
        
        # Ensure final_total is calculated based on current data if not set manually
        if not self.pk or self.total_amount != self._original_total_amount or \
           self.tax_rate != self._original_tax_rate or self.discount_amount != self._original_discount_amount:
            tax_amount = (self.total_amount * self.tax_rate) / Decimal('100.00')
            self.final_total = self.total_amount + tax_amount - self.discount_amount

        super().save(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original values for comparison in save method
        self._original_total_amount = self.total_amount
        self._original_tax_rate = self.tax_rate
        self._original_discount_amount = self.discount_amount

    def __str__(self):
        return f"{_('فاتورة رقم')} {self.invoice_number or self.pk} - {self.customer_name}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items', verbose_name=_("الفاتورة"))
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounting_invoice_items', verbose_name=_("المنتج"))
    description = models.CharField(_("الوصف"), max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField(_("الكمية"), default=1)
    unit_price = models.DecimalField(_("سعر الوحدة"), max_digits=10, decimal_places=2)
    line_total = models.DecimalField(_("الإجمالي الفرعي"), max_digits=10, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.description or (self.product.name if self.product else '')} on Invoice {self.invoice.invoice_number}"
