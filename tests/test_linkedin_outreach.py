from job_hunter.scrapers.linkedin_outreach import LinkedInOutreach
from unittest.mock import MagicMock, patch
import pytest

@patch("job_hunter.scrapers.linkedin_outreach.BrowserManager")
@patch("job_hunter.scrapers.linkedin_outreach.DataManager")
def test_linkedin_outreach_init(mock_dm, mock_bm):
    outreach = LinkedInOutreach()
    assert outreach.bm is not None
    assert outreach.db is not None

def test_get_first_name():
    outreach = LinkedInOutreach()
    assert outreach.get_first_name("John Doe") == "John"
    assert outreach.get_first_name("Alice") == "Alice"
    assert outreach.get_first_name("") == "Sir/Madam"
    assert outreach.get_first_name(None) == "Sir/Madam"

@patch("job_hunter.scrapers.linkedin_outreach.BrowserManager")
@patch("job_hunter.scrapers.linkedin_outreach.DataManager")
def test_send_message_draft_mode(mock_dm, mock_bm):
    # Mock driver and elements
    mock_driver = MagicMock()
    mock_bm.return_value.get_driver.return_value = mock_driver

    outreach = LinkedInOutreach()
    outreach.driver = mock_driver

    connection = {
        "name": "John Doe",
        "first_name": "John",
        "element": MagicMock()
    }

    # Mock finding message box
    mock_msg_box = MagicMock()
    mock_driver.find_elements.return_value = [mock_msg_box]

    with patch("job_hunter.scrapers.linkedin_outreach.type_human_like") as mock_type:
        success = outreach.send_message(connection, "Hello {first_name}", auto_send=False)

        assert success is True
        mock_type.assert_called()
        # Ensure click on send button was NOT called
        mock_driver.find_element.assert_not_called()
