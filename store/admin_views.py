from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay
from store.models import Order, Customer, Product, OrderItem
from django.utils import timezone
import datetime
import json

@staff_member_required
def statistics_view(request):
    """
    Custom admin view for displaying store statistics.
    """
    # 1. Total Revenue (from completed orders)
    total_revenue = Order.objects.filter(complete=True).aggregate(total=Sum('total_amount'))['total'] or 0

    # 2. Total Orders
    total_orders = Order.objects.count()

    # 3. Total Customers
    total_customers = Customer.objects.count()

    # 4. Total Products
    total_products = Product.objects.count()

    # 5. Sales data for the last 30 days for the chart
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    sales_by_day = Order.objects.filter(complete=True, date_ordered__gte=thirty_days_ago) \
        .annotate(day=TruncDay('date_ordered')) \
        .values('day') \
        .annotate(total_sales=Sum('total_amount')) \
        .order_by('day')

    # Format data for Chart.js
    sales_chart_labels = [sale['day'].strftime('%Y-%m-%d') for sale in sales_by_day]
    sales_chart_data = [float(sale['total_sales']) for sale in sales_by_day]
    
    # 6. Best-selling products
    best_selling_products = OrderItem.objects.values('product__name') \
        .annotate(total_sold=Sum('quantity')) \
        .order_by('-total_sold')[:5] # Top 5

    products_chart_labels = [item['product__name'] for item in best_selling_products]
    products_chart_data = [item['total_sold'] for item in best_selling_products]


    context = {
        'title': 'إحصائيات المتجر',
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_customers': total_customers,
        'total_products': total_products,
        'sales_chart_labels': json.dumps(sales_chart_labels),
        'sales_chart_data': json.dumps(sales_chart_data),
        'products_chart_labels': json.dumps(products_chart_labels),
        'products_chart_data': json.dumps(products_chart_data),
    }
    return render(request, 'admin/statistics.html', context) 