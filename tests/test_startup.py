def test_application_imports_with_supported_mcp_sdk() -> None:
    from pogeo.main import app

    assert app.title == "PoGeo"
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
