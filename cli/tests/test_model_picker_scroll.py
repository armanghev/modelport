from modelport_agent_config.model_picker import MODEL_PAGE_SIZE, SCROLL_MARGIN, _list_window_height


def test_list_window_height_accounts_for_hints() -> None:
    assert _list_window_height() == MODEL_PAGE_SIZE + 2
    assert SCROLL_MARGIN >= 1
