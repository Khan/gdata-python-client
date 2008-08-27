#!/usr/bin/python
#
# Copyright (C) 2008 Google Inc.
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

"""This module provides a TokenStore class which is designed to manage
auth tokens required for different services.

Each token is valid for a set of scopes which is the start of a URL. An HTTP
client will use a token store to find a valid Authorization header to send
in requests to the specified URL. If the HTTP client determines that a token
has expired or been revoked, it can remove the token from the store so that
it will not be used in future requests.
"""


__author__ = 'api.jscudder (Jeff Scudder)'


SCOPE_ALL = 'http://'


class TokenStore(object):
  """Manages Authorization tokens which will be sent in HTTP headers."""
  def __init__(self, scoped_tokens=None):
    self._tokens = scoped_tokens or {}

  def add_token(self, token, scopes):
    """Adds a new token to the store (replaces tokens with the same scope).

    Args:
      token: str The token value to be sent as the value for the 
          Authorization header in an HTTP request.
      scopes: list of atom.url.Url objects, or strings which specify the
          URLs for which this token can be used. These do not need to be
          full URLs, any URL that begins with the scope will be considered
          a match.

    Returns:
      True if the token was added, False if the token was not added becase
      no scopes were provided.
    """
    if scopes:
      for scope in scopes:
        self._tokens[str(scope)] = token
      return True
    else:
      return False

  def find_token(self, url):
    """Selects an Authorization header token which can be used for the URL.

    Args:
      url: str or atom.url.Url The URL which is going to be requested. All
          tokens are examined to see if any scopes begin match the beginning
          of the URL. The first match found is returned.

    Returns:
      The token string to be used in the Authorization headers, or None, if 
      the url did not begin with any of the token scopes available. 
    """
    url = str(url)
    if url in self._tokens:
      return self._tokens[url]
    else:
      for scope, token in self._tokens.iteritems():
        if url.startswith(scope):
          return token
    return None

  def remove_token(self, url):
    """Removes the first token which is considered valid for the URL.

    See find_token for information on how the correct token for the URL is
    found.

    Returns:
      True if a token was found for the url and then removed from the token
      store. False if no token was found that matches the URL.
    """
    url = str(url)
    if url in self._tokens:
      del self._tokens[url]
      return True
    else:
      for scope in self._tokens:
        if url.startswith(scope):
          del self._tokens[scope]
          return True
    return False
