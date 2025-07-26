from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'), # New dashboard view as default
    path('orders/', views.order_list_view, name='order_list'), # Dedicated order list
    path('orders/<int:order_id>/edit_status/', views.edit_order_status, name='edit_order_status'),
    path('orders/<int:order_id>/create-invoice/', views.create_invoice_from_order, name='create_invoice_from_order'),
    path('invoices/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),
    path('reports/', views.reports_view, name='reports'), # New financial reports view
    path('create/invoice/', views.create_invoice_view, name='create_invoice'), # New invoice creation view
    path('invoices/', views.invoice_list_view, name='invoice_list'), # New invoice list view
    path('invoices/<uuid:invoice_uuid>/', views.invoice_detail_view, name='invoice_detail'), # New invoice detail view using UUID
    path('invoices/<uuid:invoice_uuid>/print/thermal/', views.invoice_thermal_print_view, name='invoice_thermal_print_view'), # New thermal print view using UUID
] 