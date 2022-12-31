from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail

from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from django_redis import get_redis_connection

import eventlet

from .models import *
from .serializers import UserInfoSerializer


# Create your views here.
@api_view(['POST'])
def getToken(request):
    email = request.POST['email']
    password = request.POST['password']
    # print(name, password)
    user = User.objects.filter(email=email)

    if user:
        # 判断密码是否正确，正确返回true
        isnotuser = check_password(password, user[0].password)
        if isnotuser:
            # 获取用户 token
            tokenForm = Token.objects.update_or_create(user=user[0])
            token = tokenForm[0].key
            return Response(token)
        else:
            return Response('password error')
    else:
        return Response('user none')


class UserInfoViews(APIView):
    def get(self, request):
        return Response('getUserInfo')

    def post(self, request):
        token = request.POST['token']
        # print(token)

        # 这里响应前端的 tryAutoLogin， 可以在此添加基于 token 的校验，比如校验 token 是否过期，这个时间可以自己决定
        token_user = Token.objects.filter(key=token)  # 当查询条件不符合时候，返回空列表，使用 get 方法的话，则会直接报错
        # token_user.created 即为这个 token 的创建时间，本例中每次登录时，根据 update_or_created 会重新更新这个时间，
        # 所以不会有过期的问题，但这样token 是永远不变的，存在安全问题。
        if token_user:
            userinfo = UserInfo.objects.get(belong=token_user[0].user)
            email = token_user[0].user.email
            userinfo_response = {'email': email, 'nickname': userinfo.nickname, 'userImg': str(userinfo.userImg),
                                 'status': 'available'}
        else:
            userinfo_response = {'email': '未登录', 'nickname': '未登录', 'userImg': 'logo.png',
                                 'status': 'unavailable'}
        return Response(userinfo_response)


def token_to_user(token):
    '''
        根据 token 返回相应的用户实例，如果失败返回 False
    '''
    token_user = Token.objects.filter(key=token)  # 当查询条件不符合时候，返回空列表，使用 get 方法的话，则会直接报错
    if token_user:
        user = token_user[0].user
        return user
    else:
        return False


@api_view(['POST'])
def register(request):
    data = request.POST
    # print(data)

    email = data['email']
    password = data['password']
    password = make_password(password)  # 明文密码经过加密处理
    username = email  # user 表中的 username 设置为与 email 同值，因为在表中 username 为主键

    # 创建新用户
    u = User.objects.create(username=username, password=password, email=email)
    u.save()

    # 给新用户设置用户信息
    nickname = data['nickname']
    userImgRequest = request.FILES['userImg']
    userImg = userImgRequest.read()
    userImgName = userImgRequest.name
    # 找到 . 的位置, 将图片名字修改为邮箱名并保留后缀
    where = userImgName.rfind(".")
    format = userImgName[where:]
    imgname = email + format
    # print(imgname)
    belong = u  # user

    # 保存用户信息
    ui = UserInfo.objects.create(nickname=nickname, userImg="userImg/" + imgname, belong=belong)
    ui.save()

    # 将用户图片存到服务器中
    with open("upload/" + "userImg/" + imgname, "wb") as f:
        f.write(userImg)
    return Response('ok')


def sendEmail(email):
    # 生成验证码
    import random
    str1 = '0123456789'
    rand_str = ''
    for i in range(0, 6):
        rand_str += str1[random.randrange(0, len(str1))]

    # 发送邮件：
    # send_mail的参数分别是  邮件标题，邮件内容)
    message = "您的验证码是" + rand_str + "，5分钟内有效，请尽快填写"
    # 添加收件邮箱
    emailBox = []
    emailBox.append(email)
    send_mail('django_login', message, '2601256080@qq.com', emailBox, fail_silently=False)
    return rand_str


