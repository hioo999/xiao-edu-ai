def preview_policy() -> dict[str, str]:
    return {
        "sandbox": "allow-scripts",
        "contentSecurityPolicy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'unsafe-inline'",
        "allowTopNavigation": "false",
        "allowCookies": "false",
    }
