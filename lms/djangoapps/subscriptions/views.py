# View for semi-static templatized content.
#
# List of valid templates is explicitly managed for (short-term)
# security reasons.

from edxmako.shortcuts import render_to_response, render_to_string
from mako.exceptions import TopLevelLookupException
from django.shortcuts import redirect
from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponseServerError, Http404
from django.views.decorators.csrf import ensure_csrf_cookie
from util.cache import cache_if_anonymous
from django.views.decorators.http import require_http_methods
from openedx.core.djangoapps.user_api.accounts.api import check_account_exists
from django.contrib.auth.models import User, AnonymousUser
from student.views import create_account, create_account_with_params


def render_404(request):
    return redirect('/')


def render_500(request):
    return redirect('/')

# anonymous
# @ensure_csrf_cookie
# @cache_if_anonymous()

# logged
# @ensure_csrf_cookie
# @login_required

# external access
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt

@require_http_methods(["GET", "POST"])
def render_subs(request, template):
    import requests

    import appmysqldb
    mysql_host = getattr(settings, "SUBSCRIPTION_MYSQL_HOST", "localhost")
    mysql_database = getattr(settings, "SUBSCRIPTION_MYSQL_DB_NAME", "edxapp")
    mysql_user = getattr(settings, "SUBSCRIPTION_MYSQL_USER", "edxapp001")
    mysql_pwd = getattr(settings, "SUBSCRIPTION_MYSQL_PASSWORD", "password")

    user_id = 0
    step_pos = 1
    stype = '0'
    pay = ''
    pay_ok = '0'
    conflicts = ''
    frmbuttonpay = ''

    if request.GET.get('m'):
        stype = request.GET['m']

    if request.GET.get('pay'):
        pay = request.GET['pay']

    user = request.user
    if user.is_authenticated():
        if stype == '1' or stype == '4':
            step_pos = 3
        else:
            if stype == '2' or stype == '3' or stype == '5' or stype == '6':
                step_pos = 2
            else:
                return redirect('/dashboard')
    else:
        step_pos = 1
        user = user

    """ get form data  """
    datapost = ''
    UserInfo = {
        'Username': '',
        'LastName': '',
        'FirstName': '',
        'Email': '',
        'Password1': '',
        'Password2': '',
        'honor_code': 0
    }
    UserInfoError = {
        'Username': 1,
        'LastName': 1,
        'FirstName': 1,
        'Email': 1,
        'Password1': 1,
        'Password2': 1,
        'honor_code': 1
    }

    # edx account vars
    email = ""
    username = ""
    password = ""
    name = ""
    honor_code = ""

    if request.POST and step_pos == 1:
        datapost = request.POST.items()
        if request.POST.get("Username"):
            UserInfo['Username'] = request.POST["Username"]
            UserInfoError['Username'] = 0
            username = UserInfo['Username']

        if request.POST.get("LastName"):
            UserInfo['LastName'] = request.POST["LastName"]
            UserInfoError['LastName'] = 0
        if request.POST.get("FirstName"):
            UserInfo['FirstName'] = request.POST["FirstName"]
            UserInfoError['FirstName'] = 0
        if UserInfo['FirstName'] != '' and UserInfo['LastName'] != '':
            name = "%s %s" % (UserInfo['FirstName'], UserInfo['LastName'])

        if request.POST.get("Email"):
            import re
            check_email = request.POST["Email"]
            if check_email != '' and re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", check_email):
                UserInfo['Email'] = check_email
                UserInfoError['Email'] = 0
                email = check_email

        if request.POST.get("Password1"):
            UserInfo['Password1'] = request.POST["Password1"]
            UserInfoError['Password1'] = 0
        if request.POST.get("Password2"):
            UserInfo['Password2'] = request.POST["Password2"]
            UserInfoError['Password2'] = 0

        if request.POST.get("honor_code"):
            UserInfo['honor_code'] = 1
            UserInfoError['honor_code'] = 0
            honor_code = 1

        if UserInfo['Password1'] != '' and UserInfo['Password2'] != '':
            if UserInfo['Password1'] != UserInfo['Password2']:
                UserInfoError['Password2'] = 1
            else:
                password = UserInfo['Password1']

        # Handle duplicate email/username
        if email != '' and username != '' and name != '' and honor_code == 1 and password != '':
            check_account = check_account_exists(email=email, username=username)
            if "email" in check_account:
                conflicts = "It looks like the email entered belongs to an existing account."
            if "username" in check_account:
                conflicts = "It looks like the username entered belongs to an existing account."

            # Create a new account
        if conflicts == "":
            conflicts = "creating a new account"
            user = User.objects.filter(username=username)

            if not user.exists():
                post_vars = dict(
                    username=username,
                    honor_code=u'true',
                    is_active=u'true',
                    email=email,
                    terms_of_service=u'true',
                    name=name,
                    first_name=UserInfo['FirstName'],
                    first_lastname=UserInfo['LastName'],
                    password=password,
                    backend="django_subscription"
                )
                # print post_vars
                user = create_account_with_params(request, post_vars)
                if user.is_authenticated():
                    redirect_to = "/subscription?m=%s" % (stype)
                    return redirect(redirect_to)

    # step2 or step3
    if user != '' and (step_pos == 3 or step_pos == 2):
        sus_id = 0
        type_sus = 0

        # check user_id
        db = appmysqldb.mysql(mysql_host, 3306, mysql_database, mysql_user, mysql_pwd)
        q = "SELECT id,email FROM auth_user WHERE username='%s' LIMIT 1" % (user)
        db.query(q)
        res = db.fetchall()
        for row in res:
            user_id = row[0]
            edx_email = row[1]

        if step_pos == 2 and user_id > 0:
            if pay == 'done':
                params = request.POST.dict()
                pay_params = u",".join([u"{0}={1}".format(k, params.get(k, '')) for k in params])
                pay_status = u"{0}".format(params.get('payment_status', ''))
                if pay_status == 'Completed' or pay_status == 'Processed':
                    pay_ok = '1'
                else:
                    import datetime
                    now = datetime.datetime.now()
                    date_sus = now.strftime("%Y-%m-%d")
                    if pay_params == '':
                        pay_params = 'User Return to platform'
                    if pay_status == '':
                        pay_status = 'Pending'
                    set_enabled = 0
                    q = "INSERT INTO aux_subscriptions (user_id,email,type_sus,date_sus,pay_params,pay_status,enabled) VALUES('%s','%s','%s','%s','%s','%s','%s')" % (user_id,edx_email,stype,date_sus,pay_params,pay_status,set_enabled)
                    db.query(q)
            else:
                # check aux_subs type_sus individual or enterprises
                if stype == 2 or stype == 3:
                    check_stype = 1
                else:
                    check_stype = 4
                # check aux_subscription
                check_sus_id = 0
                q = "SELECT aux_subscription_id,type_sus FROM aux_subscriptions WHERE user_id='%s' AND (type_sus='1' OR type_sus='4') LIMIT 1" % (user_id)
                db.query(q)
                res = db.fetchall()
                for row in res:
                    check_sus_id = row[0]
                    get_type = row[1]
                if check_sus_id > 0:
                    if check_stype != get_type:
                        q = "UPDATE aux_subscriptions SET type_sus='%s' WHERE aux_subscription_id='%s'" % (check_stype, sus_id)
                        db.query(q)
                else:
                    if user_id > 0:
                        import datetime
                        now = datetime.datetime.now()
                        date_sus = now.strftime("%Y-%m-%d")
                        q = "INSERT INTO aux_subscriptions (user_id,email,type_sus,date_sus) VALUES('%s','%s','%s','%s')" % (user_id,edx_email,check_stype,date_sus)
                        db.query(q)

                # print paypal button
                import paybuild
                frmbuttonpay = paybuild.build_cb_payment(stype, user_id, edx_email, debug_mode='0')

        if step_pos == 3 and user_id > 0:
            # check aux_subscription
            q = "SELECT aux_subscription_id,type_sus FROM aux_subscriptions WHERE user_id='%s' LIMIT 1" % (user_id)
            db.query(q)
            res = db.fetchall()
            for row in res:
                sus_id = row[0]
                type_sus = row[1]

            if sus_id > 0:
                if stype != type_sus:
                    q = "UPDATE aux_subscriptions SET type_sus='%s' WHERE aux_subscription_id='%s'" % (stype, sus_id)
                    db.query(q)
            else:
                if user_id > 0:
                    import datetime
                    now = datetime.datetime.now()
                    date_sus = now.strftime("%Y-%m-%d")
                    q = "INSERT INTO aux_subscriptions (user_id,email,type_sus,date_sus) VALUES('%s','%s','%s','%s')" % (user_id,edx_email,stype,date_sus)
                    db.query(q)

    # processing step1
    step_error = 0
    if step_pos == 1:
        for key, value in UserInfoError.iteritems():
            if value == 1:
                step_error = 1

    # processing step2 and step3
    if step_pos == 2:
        if pay == 'done':
            template = "subscription.4.html"
        else:
            template = "subscription.2.html"
    else:
        if step_pos == 3:
            template = "subscription.3.html"
        else:
            template = "subscription.html"

    # return template
    return render_to_response(
        'subscriptions/' + template,
        {
            'stype': stype,
            'UserInfo': UserInfo,
            'UserInfoError': UserInfoError,
            'step_pos': step_pos,
            'step_error': step_error,
            'conflicts': conflicts,
            'user': user,
            'frmbuttonpay': frmbuttonpay,
            'pay_ok': pay_ok
        }
    )

    try:
        resp = render_to_response(
            'subscriptions/subscription.2.html',
            {'stype': stype}
        )
    except TopLevelLookupException:
        raise Http404
    else:
        return resp


