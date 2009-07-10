#!/usr/bin/env python
#
# Copyright (C) 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# This module is used for version 2 of the Google Data APIs.

"""Provides auth related token classes and functions for Google Data APIs.

Token classes represent a user's authorization of this app to access their
data. Usually these are not created directly but by a GDClient object.

ClientLoginToken
AuthSubToken
OAuthHmacToken
"""


import time
import random
import urllib
import atom.http_core


__author__ = 'j.s@google.com (Jeff Scudder)'


PROGRAMMATIC_AUTH_LABEL = 'GoogleLogin auth='
AUTHSUB_AUTH_LABEL = 'AuthSub token='


# ClientLogin functions and classes.
def generate_client_login_request_body(email, password, service, source, 
    account_type='HOSTED_OR_GOOGLE', captcha_token=None, 
    captcha_response=None):
  """Creates the body of the autentication request

  See http://code.google.com/apis/accounts/AuthForInstalledApps.html#Request
  for more details.

  Args:
    email: str
    password: str
    service: str
    source: str
    account_type: str (optional) Defaul is 'HOSTED_OR_GOOGLE', other valid
        values are 'GOOGLE' and 'HOSTED'
    captcha_token: str (optional)
    captcha_response: str (optional)

  Returns:
    The HTTP body to send in a request for a client login token.
  """
  # Create a POST body containing the user's credentials.
  request_fields = {'Email': email,
                    'Passwd': password,
                    'accountType': account_type,
                    'service': service,
                    'source': source}
  if captcha_token and captcha_response:
    # Send the captcha token and response as part of the POST body if the
    # user is responding to a captch challenge.
    request_fields['logintoken'] = captcha_token
    request_fields['logincaptcha'] = captcha_response
  return urllib.urlencode(request_fields)


GenerateClientLoginRequestBody = generate_client_login_request_body


def get_client_login_token_string(http_body):
  """Returns the token value for a ClientLoginToken.

  Reads the token from the server's response to a Client Login request and
  creates the token value string to use in requests.

  Args:
    http_body: str The body of the server's HTTP response to a Client Login
        request
 
  Returns:
    The token value string for a ClientLoginToken.
  """
  for response_line in http_body.splitlines():
    if response_line.startswith('Auth='):
      # Strip off the leading Auth= and return the Authorization value.
      return response_line[5:]
  return None


GetClientLoginTokenString = get_client_login_token_string


def get_captcha_challenge(http_body, 
    captcha_base_url='http://www.google.com/accounts/'):
  """Returns the URL and token for a CAPTCHA challenge issued by the server.

  Args:
    http_body: str The body of the HTTP response from the server which 
        contains the CAPTCHA challenge.
    captcha_base_url: str This function returns a full URL for viewing the 
        challenge image which is built from the server's response. This
        base_url is used as the beginning of the URL because the server
        only provides the end of the URL. For example the server provides
        'Captcha?ctoken=Hi...N' and the URL for the image is
        'http://www.google.com/accounts/Captcha?ctoken=Hi...N'

  Returns:
    A dictionary containing the information needed to repond to the CAPTCHA
    challenge, the image URL and the ID token of the challenge. The 
    dictionary is in the form:
    {'token': string identifying the CAPTCHA image,
     'url': string containing the URL of the image}
    Returns None if there was no CAPTCHA challenge in the response.
  """
  contains_captcha_challenge = False
  captcha_parameters = {}
  for response_line in http_body.splitlines():
    if response_line.startswith('Error=CaptchaRequired'):
      contains_captcha_challenge = True
    elif response_line.startswith('CaptchaToken='):
      # Strip off the leading CaptchaToken=
      captcha_parameters['token'] = response_line[13:]
    elif response_line.startswith('CaptchaUrl='):
      captcha_parameters['url'] = '%s%s' % (captcha_base_url,
          response_line[11:])
  if contains_captcha_challenge:
    return captcha_parameters
  else:
    return None


GetCaptchaChallenge = get_captcha_challenge


class ClientLoginToken(object):

  def __init__(self, token_string):
    self.token_string = token_string

  def modify_request(self, http_request):
    http_request.headers['Authorization'] = '%s%s' % (PROGRAMMATIC_AUTH_LABEL,
        self.token_string)

  ModifyRequest = modify_request


