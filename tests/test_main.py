import pytest

from main import app

# Routes that don't return 200 OK without query/post parameters
SKIP_ROUTES = frozenset(("/staticmap", "/page"))

REQ_METHODS = set(["GET", "POST"])


@pytest.fixture
def client():
    """ Create Flask's modified Werkzeug client to use in tests """
    app.config["TESTING"] = True
    client = app.test_client()
    return client


def test_routes(client):
    """ Test all non-argument routes in Flask app """
    for rule in app.url_map.iter_rules():
        route = str(rule)
        if rule.arguments or route in SKIP_ROUTES:
            continue

        for m in REQ_METHODS.intersection(set(rule.methods)):
            # Make request for each method supported by route
            method = getattr(client, m.lower())
            resp = method(route)
            assert resp.status == "200 OK"
