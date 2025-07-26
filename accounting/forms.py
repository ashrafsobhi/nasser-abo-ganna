from django import forms
from .models import Invoice, InvoiceItem
from store.models import Product # Assuming products will be linked

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['order', 'customer', 'customer_name', 'customer_phone', 'customer_email', 'customer_address', 
                  'invoice_number', 'due_date', 'total_amount', 'tax_rate', 'discount_amount', 'final_total',
                  'payment_method', 'is_paid', 'internal_notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'readonly': 'readonly'}), # Make total_amount readonly if it's calculated by JS
            'final_total': forms.NumberInput(attrs={'readonly': 'readonly'}), # Make final_total readonly if it's calculated by JS
        }

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'description', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add a placeholder for description if product is not selected
        if not self.instance.product and not self.instance.description:
            self.fields['description'].widget.attrs['placeholder'] = "ادخل وصف المنتج إذا لم يكن منتجاً محدداً" 