# AuthSub functions and classes.
def _to_uri(str_or_uri):
  if isinstance(str_or_uri, (str, unicode)):
    return atom.http_core.Uri.parse_uri(str_or_uri)
  return str_or_uri


def generate_auth_sub_url(next, scopes, secure=False, session=True,
    request_url=atom.http_core.parse_uri(
        'https://www.google.com/accounts/AuthSubRequest'),
    domain='default', scopes_param_prefix='auth_sub_scopes'):
  """Constructs a URI for requesting a multiscope AuthSub token.

  The generated token will contain a URL parameter to pass along the
  requested scopes to the next URL. When the Google Accounts page
  redirects the broswser to the 'next' URL, it appends the single use
  AuthSub token value to the URL as a URL parameter with the key 'token'.
  However, the information about which scopes were requested is not
  included by Google Accounts. This method adds the scopes to the next
  URL before making the request so that the redirect will be sent to
  a page, and both the token value and the list of scopes for which the token
  was requested.

  Args:
    next: atom.http_core.Uri or string The URL user will be sent to after
          authorizing this web application to access their data.
    scopes: list containint strings or atom.http_core.Uri objects. The URLs
            of the services to be accessed.
    secure: boolean (optional) Determines whether or not the issued token
            is a secure token.
    session: boolean (optional) Determines whether or not the issued token
             can be upgraded to a session token.
    request_url: atom.http_core.Uri or str The beginning of the request URL.
                 This is normally 
                 'http://www.google.com/accounts/AuthSubRequest' or
                 '/accounts/AuthSubRequest'
    domain: The domain which the account is part of. This is used for Google
            Apps accounts, the default value is 'default' which means that
            the requested account is a Google Account (@gmail.com for
            example)
    scopes_param_prefix: str (optional) The requested scopes are added as a
                         URL parameter to the next URL so that the page at
                         the 'next' URL can extract the token value and the
                         valid scopes from the URL. The key for the URL
                         parameter defaults to 'auth_sub_scopes'

  Returns:
    An atom.http_core.Uri which the user's browser should be directed to in
    order to authorize this application to access their information.
  """
  if isinstance(next, (str, unicode)):
    next = atom.http_core.Uri.parse_uri(next)
  scopes_string = ' '.join([str(scope) for scope in scopes])
  next.query[scopes_param_prefix] = scopes_string

  if isinstance(request_url, (str, unicode)):
    request_url = atom.http_core.Uri.parse_uri(request_url)
  request_url.query['next'] = str(next)
  request_url.query['scope'] = scopes_string
  if session:
    request_url.query['session'] = '1'
  else:
    request_url.query['session'] = '0'
  if secure:
    request_url.query['secure'] = '1'
  else:
    request_url.query['secure'] = '0'
  request_url.query['hd'] = domain
  return request_url


def auth_sub_string_from_url(url, scopes_param_prefix='auth_sub_scopes'):
  """Finds the token string (and scopes) after the browser is redirected.

  After the Google Accounts AuthSub pages redirect the user's broswer back to
  the web application (using the 'next' URL from the request) the web app must
  extract the token from the current page's URL. The token is provided as a
  URL parameter named 'token' and if generate_auth_sub_url was used to create
  the request, the token's valid scopes are included in a URL parameter whose
  name is specified in scopes_param_prefix.

  Args:
    url: atom.url.Url or str representing the current URL. The token value
         and valid scopes should be included as URL parameters.
    scopes_param_prefix: str (optional) The URL parameter key which maps to
                         the list of valid scopes for the token.

  Returns:
    A tuple containing the token value as a string, and a tuple of scopes 
    (as atom.http_core.Uri objects) which are URL prefixes under which this
    token grants permission to read and write user data.
    (token_string, (scope_uri, scope_uri, scope_uri, ...))
    If no scopes were included in the URL, the second value in the tuple is
    None. If there was no token param in the url, the tuple returned is 
    (None, None)
  """
  if isinstance(url, (str, unicode)):
    url = atom.http_core.Uri.parse_uri(url)
  if 'token' not in url.query:
    return (None, None)
  token = url.query['token']
  # TODO: decide whether no scopes should be None or ().
  scopes = None # Default to None for no scopes.
  if scopes_param_prefix in url.query:
    scopes = tuple(url.query[scopes_param_prefix].split(' '))
  return (token, scopes)


