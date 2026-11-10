import base64
import gzip
import socket
import ssl
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError, HTTPError
import bridge
from controller import Bridge

URL='https://example.invalid/subscription/SECRET_TOKEN'
BODY=b'vless://11111111-1111-1111-1111-111111111111@example.invalid:443?security=tls#Test'


class DownloadTests(unittest.TestCase):
    def download(self, body, headers=None):
        response=Mock(headers=headers or {})
        response.read.return_value=body
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        opener=Mock()
        opener.open.return_value=response
        with patch('bridge.build_opener',return_value=opener):
            result=bridge.load_subscription(URL,with_metadata=True)
        return result

    def test_plain_and_gzip_subscriptions(self):
        plain=self.download(BODY)[0]
        compressed=self.download(gzip.compress(base64.b64encode(BODY)),{'Content-Encoding':'gzip','subscription-userinfo':'total=1000; expire=1234'})
        self.assertEqual(plain,compressed[0])
        self.assertEqual(compressed[2],{'total':1000,'expire':1234})

    def test_html_empty_and_corrupt_gzip(self):
        for body,headers,code in [(b'<html>login</html>',{},'SUB_HTML'),(b'',{},'SUB_EMPTY'),(b'bad',{'Content-Encoding':'gzip'},'SUB_GZIP')]:
            with self.subTest(code=code),self.assertRaisesRegex(ValueError,code):
                self.download(body,headers)

    def test_decompression_limit(self):
        with self.assertRaisesRegex(ValueError,'4 МБ'):
            self.download(gzip.compress(b'a'*(bridge.LIMIT+1)),{'Content-Encoding':'gzip'})

    def test_tls_preserves_system_roots_and_verification(self):
        context=bridge.subscription_tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertGreater(context.cert_store_stats()['x509_ca'],0)
        with patch('bridge.ssl.create_default_context') as factory:
            bridge.subscription_tls_context()
        factory.assert_called_once_with()
        factory.return_value.load_verify_locations.assert_called_once_with(cafile=bridge.certifi.where())

    def test_direct_retry_is_explicit_and_does_not_change_default_route(self):
        response=Mock(headers={})
        response.read.return_value=BODY
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        opener=Mock()
        opener.open.return_value=response
        with patch('bridge.build_opener',return_value=opener) as factory:
            bridge.load_subscription(URL)
            self.assertFalse(any(isinstance(handler,bridge.ProxyHandler) for handler in factory.call_args.args))
            bridge.load_subscription(URL,use_system_proxy=False)
            handler=factory.call_args.args[0]
            self.assertIsInstance(handler,bridge.ProxyHandler)
            self.assertEqual(handler.proxies,{})

    def test_insecure_redirect_still_rejected(self):
        with self.assertRaises(ValueError):
            bridge.SecureRedirect().redirect_request(None,None,302,'',{},'http://example.invalid/')


class ErrorTests(unittest.TestCase):
    def test_diagnostics_preserve_existing_servers_and_hide_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            api=Bridge(directory)
            api._nodes={'existing':{'protocol':'vless'}}
            errors=[(URLError(socket.gaierror('SECRET_TOKEN')),'SUB_DNS'),
                    (URLError(TimeoutError('SECRET_TOKEN')),'SUB_TIMEOUT'),
                    (URLError(ssl.SSLCertVerificationError('SECRET_TOKEN')),'SUB_TLS'),
                    (URLError(ConnectionRefusedError('SECRET_TOKEN')),'SUB_REFUSED'),
                    (HTTPError(URL,403,'SECRET_TOKEN',{},None),'SUB_HTTP_403')]
            try:
                for error,code in errors:
                    with self.subTest(code=code),patch('controller.load_subscription',side_effect=error):
                        result=api.load(URL)
                    self.assertIn(code,result['error'])
                    self.assertNotIn('SECRET_TOKEN',result['error'])
                    self.assertEqual(api.servers()['names'],['existing'])
            finally:
                api._close_window()
                api._wake.set()
                api._monitor.join(timeout=2)
                api._store.db.close()


if __name__=='__main__': unittest.main()
