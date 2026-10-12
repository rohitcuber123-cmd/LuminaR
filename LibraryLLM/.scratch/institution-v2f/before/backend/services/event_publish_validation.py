"""Shared, category-driven publication contract; drafts keep the base Event schema."""
import json
from pathlib import Path

from fastapi import HTTPException

EVENT_PUBLISH_REQUIREMENTS = json.loads(
    (Path(__file__).resolve().parents[1] / 'schemas/event_publish_requirements.json').read_text(encoding='utf8'))


def publish_errors(event):
    rule = EVENT_PUBLISH_REQUIREMENTS[event['category']]
    errors = [{'field': field, 'message': message} for field, message in rule['fields'].items()
              if not event.get(field) or isinstance(event[field], str) and not event[field].strip()]
    if len(event.get('related_work_ids', [])) < rule['min_books']:
        errors.append({'field': 'related_work_ids', 'message': rule['books_error']})
    return errors


def validate_publish(event):
    errors = publish_errors(event)
    if errors:
        # A string detail remains compatible with the existing API error renderer.
        raise HTTPException(422, ' '.join(error['message'] for error in errors))


def requires_published_validation(old, merged):
    # Existing V1 publications remain editable without a backfill. Changing their
    # category adopts the new contract; compliant publications cannot regress.
    return old['category'] != merged['category'] or not publish_errors(old)