AuthSubStringFromUrl = auth_sub_string_from_url


def auth_sub_string_from_body(http_body):
  """Extracts the AuthSub token from an HTTP body string.

  Used to find the new session token after making a request to upgrade a
  single use AuthSub token.

  Args:
    http_body: str The repsonse from the server which contains the AuthSub
        key. For example, this function would find the new session token
        from the server's response to an upgrade token request.

  Returns:
    The raw token value string to use in an AuthSubToken object.
  """
  for response_line in http_body.splitlines():
    if response_line.startswith('Token='):
      # Strip off Token= and return the token value string.
      return response_line[6:]
  return None


class AuthSubToken(object):

  def __init__(self, token_string, scopes=None):
    self.token_string = token_string
    self.scopes = scopes or []

  def modify_request(self, http_request):
    http_request.headers['Authorization'] = '%s%s' % (AUTHSUB_AUTH_LABEL,
        self.token_string)

  ModifyRequest = modify_request

  def from_url(str_or_uri):
    """Creates a new AuthSubToken using information in the URL.
    
    Uses auth_sub_string_from_url.

    Args:
      str_or_uri: The current page's URL (as a str or atom.http_core.Uri)
                  which should contain a token query parameter since the
                  Google auth server redirected the user's browser to this
                  URL.
    """
    token_and_scopes = auth_sub_string_from_url(str_or_uri)
    return AuthSubToken(token_and_scopes[0], token_and_scopes[1])

  from_url = staticmethod(from_url)
  FromUrl = from_url

  def _upgrade_token(self, http_body):
    """Replaces the token value with a session token from the auth server.
    
    Uses the response of a token upgrade request to modify this token. Uses
    auth_sub_string_from_body.
    """
    self.token_string = auth_sub_string_from_body(http_body)


# OAuth functions and classes.
RSA_SHA1 = 'RSA-SHA1'
HMAC_SHA1 = 'HMAC-SHA1'


def build_oauth_base_string(http_request, consumer_key, nonce, signaure_type,
                            timestamp, version, next='oob', token=None,
                            verifier=None):
  """Generates the base string to be signed in the OAuth request.
  
  Args:
    http_request: The request being made to the server. The Request's URL
        must be complete before this signature is calculated as any changes
        to the URL will invalidate the signature.
    consumer_key: Domain identifying the third-party web application. This is
        the domain used when registering the application with Google. It
        identifies who is making the request on behalf of the user.
    nonce: Random 64-bit, unsigned number encoded as an ASCII string in decimal
        format. The nonce/timestamp pair should always be unique to prevent
        replay attacks.
    signaure_type: either RSA_SHA1 or HMAC_SHA1
    timestamp: Integer representing the time the request is sent. The
        timestamp should be expressed in number of seconds after January 1,
        1970 00:00:00 GMT.
    version: The OAuth version used by the requesting web application. This
        value must be '1.0' or '1.0a'. If not provided, Google assumes version
        1.0 is in use.
    next: The URL the user should be redirected to after granting access
        to a Google service(s). It can include url-encoded query parameters.
        The default value is 'oob'. (This is the oauth_callback.)
    token: The string for the OAuth request token or OAuth access token.
    verifier: str Sent as the oauth_verifier and required when upgrading a 
        request token to an access token.
  """
  # First we must build the canonical base string for the request.
  params = http_request.uri.query.copy()
  params['oauth_consumer_key'] = consumer_key
  params['oauth_nonce'] = nonce
  params['oauth_signature_method'] = signaure_type
  params['oauth_timestamp'] = str(timestamp)
  if next is not None:
    params['oauth_callback'] = str(next)
  if token is not None:
    params['oauth_token'] = token
  if version is not None:
    params['oauth_version'] = version
  if verifier is not None:
    params['oauth_verifier'] = verifier
  # We need to get the key value pairs in lexigraphically sorted order.
  sorted_keys = sorted(params.keys())
  pairs = []
  for key in sorted_keys:
    pairs.append('%s=%s' % (urllib.quote(key, safe='~'),
                            urllib.quote(params[key], safe='~')))
  # We want to escape /'s too, so use safe='~'
  all_parameters = urllib.quote('&'.join(pairs), safe='~')
  normailzed_host = http_request.uri.host.lower()
  normalized_scheme = (http_request.uri.scheme or 'http').lower()
  non_default_port = None
  if (http_request.uri.port is not None 
      and ((normalized_scheme == 'https' and http_request.uri.port != 443) 
           or (normalized_scheme == 'http' and http_request.uri.port != 80))):
    non_default_port = http_request.uri.port
  path = http_request.uri.path or '/'
  request_path = None
  if not path.startswith('/'):
    path = '/%s' % path
  if non_default_port is not None:
    # Set the only safe char in url encoding to ~ since we want to escape / 
    # as well.
    request_path = urllib.quote('%s://%s:%s%s' % (
        normalized_scheme, normailzed_host, non_default_port, path), safe='~')
  else:
    # Set the only safe char in url encoding to ~ since we want to escape / 
    # as well.
    request_path = urllib.quote('%s://%s%s' % (
        normalized_scheme, normailzed_host, path), safe='~')
  # TODO: ensure that token escaping logic is correct, not sure if the token
  # value should be double escaped instead of single. 
  base_string = '&'.join((http_request.method.upper(), request_path,
                          all_parameters))
  # Now we have the base string, we can calculate the oauth_signature.
  return base_string


