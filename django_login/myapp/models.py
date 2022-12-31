from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UserInfo(models.Model):

    nickname = models.CharField(max_length=100)
    userImg = models.ImageField(upload_to="userImg/", null=True, blank=True)
    belong = models.OneToOneField(User, on_delete=models.CASCADE, related_name="userinfo_user")

    def __str__(self):
        return self.nickname
    
    class Meta:
        verbose_name = '用户信息'