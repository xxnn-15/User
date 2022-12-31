from django.urls import path
from . import views
urlpatterns = [
    path('getToken/', views.getToken),
    path('getUserInfo/', views.UserInfoViews.as_view()),
    path('register/', views.register),
    path('sendVerificationCode/', views.sendVerificationCode),
    path('sendVerificationCode_forgetPassword/', views.sendVerificationCode_forgetPassword),
    path('checkVerificationCode/', views.checkVerificationCode),
    path('modifyPassword/', views.modifyPassword),
    path('modifyUserInfo/', views.modifyUserInfo)
]