def generate_hmac_signature(http_request, consumer_key, consumer_secret,
                            timestamp, nonce, version, next='oob',
                            token=None, token_secret=None, verifier=None):
  import hmac
  import base64
  base_string = build_oauth_base_string(
      http_request, consumer_key, nonce, HMAC_SHA1, timestamp, version,
      next, token, verifier=verifier)
  hash_key = None
  hashed = None
  if token_secret is not None:
    hash_key = '%s&%s' % (urllib.quote(consumer_secret, safe='~'),
                          urllib.quote(token_secret, safe='~'))
  else:
    hash_key = '%s&' % urllib.quote(consumer_secret, safe='~')
  try:
    import hashlib
    hashed = hmac.new(hash_key, base_string, hashlib.sha1)
  except ImportError:
    import sha
    hashed = hmac.new(hash_key, base_string, sha)
  return base64.b64encode(hashed.digest())


def generate_rsa_signature():
  pass


def generate_auth_header(consumer_key, timestamp, nonce, signature_type,
                         signature, version='1.0', next=None, token=None,
                         verifier=None):
  """Builds the Authorization header to be sent in the request.
  
  Args:
    consumer_key: Identifies the application making the request (str).
    timestamp: 
    nonce:
    signature_type: One of either HMAC_SHA1 or RSA_SHA1
    signature: The HMAC or RSA signature for the request as a base64
        encoded string.
    version: The version of the OAuth protocol that this request is using.
        Default is '1.0'
    next: The URL of the page that the user's browser should be sent to
        after they authorize the token. (Optional)
    token: str The OAuth token value to be used in the oauth_token parameter
        of the header.
    verifier: str The OAuth verifier which must be included when you are
        upgrading a request token to an access token.
  """
  params = {
      'oauth_consumer_key': consumer_key,
      'oauth_version': version,
      'oauth_nonce': nonce,
      'oauth_timestamp': str(timestamp),
      'oauth_signature_method': signature_type,
      'oauth_signature': signature}
  if next is not None:
    params['oauth_callback'] = str(next)
  if token is not None:
    params['oauth_token'] = token
  if verifier is not None:
    params['oauth_verifier'] = verifier
  pairs = [
      '%s="%s"' % (
          k, urllib.quote(v, safe='~')) for k, v in params.iteritems()]
  return 'OAuth %s' % (', '.join(pairs))


REQUEST_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetRequestToken'
ACCESS_TOKEN_URL = 'https://www.google.com/accounts/OAuthGetAccessToken'


