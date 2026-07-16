from unittest.mock import patch, Mock

mock_sock = Mock(name="mock_socket", recv=Mock(return_value=None))


class TestServerMocked:

    # def test_writing_to_csv_file_mocked(self, mock_file_open):
    #     pass

    def test_handle_read_drops_client_on_empty_data(self):
        """Verify the client drops and closes a client socket when empty data is received."""
        with patch("client.connect", new_callable=Mock(return_value=Mock(return_value=mock_sock))):
            from client import run_reader
            run_reader(Mock(), Mock())
            mock_sock.close.assert_called()