@csrf_exempt
@require_http_methods(["GET", "POST"])
def render_pay_callback(request):
    params = ''
    pay_params = ''
    pay_ok = '0'
    pay_item = ''
    pay_reference = ''
    pay_status = ''
    pay_date = ''
    edx_user_id = '0'
    edx_type_sus = ''
    edx_email = ''

    if request.method == "GET":
        params = request.GET.dict()
    elif request.method == "POST":
        params = request.POST.dict()

    if params != "":
        import appmysqldb
        mysql_host = getattr(settings, "SUBSCRIPTION_MYSQL_HOST", "172.31.23.49")
        mysql_database = getattr(settings, "SUBSCRIPTION_MYSQL_DB_NAME", "edxapp")
        mysql_user = getattr(settings, "SUBSCRIPTION_MYSQL_USER", "edxapp001")
        mysql_pwd = getattr(settings, "SUBSCRIPTION_MYSQL_PASSWORD", "password")

        db = appmysqldb.mysql(mysql_host, 3306, mysql_database, mysql_user, mysql_pwd)

        pay_params = u",".join([u"{0}={1}".format(k, params.get(k, '')) for k in params])
        pay_status = u"{0}".format(params.get('payment_status', ''))
        if pay_status == 'Completed' or pay_status == 'Processed':
            pay_ok = '1'
        pay_item = u"{0}".format(params.get('item_name', ''))
        pay_reference = u"{0}".format(params.get('item_number', ''))
        pay_date = u"{0}".format(params.get('payment_date', ''))
        pay_email = u"{0}".format(params.get('payer_email', ''))
        custom_payment = u"{0}".format(params.get('custom', ''))
        if custom_payment != '':
            data_custom = custom_payment.split('|')
            if data_custom[0] != '' and data_custom[1] != '':
                edx_user_id = data_custom[0]
                edx_type_sus = data_custom[1]

        if edx_user_id > 0 and edx_type_sus != '':
            q = "SELECT email FROM auth_user WHERE id='%s'" % (edx_user_id)
            db.query(q)
            res = db.fetchall()
            for row in res:
                edx_email = row[0]

        if pay_item != '' and pay_reference != '' and pay_status != '':
            import datetime
            now = datetime.datetime.now()
            date_sus = now.strftime("%Y-%m-%d")
            q_aux_payments = "INSERT INTO aux_subscriptions "
            q_aux_payments += " (user_id,email,type_sus,pay_item,pay_reference,pay_email,pay_status,pay_ok,pay_date,pay_params,date_sus)"
            q_aux_payments += " VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s')" % (edx_user_id, edx_email, edx_type_sus, pay_item, pay_reference,
                                                                                               pay_email, pay_status, pay_ok, pay_date, pay_params,date_sus)
            db.query(q_aux_payments)

    try:
        resp = render_to_response(
            'subscriptions/pay_callback.html',
            {
                'pay_ok': pay_ok,
                'pay_item': pay_item,
                'pay_reference': pay_reference,
                'pay_date': pay_date,
                'pay_status': pay_status,
                'edx_user_id': edx_user_id,
                'edx_type_sus': edx_type_sus
            }
        )
    except TopLevelLookupException:
        raise Http404
    else:
        return resp