def generate_request_for_request_token(
    consumer_key, signature_type, scopes, rsa_key=None, consumer_secret=None,
    auth_server_url=REQUEST_TOKEN_URL, next='oob', version='1.0'):
  """Creates request to be sent to auth server to get an OAuth request token.
  
  Args:
    consumer_key: 
    signature_type: either RSA_SHA1 or HMAC_SHA1. The rsa_key must be
        provided if the signature type is RSA but if the signature method
        is HMAC, the consumer_secret must be used.
    scopes: List of URL prefixes for the data which we want to access. For
        example, to request access to the user's Blogger and Google Calendar
        data, we would request 
        ['http://www.blogger.com/feeds/', 
         'https://www.google.com/calendar/feeds/', 
         'http://www.google.com/calendar/feeds/']
    rsa_key: Only used if the signature method is RSA_SHA1.
    consumer_secret: Only used if the signature method is HMAC_SHA1.
    auth_server_url: The URL to which the token request should be directed.
        Defaults to 'https://www.google.com/accounts/OAuthGetRequestToken'.
    next: The URL of the page that the user's browser should be sent to
        after they authorize the token. (Optional)
    version: The OAuth version used by the requesting web application.
        Defaults to '1.0a'

  Returns:
    An atom.http_core.HttpRequest object with the URL, Authorization header
    and body filled in.
  """
  request = atom.http_core.HttpRequest(auth_server_url, 'POST')
  # Add the requested auth scopes to the Auth request URL.
  if scopes:
    request.uri.query['scope'] = ' '.join(scopes)
  timestamp = str(int(time.time()))
  nonce = ''.join([str(random.randint(0, 9)) for i in xrange(15)])
  if signature_type == HMAC_SHA1:
    signature = generate_hmac_signature(
        request, consumer_key, consumer_secret, timestamp, nonce, version,
        next=next)
    request.headers['Authorization'] = generate_auth_header(
        consumer_key, timestamp, nonce, signature_type, signature, version,
        next)
    request.headers['Content-Length'] = '0'
    return request
  elif signature_type == RSA_SHA1:
    return None
  return None


def generate_request_for_access_token(
    request_token, auth_server_url=ACCESS_TOKEN_URL):
  """Creates a request to ask the OAuth server for an access token.
  
  Requires a request token which the user has authorized. See the
  documentation on OAuth with Google Data for more details:
  http://code.google.com/apis/accounts/docs/OAuth.html#AccessToken

  Args:
    request_token: An OAuthHmacToken or OAuthRsaToken which the user has
        approved using their browser.
    auth_server_url: (optional) The URL at which the OAuth access token is
        requested. Defaults to 
        https://www.google.com/accounts/OAuthGetAccessToken

  Returns:
    A new HttpRequest object which can be sent to the OAuth server to
    request an OAuth Access Token.
  """
  http_request = atom.http_core.HttpRequest(auth_server_url, 'POST')
  http_request.headers['Content-Length'] = '0'
  return request_token.modify_request(http_request)


def oauth_token_info_from_body(http_body):
  """Exracts an OAuth request token from the server's response.
 
  Returns:
    A tuple of strings containing the OAuth token and token secret. If
    neither of these are present in the body, returns (None, None)
  """
  token = None
  token_secret = None
  for pair in http_body.split('&'):
    if pair.startswith('oauth_token='):
      token = urllib.unquote(pair[len('oauth_token='):])
    if pair.startswith('oauth_token_secret='):
      token_secret = urllib.unquote(pair[len('oauth_token_secret='):]) 
  return (token, token_secret)


def hmac_token_from_body(http_body, consumer_key, consumer_secret,
                         auth_state):
  token_value, token_secret = oauth_token_info_from_body(http_body)
  token = OAuthHmacToken(consumer_key, consumer_secret, token_value,
                         token_secret, auth_state)
  return token


DEFAULT_DOMAIN = 'default'
OAUTH_AUTHORIZE_URL = 'https://www.google.com/accounts/OAuthAuthorizeToken'


