from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from .models import (
    Category, Product, Customer, Order, OrderItem, Cart, CartItem, 
    Inquiry, Coupon, SiteConfiguration, Promotion, FAQ,
    BlogCategory, BlogPost, Wishlist, WishlistItem, Address, StoredPaymentMethod,
    PushSubscription, Notification, AboutPage, TeamMember, PhoneOTP, Expense
)
from django.urls import reverse
from django.utils.html import format_html
from pywebpush import webpush, WebPushException
import json
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.admin.views.main import ChangeList
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .resources import ProductResource
from ckeditor.widgets import CKEditorWidget
from django.db import models

# Set the site header and title in Arabic
admin.site.site_header = "لوحة تحكم متجر الهدايا"
admin.site.site_title = "متجر الهدايا"
admin.site.index_title = "مرحباً بك في لوحة التحكم"

# --- App-specific admin registrations ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

class ProductResource(resources.ModelResource):
    class Meta:
        model = Product

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'cost_price', 'stock', 'available', 'created', 'updated', 'get_image')
    list_filter = ('category', 'available', 'created', 'updated')
    search_fields = ('name', 'category__name')
    list_editable = ('price', 'cost_price', 'stock', 'available')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('get_image',)
    resource_class = ProductResource

    def get_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />'.format(obj.image.url))
        return "No Image"
    get_image.short_description = 'Image'

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'get_full_name', 'get_email')
    search_fields = ('name', 'email')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    readonly_fields = ('price', 'get_total')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'date_ordered', 'status', 'payment_status', 'final_total', 'complete']
    list_filter = ['status', 'payment_status', 'date_ordered']
    search_fields = ['id', 'customer__user__username', 'customer__user__first_name', 'customer__user__last_name']
    inlines = [OrderItemInline]
    change_form_template = 'admin/store/order/change_form.html'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer__user')

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'contact_email', 'phone_number')
    fieldsets = (
        (_('المعلومات الأساسية'), {'fields': ('site_name', 'logo')}),
        (_('معلومات التواصل'), {'fields': ('contact_email', 'phone_number', 'address', 'whatsapp_number')}),
        (_('روابط التواصل الاجتماعي'), {'fields': ('facebook_url', 'instagram_url', 'twitter_url')}),
    )

    def has_add_permission(self, request):
        # Allow adding if no instance exists yet
        return not SiteConfiguration.objects.exists()

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_replied')
    list_filter = ('is_replied', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'phone', 'subject', 'message', 'created_at', 'user')

    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'email', 'phone', 'subject', 'message', 'created_at')
        }),
        (_('الرد على الاستفسار'), {
            'fields': ('is_replied', 'reply')
        }),
    )

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount', 'valid_from', 'valid_to', 'active', 'share_link')
    list_filter = ('active', 'valid_from', 'valid_to')
    search_fields = ('code',)

    def get_list_display(self, request):
        """A bit of a hack to get the request object into the admin method"""
        self.request = request
        return super().get_list_display(request)

    def share_link(self, obj):
        url = reverse('store:shareable_coupon', args=[obj.code])
        # Use the request object stored from get_list_display
        full_url = self.request.build_absolute_uri(url)
        return format_html(
            '<a href=\"{0}\" target=\"_blank\">مشاركة</a> | '\
            '<a href=\"#\" onclick=\"navigator.clipboard.writeText(\'{0}\'); alert(\'تم نسخ الرابط!\'); return false;\">نسخ الرابط</a>', \
            full_url
        )
    share_link.short_description = 'مشاركة / نسخ الرابط'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('customer', 'created_at')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'get_total')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'link', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('title',)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'display_order', 'active')
    list_editable = ('display_order', 'active')
    search_fields = ('question', 'answer')
    list_filter = ('active',)

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'published_date', 'active')
    list_filter = ('active', 'category', 'published_date')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author',)
    date_hierarchy = 'published_date'
    ordering = ('-published_date',)

    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)

class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    readonly_fields = ('product', 'date_added')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('customer', 'created_at')
    inlines = [WishlistItemInline]
    readonly_fields = ('customer', 'created_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'read', 'created_at')
    list_filter = ('read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)
    list_select_related = ('user',)

class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1
    ordering = ['display_order']

@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):
    inlines = [TeamMemberInline]
    formfield_overrides = {
        models.TextField: {'widget': CKEditorWidget},
    }

    def has_add_permission(self, request):
        # Allow adding if no AboutPage instance exists yet
        return not AboutPage.objects.exists()

admin.site.register(PushSubscription)

class StoredPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'card_brand', 'last_four_digits', 'created_at')
    search_fields = ('customer__user__username', 'customer__user__email', 'card_brand')
    list_filter = ('card_brand', 'created_at')

admin.site.register(StoredPaymentMethod, StoredPaymentMethodAdmin)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'date', 'category', 'created_at')
    list_filter = ('date', 'category')
    search_fields = ('description', 'category')
