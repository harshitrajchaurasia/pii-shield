"""US-format PII: the values must disappear, the surrounding text must survive."""
import pytest

from pi_remover import PIRemover, PIRemoverConfig


@pytest.fixture(scope="module")
def remover():
    return PIRemover(PIRemoverConfig(enable_ner=True, spacy_model="en_core_web_md", use_typed_tokens=True))


# (input, values that must be gone, text that must remain)
CASES = [
    ("My name is Emily Johnson and my SSN is 123-45-6789.",
     ["Emily", "Johnson", "123-45-6789"], ["and my SSN is"]),
    ("SSN 123456789 on file.", ["123456789"], ["SSN", "on file."]),
    ("Call me at (415) 555-0132 or +1 212 555 0147.",
     ["415", "0132", "212 555"], ["Call me at", " or "]),
    ("I live at 742 Evergreen Terrace, Springfield, IL 62704.",
     ["742 Evergreen", "62704"], ["I live at"]),
    ("Ship to 1600 Pennsylvania Ave NW, Washington, DC 20500.", ["1600 Pennsylvania", "20500"], ["Ship to"]),
    ("Apt 4B, 350 Fifth Avenue, New York, NY 10118-0110", ["350 Fifth", "10118"], []),
    ("Visa 4111 1111 1111 1111 exp 04/28 CVV 123", ["4111", "CVV 123", "04/28"], ["Visa", "exp"]),
    ("Amex 3782 822463 10005", ["822463"], ["Amex"]),
    ("Routing number 021000021, account number 000123456789.",
     ["021000021", "000123456789"], ["Routing number", "account number"]),
    ("California driver's license D1234567.", ["D1234567"], ["driver's license"]),
    ("Driver's License #: S530-4123-9876 (Florida)", ["S530-4123-9876"], ["Driver's License"]),
    ("US passport number 123456789.", ["123456789"], ["passport number"]),
    ("My EIN is 12-3456789.", ["3456789", "12-"], ["My EIN is"]),
    ("Medicare number 1EG4-TE5-MK73", ["1EG4-TE5-MK73"], ["Medicare number"]),
    ("Date of birth: April 15, 1988", ["April 15, 1988"], ["Date of birth"]),
    ("DOB: 04/15/1988", ["04/15/1988"], ["DOB"]),
    ("Patient MRN: 00451234, diagnosed with type 2 diabetes.", ["00451234"], ["diagnosed with type 2 diabetes"]),
    ("Policy holder: David Martinez, member ID XWZ123456789", ["David", "Martinez", "XWZ123456789"], ["member ID"]),
    ("Dear Michael Brown, thank you for your order.", ["Michael", "Brown"], ["thank you for your order."]),
    ("Hi, I'm Sarah O'Connor from Austin, Texas.", ["Sarah", "O'Connor"], ["Hi, I'm", "from"]),
    ("password: Hunter2!", ["Hunter2"], ["password"]),
    ("VIN 1HGCM82633A004352", ["1HGCM82633A004352"], ["VIN [VIN]"]),
    ("Server 2001:db8::1 is down.", ["db8"], ["Server", "is down."]),
    ("License plate 7ABC123, registered in Ohio.", ["7ABC123"], ["License plate", "Ohio"]),
    ("My wife's ITIN is 912-71-4455.", ["912-71-4455"], ["[ITIN]"]),
    ("Card 4532-0151-2345-6789, call (972) 555-0186.", ["4532", "972", "0186"], ["[CARD]", "[PHONE_US]"]),
]

# Text with no PII must come back unchanged.
CLEAN = [
    "The meeting is at 3 PM on Tuesday in room 204.",
    "Order #12345 shipped on 11/20/2026 for $45.99.",
    "Version 2.5 cut latency by 3.2x.",
    "Line one\n\nLine two\n- bullet",
    "Thanks for the help! Can you also summarize the attached report?",
    "Can you explain how Kubernetes handles pod scheduling? Use 3 nodes and 2.5 GB memory.",
    "We file jointly in California and spend summers in Colorado.",
]


@pytest.mark.parametrize("text,gone,kept", CASES)
def test_us_pii(remover, text, gone, kept):
    out = remover.redact(text)
    for v in gone:
        assert v not in out, f"{v!r} leaked: {out!r}"
    for k in kept:
        assert k in out, f"{k!r} lost: {out!r}"


@pytest.mark.parametrize("text", CLEAN)
def test_clean_text_untouched(remover, text):
    assert remover.redact(text) == text


def test_signoff_only_redacts_signature(remover):
    text = "Please review my claim.\n\nThanks,\nJennifer Lopez\n(312) 555-0144"
    out = remover.redact(text)
    assert out.startswith("Please review my claim.")
    assert "Jennifer" not in out and "0144" not in out


def test_details_match_text(remover):
    d = remover.redact_with_details("Email jane.doe@example.com, SSN 123-45-6789.")
    assert d.redacted_text.count("[") == len(d.redactions)
    assert {r.original for r in d.redactions} >= {"jane.doe@example.com", "123-45-6789"}


def test_us_token_names():
    r = PIRemover(PIRemoverConfig(enable_ner=False, use_granular_tokens=False,
                                  token_aliases={"DL": "DRIVERS_LICENSE", "ROUTING_NUM": "ROUTING_NUMBER"}))
    out = r.redact("Call (415) 555-0132, driver's license D1234567, routing 021000021.")
    assert out == "Call [PHONE], driver's license [DRIVERS_LICENSE], routing [ROUTING_NUMBER]."
