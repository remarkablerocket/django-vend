from datetime import datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse

import requests

from .models import VendRetailer


def login(request):
    client_id = getattr(settings, "VEND_KEY", None)
    if not client_id:
        raise ImproperlyConfigured('django setting VEND_KEY is required')

    redirect_uri = 'http://127.0.0.1:8000/vend/auth/complete/'
    state = 'test'

    url = 'https://secure.vendhq.com/connect?response_type=code&client_id={}&redirect_uri={}&state={}'.format(client_id, redirect_uri, state)

    request.session['vend_state'] = state
    return HttpResponseRedirect(url)

def complete(request):
    if request.method == 'GET':
        name = request.GET.get('domain_prefix')
        if not name:
            raise SuspiciousOperation('OAuth2 failure')
        code = request.GET.get('code')
        if not code:
            raise SuspiciousOperation('OAuth2 failure')
        user_id = request.GET.get('user_id')
        if not user_id:
            raise SuspiciousOperation('OAuth2 failure')
        returned_state = request.GET.get('state')
        session_state = request.session.get('vend_state')
        if returned_state is None or returned_state != session_state:
            raise SuspiciousOperation('OAuth2 failure')

        url = 'https://{}.vendhq.com/api/1.0/token'.format(name)
        client_id = getattr(settings, "VEND_KEY", None)
        if not client_id:
            raise ImproperlyConfigured('django setting VEND_KEY is required')
        client_secret = getattr(settings, "VEND_SECRET", None)
        if not client_secret:
            raise ImproperlyConfigured('django setting VEND_SECRET is required')
        redirect_uri = 'http://127.0.0.1:8000/vend/auth/complete/'

        data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
        r = requests.post(url, data=data)

        try:
            data = r.json()
        except ValueError:
            raise SuspiciousOperation('OAuth2 failure')
        access_token = data.get('access_token')
        if not access_token:
            raise SuspiciousOperation('OAuth2 failure')
        token_type = data.get('token_type')
        if not token_type or token_type != 'Bearer':
            raise SuspiciousOperation('OAuth2 failure')
        expires = data.get('expires')
        if not expires:
            raise SuspiciousOperation('OAuth2 failure')
        expires_in = data.get('expires_in')
        if not expires_in:
            raise SuspiciousOperation('OAuth2 failure')
        refresh_token  = data.get('refresh_token') 
        if not refresh_token:
            raise SuspiciousOperation('OAuth2 failure')

        try:
            retailer = VendRetailer.objects.get(name=name)
        except VendRetailer.DoesNotExist:
            retailer = VendRetailer(
                name=name,
                access_token=access_token,
                expires=datetime.fromtimestamp(expires),
                expires_in=expires_in,
                refresh_token=refresh_token,
            )
        else:
            retailer.access_token = access_token
            retailer.expires = datetime.fromtimestamp(expires)
            retailer.expires_in = expires_in
            retailer.refresh_token = refresh_token
        retailer.save()
        request.session['retailer_id'] = retailer.id
    
    else:
        raise SuspiciousOperation('{} request not allowed'.format(request.method))

    return HttpResponseRedirect('http://127.0.0.1:8000/vend/auth/select-user/')

def select_user(request):
    retailer_id = request.session.get('retailer_id')
    if retailer_id:
        retailer = VendRetailer.objects.get(id=retailer_id)
    else:
        return HttpResponseRedirect(reverse('vend_auth_login'))

    url = 'https://{}.vendhq.com/api/users'.format(retailer.name)

    headers = {
        'Authorization': 'Bearer {}'.format(retailer.access_token),
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    r = requests.get(url, headers=headers)
    try:
        users = r.json()['users']
        for user in users:
            print(user['id'])
    except (ValueError, KeyError):
        users = None

    return render(request, 'vend_auth/select_user.html', {'users': users})