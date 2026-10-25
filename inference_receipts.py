"""Finite rejected-response telemetry, without provider bodies or generated text."""
import math
import re


CANDIDATE_FAILURES = {
    'Expected candidate object': 'candidate_object',
    'Exactly two bounded intentions required': 'candidate_count',
    'Invalid candidate fields': 'candidate_fields',
    'Invalid candidate ID': 'candidate_id',
    'Invalid candidate text': 'candidate_text',
    'Invalid spoken length or tone': 'spoken_length_or_tone',
    'Two distinct alternatives required': 'duplicate_alternatives',
}
FAILURES = frozenset(CANDIDATE_FAILURES.values()) | {'invalid_json', 'response_shape', 'incomplete_output'}
FINISH_REASONS = ('stop', 'length', 'content_filter', 'tool_calls', 'error', 'unknown')


def usage_receipt(raw):
    result = {}
    if not isinstance(raw, dict):
        return result
    for field in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'cost'):
        value = raw.get(field)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            result[field] = value
    details = raw.get('completion_tokens_details')
    if isinstance(details, dict):
        value = details.get('reasoning_tokens')
        if type(value) is int and value >= 0:
            result['completion_tokens_details'] = {'reasoning_tokens': value}
    return result


def rejected_language_receipt(raw):
    if not isinstance(raw, dict):
        raise ValueError('Missing rejected inference receipt')
    model = raw.get('model')
    elapsed = raw.get('elapsed_seconds')
    failure = raw.get('validation_failure')
    if (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}', model)
            or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
            or not isinstance(failure, str) or failure not in FAILURES):
        raise ValueError('Invalid rejected inference receipt')
    finish = raw.get('finish_reason')
    return {'model': model, 'elapsed_seconds': elapsed, 'usage': usage_receipt(raw.get('usage')),
            'finish_reason': finish if finish in FINISH_REASONS else 'unknown',
            'validation_failure': failure, 'accepted': False}
