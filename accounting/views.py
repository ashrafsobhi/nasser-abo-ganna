from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from store.models import Order, OrderItem, Customer, Expense, Invoice, InvoiceItem # Added Invoice, InvoiceItem
from django.utils.translation import gettext_lazy as _
from django.forms import ModelForm
from django import forms # Added for custom ChoiceField widget
from django.db.models import Sum, Count, F # New import for aggregation and F
from django.utils import timezone # New import for date calculations
from decimal import Decimal # New import for precise calculations
from django.db.models import Q # New import for Q object
from datetime import timedelta # New import for timedelta
from store.whatsapp_service import send_order_status_update_notification # Import WhatsApp notification function
from django.db.models.functions import TruncDate # New import for grouping by date
import json # New import for serializing data
from store.forms import InvoiceForm, InvoiceItemFormSet # New imports for Invoice forms
from django.urls import reverse # New import for generating URLs
from django.conf import settings # New import for accessing settings like BASE_URL
import qrcode # New import for QR code generation
import io # New import for in-memory file operations
import base64 # New import for base64 encoding
from django.forms import inlineformset_factory
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from store.models import Order, Customer, Product, OrderItem
from .models import Invoice, InvoiceItem
from .forms import InvoiceForm, InvoiceItemForm

# Form for updating order status
class OrderStatusForm(ModelForm):
    status = forms.ChoiceField(
        choices=Order.STATUS_CHOICES,
        label=_("حالة الطلب"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class Meta:
        model = Order
        fields = ['status']


@staff_member_required
def dashboard_view(request):
    # Get current date for daily/monthly/annual filters
    today = timezone.localdate()
    this_month_start = today.replace(day=1)
    this_year_start = today.replace(month=1, day=1)

    # Base queryset for completed orders
    completed_orders = Order.objects.filter(complete=True)

    # Total Orders
    total_orders = Order.objects.count()
    new_orders_today = Order.objects.filter(date_ordered__date=today).count()

    # Revenue
    total_revenue = completed_orders.aggregate(Sum('final_total'))['final_total__sum'] or Decimal('0.00')
    daily_revenue = completed_orders.filter(date_ordered__date=today).aggregate(Sum('final_total'))['final_total__sum'] or Decimal('0.00')
    monthly_revenue = completed_orders.filter(date_ordered__date__gte=this_month_start).aggregate(Sum('final_total'))['final_total__sum'] or Decimal('0.00')
    annual_revenue = completed_orders.filter(date_ordered__date__gte=this_year_start).aggregate(Sum('final_total'))['final_total__sum'] or Decimal('0.00')

    # Cost of Goods Sold (COGS)
    total_cogs = OrderItem.objects.filter(
        order__in=completed_orders # Filter by completed orders
    ).aggregate(
        total_c=Sum(F('product__cost_price') * F('quantity'))
    )['total_c'] or Decimal('0.00')

    daily_cogs = OrderItem.objects.filter(
        order__in=completed_orders.filter(date_ordered__date=today)
    ).aggregate(
        total_c=Sum(F('product__cost_price') * F('quantity'))
    )['total_c'] or Decimal('0.00')

    monthly_cogs = OrderItem.objects.filter(
        order__in=completed_orders.filter(date_ordered__date__gte=this_month_start)
    ).aggregate(
        total_c=Sum(F('product__cost_price') * F('quantity'))
    )['total_c'] or Decimal('0.00')

    annual_cogs = OrderItem.objects.filter(
        order__in=completed_orders.filter(date_ordered__date__gte=this_year_start)
    ).aggregate(
        total_c=Sum(F('product__cost_price') * F('quantity'))
    )['total_c'] or Decimal('0.00')

    # Expenses
    total_expenses = Expense.objects.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    daily_expenses = Expense.objects.filter(date=today).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    monthly_expenses = Expense.objects.filter(date__gte=this_month_start).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    annual_expenses = Expense.objects.filter(date__gte=this_year_start).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Net Profit (Revenue - COGS - Expenses)
    total_net_profit = total_revenue - total_cogs - total_expenses
    daily_net_profit = daily_revenue - daily_cogs - daily_expenses
    monthly_net_profit = monthly_revenue - monthly_cogs - monthly_expenses
    annual_net_profit = annual_revenue - annual_cogs - annual_expenses

    # Orders by Status
    orders_by_status = Order.objects.values('status').annotate(count=Count('status'))
    status_counts = {item['status']: item['count'] for item in orders_by_status}

    # Sales by Payment Method
    sales_by_payment_method = completed_orders.values('payment_method').annotate(total_sales=Sum('final_total'))
    payment_method_sales = {item['payment_method']: item['total_sales'] for item in sales_by_payment_method}

    context = {
        'title': _('لوحة تحكم المحاسبة'),
        'total_orders': total_orders,
        'new_orders_today': new_orders_today,
        'total_revenue': total_revenue,
        'daily_revenue': daily_revenue,
        'monthly_revenue': monthly_revenue,
        'annual_revenue': annual_revenue,
        'total_net_profit': total_net_profit,
        'daily_net_profit': daily_net_profit,
        'monthly_net_profit': monthly_net_profit,
        'annual_net_profit': annual_net_profit,
        'total_expenses': total_expenses,
        'daily_expenses': daily_expenses,
        'monthly_expenses': monthly_expenses,
        'annual_expenses': annual_expenses,
        'status_counts': status_counts,
        'sales_by_payment_method': payment_method_sales,
        'order_status_choices': dict(Order.STATUS_CHOICES),
        'payment_method_choices': dict(Order.PAYMENT_CHOICES),
    }
    return render(request, 'accounting/dashboard.html', context)

@staff_member_required
def reports_view(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Convert dates to datetime objects if provided
    if start_date:
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

    # Filter orders and expenses based on date range
    orders_query = Order.objects.filter(complete=True)
    expenses_query = Expense.objects.all()

    if start_date:
        orders_query = orders_query.filter(date_ordered__date__gte=start_date)
        expenses_query = expenses_query.filter(date__gte=start_date)
    if end_date:
        orders_query = orders_query.filter(date_ordered__date__lte=end_date)
        expenses_query = expenses_query.filter(date__lte=end_date)

    # Calculate Revenue for the period
    period_revenue = orders_query.aggregate(Sum('final_total'))['final_total__sum'] or Decimal('0.00')

    # Calculate COGS for the period
    period_cogs = OrderItem.objects.filter(
        order__in=orders_query
    ).aggregate(
        total_c=Sum(F('product__cost_price') * F('quantity'))
    )['total_c'] or Decimal('0.00')

    # Calculate Expenses for the period
    period_expenses = expenses_query.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Calculate Net Profit for the period
    period_net_profit = period_revenue - period_cogs - period_expenses

    # Top Selling Products (for the period)
    top_selling_products = OrderItem.objects.filter(order__in=orders_query)\
        .values('product__name')\
        .annotate(total_quantity_sold=Sum('quantity'), total_sales_value=Sum(F('quantity') * F('price')))\
        .order_by('-total_quantity_sold')[:10]

    # Expenses by Category (for the period)
    expenses_by_category = expenses_query.values('category')\
        .annotate(total_amount=Sum('amount'))\
        .order_by('-total_amount')

    # --- Data for Charts --- 

    # Revenue over time
    revenue_over_time = orders_query.annotate(
        truncated_date=TruncDate('date_ordered') # Renamed annotation
    ).values('truncated_date').annotate(
        amount=Sum('final_total')
    ).order_by('truncated_date')

    # Expenses over time
    expenses_over_time = expenses_query.annotate(
        truncated_date=TruncDate('date') # Renamed annotation
    ).values('truncated_date').annotate(
        amount=Sum('amount')
    ).order_by('truncated_date')

    # Combine revenue and expenses data by date to calculate profit over time
    all_dates = sorted(list(set([item['truncated_date'] for item in revenue_over_time] + [item['truncated_date'] for item in expenses_over_time])))
    
    # Create dictionaries for quick lookup
    revenue_dict = {item['truncated_date']: item['amount'] for item in revenue_over_time}
    expenses_dict = {item['truncated_date']: item['amount'] for item in expenses_over_time}

    profit_over_time = []
    for date in all_dates:
        rev = revenue_dict.get(date, Decimal('0.00'))
        exp = expenses_dict.get(date, Decimal('0.00'))
        profit_over_time.append({
            'date': date.isoformat(), # Still use 'date' for JS consumption
            'amount': rev - exp
        })

    # Prepare data for expenses by category chart (already done above, just format for JS)
    expenses_by_category_chart_data = [{
        'category': item['category'] or _('غير مصنف'),
        'amount': item['total_amount']
    } for item in expenses_by_category]

    context = {
        'title': _('التقارير المالية'),
        'start_date': start_date.isoformat() if start_date else '',
        'end_date': end_date.isoformat() if end_date else '',
        'period_revenue': period_revenue,
        'period_cogs': period_cogs,
        'period_expenses': period_expenses,
        'period_net_profit': period_net_profit,
        'top_selling_products': top_selling_products,
        'expenses_by_category': expenses_by_category, # Still useful for the list
        
        # Data for Charts (JSON serialized)
        'revenue_data': json.dumps(list(revenue_over_time), default=str), # default=str handles Decimal and date
        'expenses_data': json.dumps(list(expenses_over_time), default=str),
        'profit_data': json.dumps(profit_over_time, default=str),
        'expenses_by_category_chart_data': json.dumps(expenses_by_category_chart_data, default=str),
    }
    return render(request, 'accounting/reports.html', context)

@staff_member_required
def create_invoice_view(request):
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST)
        invoice_item_formset = InvoiceItemFormSet(request.POST, prefix='items')

        if invoice_form.is_valid() and invoice_item_formset.is_valid():
            invoice = invoice_form.save(commit=False)
            
            # Calculate total_amount from items (before tax and discount)
            items_total = Decimal('0.00')
            for form in invoice_item_formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    quantity = form.cleaned_data.get('quantity')
                    unit_price = form.cleaned_data.get('unit_price')
                    if quantity and unit_price:
                        items_total += quantity * unit_price
            
            invoice.total_amount = items_total

            # Calculate tax and final total
            tax_rate = invoice_form.cleaned_data.get('tax_rate', Decimal('0.00'))
            discount_amount = invoice_form.cleaned_data.get('discount_amount', Decimal('0.00'))

            tax_amount = (invoice.total_amount * tax_rate) / Decimal('100.00')
            invoice.final_total = invoice.total_amount + tax_amount - discount_amount
            
            invoice.save()
            invoice_item_formset.instance = invoice
            invoice_item_formset.save()

            messages.success(request, _('تم إنشاء الفاتورة بنجاح!'))
            return redirect('accounting:create_invoice') # Or to an invoice detail page

        else:
            messages.error(request, _('حدث خطأ أثناء إنشاء الفاتورة. يرجى مراجعة الأخطاء.'))
    else:
        invoice_form = InvoiceForm()
        invoice_item_formset = InvoiceItemFormSet(prefix='items')

    context = {
        'title': _('إنشاء فاتورة جديدة'),
        'invoice_form': invoice_form,
        'invoice_item_formset': invoice_item_formset,
    }
    return render(request, 'accounting/create_invoice.html', context)

@staff_member_required
def invoice_detail_view(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid) # Use uuid for lookup
    invoice_items = invoice.items.all()
    context = {
        'title': _('تفاصيل الفاتورة'),
        'invoice': invoice,
        'invoice_items': invoice_items,
    }
    return render(request, 'accounting/invoice_detail.html', context)

@staff_member_required
def invoice_thermal_print_view(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid) # Use uuid for lookup
    invoice_items = invoice.items.all()

    # Generate public URL for the invoice
    public_invoice_url = request.build_absolute_uri(reverse('store:customer_invoice_public', args=[invoice.uuid]))

    # Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4, # Adjust box_size for thermal printer (smaller is usually better)
        border=2,  # Adjust border for thermal printer (smaller is usually better)
    )
    qr.add_data(public_invoice_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to a BytesIO object
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    context = {
        'invoice': invoice,
        'invoice_items': invoice_items,
        'site_name': _("متجر الهدايا"), # Replace with actual site config if available
        'date': timezone.now().strftime("%Y-%m-%d %H:%M"),
        'qr_code_base64': qr_code_base64, # Pass the base64 encoded QR code to template
    }
    return render(request, 'accounting/invoice_thermal_print.html', context)

@staff_member_required
def invoice_list_view(request):
    invoices = Invoice.objects.all().order_by('-invoice_date')
    context = {
        'title': _('إدارة الفواتير'),
        'invoices': invoices,
    }
    return render(request, 'accounting/invoice_list.html', context)

@staff_member_required
def order_list_view(request):
    orders = Order.objects.all().order_by('-date_ordered')

    # Filtering Logic
    status_filter = request.GET.get('status')
    date_filter = request.GET.get('date_range')
    search_query = request.GET.get('q')

    if status_filter and status_filter != 'all':
        orders = orders.filter(status=status_filter)

    if date_filter:
        today = timezone.localdate()
        if date_filter == 'today':
            orders = orders.filter(date_ordered__date=today)
        elif date_filter == 'this_week':
            start_of_week = today - timedelta(days=today.weekday())
            orders = orders.filter(date_ordered__date__gte=start_of_week)
        elif date_filter == 'this_month':
            start_of_month = today.replace(day=1)
            orders = orders.filter(date_ordered__date__gte=start_of_month)
        elif date_filter == 'this_year':
            start_of_year = today.replace(month=1, day=1)
            orders = orders.filter(date_ordered__date__gte=start_of_year)

    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(customer__user__username__icontains=search_query) |
            Q(customer__phone_number__icontains=search_query) |
            Q(shipping_address__icontains=search_query)
        )

    context = {
        'orders': orders,
        'title': _('نظام المحاسبة - إدارة الطلبات'),
        'status_choices': Order.STATUS_CHOICES,
        'current_status_filter': status_filter,
        'current_date_filter': date_filter,
        'search_query': search_query,
        'date_range_choices': {
            'all': _('جميع الأوقات'),
            'today': _('اليوم'),
            'this_week': _('هذا الأسبوع'),
            'this_month': _('هذا الشهر'),
            'this_year': _('هذه السنة'),
        }
    }
    return render(request, 'accounting/order_list.html', context)

@staff_member_required
def edit_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Store the old status before updating
    old_status = order.status

    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, _('تم تحديث حالة الطلب بنجاح!'))
            
            # Send WhatsApp notification if status has changed
            if old_status != order.status:
                send_order_status_update_notification(order)

            return redirect('accounting:order_list')
        else:
            messages.error(request, _('حدث خطأ أثناء تحديث حالة الطلب. يرجى مراجعة البيانات.'))
    else:
        form = OrderStatusForm(instance=order)
    
    context = {
        'order': order,
        'form': form,
        'title': _('تعديل حالة الطلب')
    }
    return render(request, 'accounting/edit_order_status.html', context)