@api_view(['POST'])
def sendVerificationCode(request):
    data = request.POST
    register_str = data['register']  # 是否为用户注册, 值为字符串 'true' 或 'false'
    if register_str == 'true':
        register = True
    else:
        register = False
    response = {
        "state": "fail",
        "msg": ""
    }
    if register:
        email = data['email']
        # 用户注册，先判断这个邮箱是否被注册过了
        if User.objects.filter(email=email):
            response['msg'] = "该邮箱已被注册"
            return Response(response)

        # 如果是用户注册，则将用户填写的邮箱作为 key 存在 redis 中
        key = email
    else:
        # 如果是用户修改密码，则把用户的 token 作为 key 存在 redis 中
        token = data['token']
        user = token_to_user(token)
        if user:
            email = user.email
            key = token
        else:
            response['msg'] = '未通过身份验证'
            return Response(response)

    # 发送随机字符串到指定邮箱, 并在 redis 中存下 key 和这个随机的字符串
    try:
        # 在有些情况下，可能因为一些外部因素导致无法发出邮件，限制一下程序运行时长，超过 3s 报错 (以下方法测试的时候有 bug 弃用)
        # 但我认为限制程序运行时间是必要的，因为这样没有发送成功的话可以及时给用户通知到，这个将来再改进吧
        # 经测试 eventlet 方法在 云服务器上运行良好，在 mac 本地无法运行

        eventlet.monkey_patch()
        time_limit = 3
        with eventlet.Timeout(time_limit, False):
            rand_str = sendEmail(email)
        # rand_str = sendEmail(email)
        # print(rand_str)
        # 实例化 redis
        redis_cli = get_redis_connection('verification_code')  # 这个是上面配置setting中的命名
        redis_cli.set(key, rand_str, 300)  # email 是key, rand_str是value, 300是以秒为单位的短信验证码有效时间
        # set 设置，get 获取， delete 删除， exists 存在，ttl 过期时间

        response['state'] = 'success'
        response['msg'] = '验证码发送成功'
    except Exception as e:
        print(e)
        response['msg'] = '验证码发送失败'
    return Response(response)

@api_view(['POST'])
def sendVerificationCode_forgetPassword(request):
    # 用户忘记密码
    data = request.POST
    email = data['email']
    response = {
        "state": "fail",
        "msg": ""
    }
    # 如果没有该用户
    if not User.objects.filter(email=email):
        response['msg'] = "该用户不存在"
        return Response(response)
    
    # 将用户填写的邮箱作为 key 存在 redis 中
    key = email

    try:
        # 在有些情况下，可能因为一些外部因素导致无法发出邮件，限制一下程序运行时长，超过 3s 报错 (以下方法测试的时候有 bug 弃用)
        # 但我认为限制程序运行时间是必要的，因为这样没有发送成功的话可以及时给用户通知到，这个将来再改进吧
        # 经测试 eventlet 方法在 云服务器上运行良好，在 mac 本地无法运行

        eventlet.monkey_patch()
        time_limit = 3
        with eventlet.Timeout(time_limit, False):
            rand_str = sendEmail(email)
        # rand_str = sendEmail(email)
        # print(rand_str)
        # 实例化 redis
        redis_cli = get_redis_connection('verification_code')  # 这个是上面配置setting中的命名
        redis_cli.set(key, rand_str, 300)  # email 是key, rand_str是value, 300是以秒为单位的短信验证码有效时间
        # set 设置，get 获取， delete 删除， exists 存在，ttl 过期时间

        response['state'] = 'success'
        response['msg'] = '验证码发送成功'
    except Exception as e:
        print(e)
        response['msg'] = '验证码发送失败'
    return Response(response)


