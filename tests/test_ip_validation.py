import pytest

from app import validate_ip_address


class TestValidateIpAddress:

    def test_valid_ipv4(self):
        assert validate_ip_address("192.168.1.1") == "192.168.1.1"

    def test_valid_ipv4_loopback(self):
        assert validate_ip_address("127.0.0.1") == "127.0.0.1"

    def test_valid_ipv6(self):
        assert validate_ip_address("::1") == "::1"

    def test_valid_ipv6_full(self):
        result = validate_ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert result == "2001:db8:85a3::8a2e:370:7334"

    def test_leading_zeros_ipv4_rejected(self):
        with pytest.raises(ValueError, match="無効なIPアドレス形式"):
            validate_ip_address("192.168.001.001")

    def test_invalid_string(self):
        with pytest.raises(ValueError, match="無効なIPアドレス形式"):
            validate_ip_address("not_an_ip")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="無効なIPアドレス形式"):
            validate_ip_address("")

    def test_partial_ipv4(self):
        with pytest.raises(ValueError, match="無効なIPアドレス形式"):
            validate_ip_address("192.168.1")

    def test_ipv4_out_of_range(self):
        with pytest.raises(ValueError, match="無効なIPアドレス形式"):
            validate_ip_address("256.256.256.256")
