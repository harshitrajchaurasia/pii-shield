"""Edge case tests for PI Remover case sensitivity and context preservation."""

import sys
sys.path.insert(0, 'src')
from pi_remover.core import PIRemover, PIRemoverConfig


def test_edge_cases():
    """Test edge cases with corrected expectations based on actual token names."""
    config = PIRemoverConfig(enable_ner=False)
    remover = PIRemover(config=config)

    # Full edge case test suite with correct token names
    test_cases = [
        # Case sensitivity - Names (with context keywords)
        ('from Rahul Sharma', 'from [NAME]'),  # proper case
        ('by JOHN DOE', 'by [NAME]'),  # uppercase by
        ('from rahul sharma', 'from [NAME]'),  # lowercase 
        ('by john doe', 'by [NAME]'),  # lowercase by
        
        # Case sensitivity - Excluded words (should NOT be matched as names)
        ('from support team', 'from support team'),  # support is excluded
        ('from seat a1f 102', 'from seat [SEAT]'),  # seat is excluded
        
        # THE MAIN BUG FIX - "from" should not be captured as part of name
        ('Caller rahul sharma from seat a1f 102 reported network issue',
         'Caller [NAME] from seat [SEAT] reported network issue'),
        
        # Seat patterns - context preserved  
        ('User at seat B2F-456 needs help', 'User at seat [SEAT] needs help'),
        ('desk A2F-123', 'desk [SEAT]'),
        
        # IT/ITSM patterns - using actual token names
        ('JIRA: ABC-1234', 'JIRA: [TICKET]'),  # TICKET is the actual token
        ('jira abc-1234', 'jira [TICKET]'),  # lowercase
        ('ticket: INC12345678', 'ticket: [TICKET_NUM]'),  # TICKET_NUM is actual
        ('TICKET: INC12345678', 'TICKET: [TICKET_NUM]'),
        
        # Identity documents - using actual token names
        ('PAN ABCDE1234F', 'PAN [PAN]'),  # PAN is actual token
        ('pan abcde1234f', 'pan [PAN]'),  # lowercase
        
        # Phone and email  
        ('call +91 9876543210', 'call [PHONE]'),
        ('email: john.doe@company.com', 'email: [EMAIL]'),
        
        # IP addresses - using actual token name
        ('server 192.168.1.100', 'server [IP]'),  # IP is actual token
        
        # Context preservation - labels should remain
        ('Email: test@example.com', 'Email: [EMAIL]'),
        ('Phone: 9876543210', 'Phone: [PHONE]'),
        ('IP Address: 10.0.0.1', 'IP Address: [IP]'),
        
        # Additional context patterns
        ('assigned to rahul sharma and approved by john doe',
         'assigned to [NAME] and approved by [NAME]'),
        ('created by John Doe', 'created by [NAME]'),
    ]

    print('Full Edge Case Test Suite (Corrected Token Names):')
    print('=' * 70)

    passed = 0
    failed = []
    for i, (test_input, expected) in enumerate(test_cases, 1):
        result = remover.redact(test_input)
        if result == expected:
            passed += 1
            print(f'{i:2}. PASS: {test_input!r}')
        else:
            failed.append((i, test_input, expected, result))
            print(f'{i:2}. FAIL: {test_input!r}')
            print(f'         Expected: {expected!r}')
            print(f'         Got:      {result!r}')

    print('=' * 70)
    print(f'Results: {passed}/{len(test_cases)} passed')

    if failed:
        print(f'\nFailed tests ({len(failed)}):')
        for i, inp, exp, got in failed:
            print(f'  {i}. {inp!r}')
    
    return passed == len(test_cases)


if __name__ == '__main__':
    success = test_edge_cases()
    sys.exit(0 if success else 1)
