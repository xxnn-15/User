from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(UserInfo)
class UserInfoAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'userImg', 'belong']