from __future__ import unicode_literals
from __future__ import print_function


from httpretty import HTTPretty, httprettified
import json
import mock
import pytest
import re
from contextlib import contextmanager

import uritemplate

import rest_navigator.halnav as HN

@contextmanager
def httprettify():
    '''Context manager to do what the @httprettified decorator does (without mucking
    up py.test's magic)

    '''
    HTTPretty.reset()
    HTTPretty.enable()
    try:
        yield HTTPretty
    finally:
        HTTPretty.disable()


def register_hal(url, links=None, state=None, title=None, method='GET', headers=None):
    '''Convenience function that registers a hal document at a given address'''

    def body_callback(_meth, req_url, req_headers):
        '''This is either registered for dynamic urls or is called for a static url'''
        _links = links.copy() if links is not None else {}
        _state = state.copy() if state is not None else {}
        resp_headers = headers.copy() if headers is not None else {}
        resp_headers.update({'content_type': 'application/hal+json',
                             'server': 'HTTPretty 0.6.0'})
        print('Server got: {}'.format(req_url))
        _links.update({'self': {'href': req_url}})
        if title is not None:
            _links['self']['title'] = title
        _state.update({'_links': _links})
        return 200, resp_headers, json.dumps(_state)

    HTTPretty.register_uri(method=method,
                           body=body_callback,
                           uri=url)



def test_HALNavigator__creation():
    N = HN.HALNavigator('http://www.example.com')
    assert type(N) == HN.HALNavigator
    assert repr(N) == "HALNavigator('http://www.example.com')"


def test_HALNavigator__optional_name():
    N = HN.HALNavigator('http://www.example.com', name='exampleAPI')
    assert repr(N) == "HALNavigator('exampleAPI')"


def test_HALNavigator__links():
    with httprettify():
        register_hal('http://www.example.com/',
                     links={'ht:users': {'href': 'http://www.example.com/users'}})
        N = HN.HALNavigator('http://www.example.com')
        assert N.links == {'ht:users':
                           HN.HALNavigator('http://www.example.com')['ht:users']}

def test_HALNavigator__call():
    with httprettify():
        url = 'http://www.example.com/index'
        server_state = dict(some_attribute='some value')
        register_hal(url=url, state=server_state, title='Example Title')

        N = HN.HALNavigator(url)
        assert N.state is None
        assert N() == server_state
        assert N.state == N()
        assert N.state is not N()
        assert N() is not N()

def test_HALNavigator__init_accept_schemaless():
    url = 'www.example.com'
    N = HN.HALNavigator(url)
    assert N.url == 'http://' + url
    url2 = 'http://example.com'
    N2 = HN.HALNavigator(url2)
    assert N2.url == url2

def test_HALNavigator__getitem_self_link():
    with httprettify():
        url = 'http://www.example.com/index'
        title = 'Some kinda title'
        register_hal(url, title=title)

        N = HN.HALNavigator(url)
        N()  # fetch it
        assert N.title == title


def test_HALNavigator__identity_map():
    with httprettify():
        index_url = 'http://www.example.com/'
        page1_url = index_url + '1'
        page2_url = index_url + '2'
        page3_url = index_url + '3'
        index_links = {'first': {'href': page1_url}}
        page1_links = {'next': {'href': page2_url}}
        page2_links = {'next': {'href': page3_url}}
        page3_links = {'next': {'href': page1_url}}

        register_hal(index_url, index_links)
        register_hal(page1_url, page1_links)
        register_hal(page2_url, page2_links)
        register_hal(page3_url, page3_links)

        N = HN.HALNavigator(index_url)
        page1 = N['first']
        page2 = N['first']['next']
        page3 = N['first']['next']['next']
        page4 = N['first']['next']['next']['next']
        assert page1 is page4
        assert page2 is page4['next']
        assert page3 is page4['next']['next']

def test_HALNavigator__iteration():
    with httprettify():
        index_url = 'http://www.example.com/'
        index_links = {'next': {'href': index_url + '1'}}
        register_hal(index_url, index_links)
        for i in xrange(1, 11):
            page_url = index_url + str(i)
            if i < 10:
                page_links = {'next': {'href': index_url + str(i + 1)}}
            else:
                page_links = {}
            print(page_url, page_links)
            register_hal(page_url, page_links)

        N = HN.HALNavigator(index_url)
        captured = []
        for i, nav in enumerate(N, start=1):
            print('{}: {}'.format(i, nav.url))
            assert isinstance(nav, HN.HALNavigator)
            assert nav.url == index_url + str(i)
            captured.append(nav)
        assert len(captured) == 10

def test_HALNavigator__dont_get_template_links():
    with httprettify():
        index_url = 'http://www.example.com/'
        index_regex = re.compile(index_url + '.*')
        template_href = 'http://www.example.com/{?max,page}'
        index_links = {'first': {
            'href': template_href,
            'templated': True
        }}
        register_hal(index_regex, index_links)
        
        N = HN.HALNavigator(index_url)
        with pytest.raises(ValueError):
            N['page':0]  # N is not templated
        with pytest.raises(HN.exc.AmbiguousNavigationError):
            N['first']() # N['first'] is templated
        assert N['first'].templated
        assert N['first']['page':0].url == 'http://www.example.com/?page=0'
        with pytest.raises(ValueError):
            N['first'][:'page':0]
        with pytest.raises(ValueError):
            N['first'][::'page']

def test_HALNavigator__complete_template_links():
    with httprettify():
        index_url = 'http://www.example.com/'
        index_regex = re.compile(index_url + '.*')
        template_href = 'http://www.example.com/{?max,page}'
        index_links = {'first': {
            'href': template_href,
            'templated': True
        }}
        register_hal(index_regex, index_links)
        
        N = HN.HALNavigator(index_url)
        expanded_nav =  N['first', 'page':0, 'max':1]
        assert expanded_nav.url == uritemplate.expand(template_href, max=1, page=0)
        assert N['first'].expand(page=0, max=1) == expanded_nav
        assert N['first']['page':0] == uritemplate.expand(template_href, page=0)
        assert N['first',:] == uritemplate.expand(template_href)
        
        assert N['page': 0]
        assert N[...]
        assert N['page': 0, ...]
        assert N[:]
        assert N['page':0, :]
        with pytest.raises(SyntaxError):
            N[:,...]
        with pytest.raises(SyntaxError)
            N['page':0, :, ...]
        assert N['first']
        assert N['first', 'page': 0]
        assert N['first', ...]
        assert N['first', 'page':0, ...]
        assert N['first', :]
        assert N['first', 'page':0, :]
        with pytest.raises(SyntaxError):
            assert N['first', :, ...]
        with pytest.raises(SyntaxError):
            assert N['first', 'page': 0, :, ...]