def generate_oauth_authorization_url(
    token, next=None, hd=DEFAULT_DOMAIN, hl=None, btmpl=None,
    auth_server=OAUTH_AUTHORIZE_URL):
  """Creates a URL for the page where the request token can be authorized.
  
  Args:
    token: str The request token from the OAuth server.
    next: str (optional) URL the user should be redirected to after granting
        access to a Google service(s). It can include url-encoded query
        parameters.
    hd: str (optional) Identifies a particular hosted domain account to be
        accessed (for example, 'mycollege.edu'). Uses 'default' to specify a
        regular Google account ('username@gmail.com').
    hl: str (optional) An ISO 639 country code identifying what language the
        approval page should be translated in (for example, 'hl=en' for
        English). The default is the user's selected language.
    btmpl: str (optional) Forces a mobile version of the approval page. The
        only accepted value is 'mobile'.
    auth_server: str (optional) The start of the token authorization web
        page. Defaults to 
        'https://www.google.com/accounts/OAuthAuthorizeToken'

  Returns: 
    An atom.http_core.Uri pointing to the token authorization page where the
    user may allow or deny this app to access their Google data.
  """
  uri = atom.http_core.Uri.parse_uri(auth_server)
  uri.query['oauth_token'] = token
  uri.query['hd'] = hd
  if next is not None:
    uri.query['oauth_callback'] = str(next)
  if hl is not None:
    uri.query['hl'] = hl
  if btmpl is not None:
    uri.query['btmpl'] = btmpl
  return uri
  

def oauth_token_info_from_url(url):
  """Exracts an OAuth access token from the redirected page's URL.

  Returns:
    A tuple of strings containing the OAuth token and the OAuth verifier which
    need to sent when upgrading a request token to an access token.
  """
  if isinstance(url, (str, unicode)):
    url = atom.http_core.Uri.parse_uri(url)
  token = None
  verifier = None
  if 'oauth_token' in url.query:
    token = urllib.unquote(url.query['oauth_token'])
  if 'oauth_verifier' in url.query:
    verifier = urllib.unquote(url.query['oauth_verifier'])
  return (token, verifier)


def authorize_request_token(request_token, url):
  """Adds information to request token to allow it to become an access token.

  Modifies the request_token object passed in by setting and unsetting the
  necessary fields to allow this token to form a valid upgrade request.
  
  Args:
    request_token: The OAuth request token which has been authorized by the
        user. In order for this token to be upgraded to an access token,
        certain fields must be extracted from the URL and added to the token
        so that they can be passed in an upgrade-token request.
    url: The URL of the current page which the user's browser was redirected
        to after they authorized access for the app. This function extracts
        information from the URL which is needed to upgraded the token from
        a request token to an access token.

  Returns:
    The same token object which was passed in.
  """
  token, verifier = oauth_token_info_from_url(url)
  request_token.token = token
  request_token.verifier = verifier
  request_token.auth_state = AUTHORIZED_REQUEST_TOKEN
  return request_token


AuthorizeRequestToken = authorize_request_token


def upgrade_to_access_token(request_token, server_response_body):
  """Extracts access token information from response to an upgrade request.
  
  Once the server has responded with the new token info for the OAuth
  access token, this method modifies the request_token to set and unset
  necessary fields to create valid OAuth authorization headers for requests.

  Args:
    request_token: An OAuth token which this function modifies to allow it
        to be used as an access token.
    server_response_body: str The server's response to an OAuthAuthorizeToken
        request. This should contain the new token and token_secret which
        are used to generate the signature and parameters of the Authorization
        header in subsequent requests to Google Data APIs.

  Returns:
    The same token object which was passed in.
  """
  token, token_secret = oauth_token_info_from_body(server_response_body)
  request_token.token = token
  request_token.token_secret = token_secret
  request_token.auth_state = ACCESS_TOKEN
  request_token.next = None
  request_token.verifier = None
  return request_token


REQUEST_TOKEN = 1
AUTHORIZED_REQUEST_TOKEN = 2
ACCESS_TOKEN = 3


