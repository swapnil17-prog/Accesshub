from marshmallow import RAISE, Schema


class BaseSchema(Schema):
    """Unknown input keys are rejected (422) rather than silently ignored."""

    class Meta:
        unknown = RAISE
        ordered = True
