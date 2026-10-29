"""Native capability enforcement for the disabled candidate, not production routing."""
from . import legacy

VERSION='V10-capability-registry-v2'
SCOPES=('GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF')


def mask(scope):
    if scope not in SCOPES:raise ValueError('Unknown backend scope')
    local=scope!='GLOBAL'
    return dict(rating=True,year=local,language=local,availability=local,
                formats=['ONLINE','PHYSICAL','BOTH'] if local else ['ONLINE'])


def check(plan,scope):
    """Never accept scope from query text. Existing EXACT behavior is preserved."""
    caps=mask(scope)
    from .parser import validate
    return validate(plan,caps)