class OAuthHmacToken(object):
  SIGNATURE_METHOD = 'HMAC-SHA1'

  def __init__(self, consumer_key, consumer_secret, token, token_secret,
               auth_state, next=None, verifier=None):
    self.consumer_key = consumer_key
    self.consumer_secret = consumer_secret
    self.token = token
    self.token_secret = token_secret
    self.auth_state = auth_state
    self.next = next
    self.verifier = verifier # Used to convert request token to access token.

  def generate_authorization_url(
      self, google_apps_domain=DEFAULT_DOMAIN, language=None, btmpl=None,
      auth_server=OAUTH_AUTHORIZE_URL):
    """Creates the URL at which the user can authorize this app to access.
    
    Args:
      google_apps_domain: str (optional) If the user should be signing in
          using an account under a known Google Apps domain, provide the
          domain name ('example.com') here. If not provided, 'default'
          will be used, and the user will be prompted to select an account
          if they are signed in with a Google Account and Google Apps
          accounts.
      language: str (optional) An ISO 639 country code identifying what 
          language the approval page should be translated in (for example,
          'en' for English). The default is the user's selected language.
      btmpl: str (optional) Forces a mobile version of the approval page. The
        only accepted value is 'mobile'.
      auth_server: str (optional) The start of the token authorization web
        page. Defaults to
        'https://www.google.com/accounts/OAuthAuthorizeToken'
    """
    return generate_oauth_authorization_url(
        self.token, hd=google_apps_domain, hl=language, btmpl=btmpl,
        auth_server=auth_server)

  GenerateAuthorizationUrl = generate_authorization_url

  def modify_request(self, http_request):
    """Sets the Authorization header in the HTTP request using the token.

    Calculates an HMAC signature using the information in the token to
    indicate that the request came from this application and that this
    application has permission to access a particular user's data.

    Returns:
      The same HTTP request object which was passed in.
    """
    timestamp = str(int(time.time()))
    nonce = ''.join([str(random.randint(0, 9)) for i in xrange(15)])
    signature = generate_hmac_signature(
        http_request, self.consumer_key, self.consumer_secret, timestamp,
        nonce, version='1.0', next=self.next, token=self.token,
        token_secret=self.token_secret, verifier=self.verifier)
    http_request.headers['Authorization'] = generate_auth_header(
        self.consumer_key, timestamp, nonce, HMAC_SHA1, signature,
        version='1.0', next=self.next, token=self.token,
        verifier=self.verifier)
    return http_request

  ModifyRequest = modify_request


def token_to_blob(token):
  """Serializes the token data as a string for storage in a datastore.
  
  Supported token classes: ClientLoginToken, AuthSubToken.

  Args:
    token: A token object which must be of one of the supported token classes.
  """
  if isinstance(token, ClientLoginToken):
    return '|'.join(('1c', urllib.quote_plus(token.token_string)))
  elif isinstance(token, AuthSubToken):
    token_string_parts = ['1a', urllib.quote_plus(token.token_string)]
    if token.scopes:
      token_string_parts.extend([urllib.quote_plus(url) for url in token.scopes])
    return '|'.join(token_string_parts)

def token_from_blob(blob):
  if blob.startswith('1c|'):
    return ClientLoginToken(urllib.unquote_plus(blob.split('|')[1]))
  elif blob.startswith('1a|'):
    parts = [urllib.unquote_plus(part) for part in blob.split('|')]
    return AuthSubToken(parts[1], parts[2:])


def dump_tokens(tokens):
  return ','.join([token_to_blob(t) for t in tokens])


def load_tokens(blob):
  return [token_from_blob(s) for s in blob.split(',')]


def ae_save(token, token_key):
  import gdata.alt.app_engine
  key_name = ''.join(('gd_auth_token', token_key))
  return gdata.alt.app_engine.set_token(key_name, token_to_blob(token))


def ae_load(token_key):
  import gdata.alt.app_engine
  key_name = ''.join(('gd_auth_token', token_key))
  token_string = gdata.alt.app_engine.get_token(key_name)
  if token_string is not None:
    return token_from_blob(token_string)
  else:
    return None


def ae_delete(token_key):
  import gdata.alt.app_engine
  key_name = ''.join(('gd_auth_token', token_key))
  gdata.alt.app_engine.delete_token(key_name)
