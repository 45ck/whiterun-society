"""Execution qualification for paid labour; historical records remain readable."""

PAID_WORK_BLOCK_REASON = 'legacy_paid_execution_unqualified'


def paid_work_capability():
    return {
        'available': False,
        'protocol': 1,
        'reason': PAID_WORK_BLOCK_REASON,
        'detail': 'Paid production requires session-bound attendance and issued/observed inventory and wage witnesses. Legacy execution is held for reconciliation.',
    }