# 接收前端发来的验证码，进行身份验证
@api_view(['POST'])
def checkVerificationCode(request):
    data = request.POST

    register_str = data['register']  # 是否为用户注册, 值为字符串 'true' 或 'false'
    if register_str == 'true':
        register = True
    else:
        register = False

    response = {
        "state": "fail",
        "msg": ""
    }
    # 判断是否为用户注册
    if register:
        email = data['email']
        key = email  # 如果是用户注册，则 redis 的key为 email
        verificationCode = data['verificationCode']
    else:
        token = data['token']
        key = token  # 如果是用户修改密码则 redis 的 key 为 token
        verificationCode = data['verificationCode']

    # 在 redis 中通过 key 拿到缓存
    redis_cli = get_redis_connection('verification_code')  # 这个链接名字要与存验证码的相同
    if redis_cli.exists(key):
        # 缓存中的验证码还没过期
        true_code = redis_cli.get(key)  # 字节形式
        true_code = str(true_code, 'utf-8')
        if true_code == verificationCode:
            # 验证通过，可以修改密码
            response['state'] = 'success'
        else:
            # 验证码错误
            response['state'] = 'fail'
            response['msg'] = '验证码错误'
    else:
        # 缓存中没有验证码或已过期
        response['state'] = 'fail'
        response['msg'] = '验证码失效'

    return Response(response)


@api_view(['POST'])
def modifyPassword(request):
    data = request.POST
    newPassword = data['newPassword']
    token = data['token']
    response = {
        'state': 'fail',
        'msg': ''
    }

    # 如果 token 是 none 则代表用户是忘记密码了，根据给出的邮箱来找到用户
    if token == 'none':
        email = data['email']
        user = User.objects.filter(email=email)[0]
        token_user = Token.objects.filter(user=user)

    # 如果 token 不是 none 则代表是用户修改密码 根据 token 找到用户
    else:
        user = token_to_user(token)
        token_user = Token.objects.filter(key=token)

    if user:
        # 修改指定用户的密码并更新 token 
        try:
            newPassword = make_password(newPassword)
            user.password = newPassword
            user.save()
            # 删除原来的 token
            token_user.delete()
            # 新建一个 token 并与该用户关联
            Token.objects.create(user=user)
            response['state'] = 'success'
            response['msg'] = '修改密码成功'
        except:
            response['state'] = 'fail'
            response['msg'] = '修改密码失败'

    else:
        response['state'] = 'fail'
        response['msg'] = '找不到指定用户'

    return Response(response)


@api_view(['POST'])
def modifyUserInfo(request):
    data = request.POST
    token = data['token']
    nickname = data['nickname']

    newNickName = False  # 是否上传了用户名
    # 如果上传的用户名不为空，则视为用户名发生了改变
    if nickname != '':
        newNickName = True

    newUserImage = False  # 是否上传了用户图片
    try:
        userImgRequest = request.FILES['userImg']
        userImg = userImgRequest.read()
        userImgName = userImgRequest.name
        newUserImage = True
    except:
        # 没有上传图片，即无法在 request中接收文件
        newUserImage = False
    response = {
        "state": "fail",
        "msg": ""
    }
    # 根据 token 找到相应的用户
    user = token_to_user(token)
    if user:
        # 修改指定用户的密码
        try:
            # 根据 user 找到相应的 userinfo
            userInfo = UserInfo.objects.filter(belong=user)[0]
            # 修改昵称
            if newNickName:
                userInfo.nickname = nickname

            # 修改图片
            if newUserImage:
                # 找到 . 的位置, 将图片名字修改为邮箱名并保留后缀
                where = userImgName.rfind(".")
                format = userImgName[where:]
                imgname = user.email + format
                # ImageField 类型的值是图片在 MEDIA_ROOT 文件夹下的路径
                userInfo.userImg = "userImg/" + imgname
                # 在 MEDIA_ROOT 中写入新的用户图片
                with open("upload/" + "userImg/" + imgname, "wb") as f:
                    f.write(userImg)

            # 将所做的修改保存到数据库中
            userInfo.save()

            response['state'] = 'success'
            response['msg'] = '修改用户信息成功'
        except:
            response['state'] = 'fail'
            response['msg'] = '修改用户信息失败'

    else:
        response['state'] = 'fail'
        response['msg'] = '找不到指定用户'

    return Response(response)
