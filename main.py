import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

ROUTER_BASE = "http://192.168.1.254"
POST_PATH = "/advancedsetup_lanipdhcpsettings.cgi"


def find_session_key(text: str) -> str | None:
    patterns = [
        r"sessionKey=([A-Za-z0-9]+)",
        r"sessionKey['\"]?\s*[:=]\s*['\"]([A-Za-z0-9]+)['\"]",
        r"name=['\"]sessionKey['\"][^>]*value=['\"]([^'\"]+)['\"]",
        r"value=['\"]([^'\"]+)['\"][^>]*name=['\"]sessionKey['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


# Extract just the IP address from the ROUTER_BASE URL
router_ip = urlparse(ROUTER_BASE).hostname

options = Options()
# Using a Context Manager to handle driver setup and teardown automatically
with webdriver.Chrome(options=options) as driver:
    driver.set_script_timeout(30)

    driver.get(ROUTER_BASE)

    input(
        "Log in to the router, go to Advanced Setup > LAN IP Settings, "
        "then press Enter here..."
    )

    page_text = driver.page_source + "\n" + driver.current_url
    session_key = find_session_key(page_text)

    if not session_key:
        session_key = input("Could not auto-find sessionKey. Paste it here: ").strip()

    # Dynamic payload based on the router's actual IP
    payload = {
        "enblDhcpSrv": "1",
        "dhcpEthStart": "192.168.1.64",
        "dhcpEthEnd": "192.168.1.63",  # The intentionally broken end IP
        "dhcpSubnetMask": "255.255.255.0",
        "dhcpLeasedTime": "1440",
        "landnsType1": "default",
        "landnsPrimary": "192.168.1.254",
        "landnsType2": "dynamic",
        "landnsSecondary": "0.0.0.0",
        "dnsRefresh": "1",
        "sessionKey": session_key,
        "nothankyou": "0",
    }

    post_url = urljoin(ROUTER_BASE, POST_PATH)

    # Added AbortController to the JS to prevent silent hangs
    result = driver.execute_async_script(
        """
        const url = arguments[0];
        const data = arguments[1];
        const done = arguments[2];

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

        fetch(url, {
            method: "POST",
            credentials: "same-origin",
            signal: controller.signal,
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: new URLSearchParams(data).toString()
        })
        .then(async response => {
            clearTimeout(timeoutId);
            const text = await response.text();
            done({
                status: response.status,
                ok: response.ok,
                bodyPreview: text.slice(0, 1000)
            });
        })
        .catch(error => {
            clearTimeout(timeoutId);
            done({
                error: error.name === 'AbortError' ? 'Request timed out' : String(error)
            });
        });
        """,
        post_url,
        payload,
    )

    print(result)