@login_required
def create_invoice_from_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Check if an invoice already exists for this order
    if hasattr(order, 'invoice'):
        messages.info(request, "يوجد بالفعل فاتورة لهذا الطلب. يمكنك تعديلها.")
        return redirect('accounting:edit_invoice', invoice_id=order.invoice.id)

    InvoiceItemFormSet = inlineformset_factory(Invoice, InvoiceItem, form=InvoiceItemForm, extra=order.orderitem_set.count(), can_delete=True)

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceItemFormSet(request.POST, instance=Invoice())

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.customer = order.customer
            # Populate customer details from the order or customer object
            invoice.customer_name = order.customer.get_full_name() if order.customer else order.shipping_address.split('\n')[0] if order.shipping_address else ''
            invoice.customer_phone = order.phone_number
            invoice.customer_email = order.customer.get_email() if order.customer else ''
            invoice.customer_address = order.shipping_address
            invoice.payment_method = order.payment_method
            invoice.total_amount = order.total_before_discount # Pre-tax/discount total from order
            invoice.is_paid = order.complete
            invoice.tax_rate = Decimal('0.00') # Default, can be adjusted manually
            invoice.discount_amount = Decimal('0.00') # Default, can be adjusted manually
            invoice.save()

            # Recalculate total_amount from items (before tax and discount)
            calculated_items_total = Decimal('0.00')
            for formset_form in formset:
                if formset_form.cleaned_data and not formset_form.cleaned_data.get('DELETE'):
                    item = formset_form.save(commit=False)
                    item.invoice = invoice
                    item.save()
                    calculated_items_total += item.line_total
            
            # Update total_amount based on invoice items, then recalculate final_total in save()
            invoice.total_amount = calculated_items_total
            invoice.save() # This save will trigger final_total calculation because fields are changed

            messages.success(request, "تم إنشاء الفاتورة بنجاح!")
            return redirect('accounting:edit_invoice', invoice_id=invoice.id) # Redirect to edit for review
    else:
        # Initial data for the invoice form
        initial_invoice_data = {
            'order': order,
            'customer': order.customer,
            'customer_name': order.customer.get_full_name() if order.customer else order.shipping_address.split('\n')[0] if order.shipping_address else '',
            'customer_phone': order.phone_number,
            'customer_email': order.customer.get_email() if order.customer else '',
            'customer_address': order.shipping_address,
            'total_amount': order.total_before_discount, # Use total_before_discount from order
            'is_paid': order.complete, 
            'invoice_date': timezone.now(), # This field is auto_now_add, so it won't be used by the form, but good for clarity
            'payment_method': order.payment_method,
            'tax_rate': Decimal('0.00'), # Default tax rate
            'discount_amount': order.coupon.discount_amount if order.coupon and order.discount_amount else Decimal('0.00'), # Use order's discount
            'final_total': order.final_total,
        }
        form = InvoiceForm(initial=initial_invoice_data)

        # Initial data for the invoice item formset
        initial_invoice_item_data = []
        for item_from_order in order.orderitem_set.all(): # Renaming 'item' to 'item_from_order' for clarity
            item_description = item_from_order.product.name if item_from_order.product else _("منتج محذوف/غير معروف")
            initial_invoice_item_data.append({
                'product': item_from_order.product,
                'description': item_description, 
                'quantity': item_from_order.quantity,
                'unit_price': item_from_order.price,
            })
        formset = InvoiceItemFormSet(initial=initial_invoice_item_data)

    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'title': 'إنشاء فاتورة من طلب'
    }
    return render(request, 'accounting/invoice_form.html', context)

@login_required
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    InvoiceItemFormSet = inlineformset_factory(Invoice, InvoiceItem, form=InvoiceItemForm, extra=1, can_delete=True)

    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceItemFormSet(request.POST, instance=invoice)

        if form.is_valid() and formset.is_valid():
            # Store original values before saving form (for save method's __init__)
            invoice._original_total_amount = invoice.total_amount
            invoice._original_tax_rate = invoice.tax_rate
            invoice._original_discount_amount = invoice.discount_amount
            
            invoice = form.save()
            formset.save()
            
            # Recalculate total amount from items
            calculated_items_total = sum(item.line_total for item in invoice.items.all())
            invoice.total_amount = calculated_items_total # Update total_amount from items
            invoice.save() # This save will trigger final_total calculation

            messages.success(request, "تم تحديث الفاتورة بنجاح!")
            return redirect('accounting:edit_invoice', invoice_id=invoice.id)
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceItemFormSet(instance=invoice)

    context = {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'title': 'تعديل الفاتورة'
    }
    return render(request, 'accounting/invoice_form.html', context)
